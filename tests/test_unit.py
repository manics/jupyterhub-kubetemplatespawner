from collections import namedtuple

import pytest
import yaml
from kubernetes_asyncio.dynamic.resource import ResourceInstance
from traitlets import TraitError

import kubetemplatespawner.spawner

from .conftest import ROOT_DIR

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest.fixture(autouse=True)
def mock_k8s_client(mocker):
    mocker.patch("kubetemplatespawner.spawner.load_config")
    mocker.patch("kubetemplatespawner.spawner.ApiClient")
    mocker.patch("kubetemplatespawner.spawner.DynamicClient")


class MockKubeTemplateSpawner(kubetemplatespawner.spawner.KubeTemplateSpawner):
    def get_env(self):
        # So that we don't need to mock hub to set environment variables
        return {"TEST": "Test\nKubeTemplateSpawner"}


def mock_spawner(username="user-1", servername="", namespace="default", **kwargs):
    k = MockKubeTemplateSpawner(
        template_path=str(ROOT_DIR / "example"),
        user=namedtuple("User", "id name")(12, username),
        orm_spawner=namedtuple("ORMSpawner", "name server")(servername, None),
        namespace=namespace,
        **kwargs,
    )
    return k


async def test_validate_name_valid():
    _ = mock_spawner(servername="a.b-c")


async def test_validate_name_invalid():
    with pytest.raises(TraitError):
        _ = mock_spawner(servername="🦆")


async def test_template_vars():
    k = mock_spawner(
        "user-1@🐧",
        "- +",
        extra_vars=lambda self: {"UID": self.user.id},
        namespace="dev",
    )
    vars = k.template_vars()
    assert vars == {
        "UID": 12,
        "env": {"TEST": "Test\nKubeTemplateSpawner"},
        "escaped_servername": "x---7d589dfd",
        "escaped_user_server": "user-1---751ab4e2--x---7d589dfd",
        "escaped_username": "user-1---751ab4e2",
        "ip": "0.0.0.0",
        "namespace": "dev",
        "port": 8888,
        "unescaped_servername": "- +",
        "unescaped_username": "user-1@🐧",
        "userid": 12,
    }


async def test_manifests():
    k = mock_spawner(
        "user-1@🐧", "", "dev", extra_vars=lambda self: {"UID": self.user.id}
    )
    ms = await k.manifests()
    assert len(ms) == 2

    if ms[0]["kind"] == "PersistentVolumeClaim":
        pvc = ms[0]
        pod = ms[1]
    else:
        pvc = ms[1]
        pod = ms[0]

    RESOURCES_DIR = ROOT_DIR / "tests" / "resources"
    with (RESOURCES_DIR / "pvc.yaml").open() as f:
        expected_pvc = yaml.unsafe_load(f)
    with (RESOURCES_DIR / "pod.yaml").open() as f:
        expected_pod = yaml.unsafe_load(f)
    assert pvc == expected_pvc
    assert pod == expected_pod


@pytest.mark.parametrize(
    "resource, expected",
    [
        ({"kind": "Pod", "status": {"podIP": "1.2.3.4"}}, ("1.2.3.4", 54321)),
        (
            {"kind": "Service", "metadata": {"name": "user-1", "namespace": "default"}},
            ("user-1.default", 54321),
        ),
    ],
    ids=["pod", "service"],
)
async def test_get_connection(resource, expected):
    k = mock_spawner(port=54321)
    c = k.get_connection(ResourceInstance(None, resource))
    assert c == expected


async def test_start(mocker):
    delete_manifest = mocker.patch("kubetemplatespawner.spawner.delete_manifest")
    deploy_manifest = mocker.patch("kubetemplatespawner.spawner.deploy_manifest")

    get_resource = mocker.patch(
        "kubetemplatespawner.spawner.get_resource",
        return_value=ResourceInstance(
            None, {"kind": "Pod", "status": {"podIP": "1.2.3.4"}}
        ),
    )

    k = mock_spawner()
    url = await k.start()
    assert url == "http://1.2.3.4:8888"

    assert not delete_manifest.called

    assert len(get_resource.call_args_list) == 1
    assert get_resource.call_args_list[0].args[1:] == (
        "v1",
        "Pod",
        "jupyter-user-1",
        "default",
    )

    assert len(deploy_manifest.call_args_list) == 2
    deploy1 = deploy_manifest.call_args_list[0].args[1]
    deploy2 = deploy_manifest.call_args_list[1].args[1]
    if deploy1["kind"] != "Pod":
        deploy1, deploy2 = deploy2, deploy1

    assert deploy1["kind"] == "Pod"
    assert deploy1["metadata"]["name"] == "jupyter-user-1"
    assert deploy2["kind"] == "PersistentVolumeClaim"
    assert deploy2["metadata"]["name"] == "jupyter-user-1"


async def test_stop(mocker):
    delete_manifest = mocker.patch("kubetemplatespawner.spawner.delete_manifest")
    deploy_manifest = mocker.patch("kubetemplatespawner.spawner.deploy_manifest")
    get_resource = mocker.patch("kubetemplatespawner.spawner.get_resource")

    k = mock_spawner()
    await k.stop()

    assert not deploy_manifest.called
    assert not get_resource.called

    assert len(delete_manifest.call_args_list) == 2
    delete1 = delete_manifest.call_args_list[0].args[1]
    delete2 = delete_manifest.call_args_list[1].args[1]
    if delete1["kind"] != "Pod":
        delete1, delete2 = delete2, delete1

    assert delete1["kind"] == "Pod"
    assert delete1["metadata"]["name"] == "jupyter-user-1"
    assert delete2["kind"] == "PersistentVolumeClaim"
    assert delete2["metadata"]["name"] == "jupyter-user-1"

    assert len(delete_manifest.call_args_list) == 2

    assert delete_manifest.call_args_list[0].args[2] == {
        "kubetemplatespawner/delete": "server"
    }
    assert delete_manifest.call_args_list[1].args[2] == {
        "kubetemplatespawner/delete": "server"
    }
