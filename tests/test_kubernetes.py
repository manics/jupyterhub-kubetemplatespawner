from uuid import uuid4

import pytest
from kubernetes_asyncio import client
from kubernetes_asyncio.dynamic import ResourceInstance

from kubetemplatespawner._kubernetes import (
    delete_manifest,
    deploy_manifest,
    manifest_summary,
    not_found,
)

pytestmark = pytest.mark.asyncio(loop_scope="module")


def config_map(name="my-config", namespace="my-namespace", annotations=None):
    manifest = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": name, "namespace": namespace},
        "data": {"abc": "123", "def": "1\n2\n3"},
    }
    if annotations:
        manifest["metadata"]["annotations"] = annotations
    return manifest


async def test_manifest_summary():
    summary = manifest_summary(config_map())
    assert summary.api_version == "v1"
    assert summary.kind == "ConfigMap"
    assert summary.name == "my-config"
    assert summary.namespace == "my-namespace"


async def test_not_found(k8s_dynclient):
    assert not_found(None)
    assert not_found(ResourceInstance(None, {"kind": "Status", "code": 12345}))

    assert not not_found(
        ResourceInstance(
            None,
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
            },
        )
    )


# load_config()
# object_is_ready()
# k8s_resource()
# wait_for_ready()
# stream_events()


async def test_deploy_manifest(k8s_client, k8s_dynclient, k8s_namespace):
    v1 = client.CoreV1Api(k8s_client)

    name = f"config-{uuid4()}"
    m = config_map(name, k8s_namespace)
    await deploy_manifest(k8s_dynclient, m, 30)
    cm = await v1.read_namespaced_config_map(name, k8s_namespace)
    assert cm.data == m["data"]

    m["data"]["ghi"] = "false"
    await deploy_manifest(k8s_dynclient, m, 30)
    cm = await v1.read_namespaced_config_map(name, k8s_namespace)
    assert cm.data == m["data"]


async def test_delete_manifest(k8s_client, k8s_dynclient, k8s_namespace):
    v1 = client.CoreV1Api(k8s_client)
    name = f"config-{uuid4()}"

    async def list_cm_names():
        all_config_maps = await v1.list_namespaced_config_map(k8s_namespace)
        return sorted(
            [
                c.metadata.name
                for c in all_config_maps.items
                if c.metadata.name.startswith(name)
            ]
        )

    cm_names = [f"{name}-0", f"{name}-1", f"{name}-2"]

    m0 = config_map(cm_names[0], k8s_namespace)
    await v1.create_namespaced_config_map(k8s_namespace, m0)

    m1 = config_map(cm_names[1], k8s_namespace, {"custom.lifecycle": "delete1"})
    await v1.create_namespaced_config_map(k8s_namespace, m1)

    m2 = config_map(cm_names[2], k8s_namespace, {"custom.lifecycle": "delete2"})
    await v1.create_namespaced_config_map(k8s_namespace, m2)
    assert await list_cm_names() == cm_names

    # Nothing matches annotation
    for m in [m0, m1, m2]:
        await delete_manifest(k8s_dynclient, m, {"custom.lifecycle": "delete3"}, 30)
    assert await list_cm_names() == cm_names

    # Delete m1
    for m in [m0, m1, m2]:
        await delete_manifest(k8s_dynclient, m, {"custom.lifecycle": "delete1"}, 30)
    assert await list_cm_names() == [cm_names[0], cm_names[2]]

    # Delete m0, m2
    for m in [m0, m1, m2]:
        await delete_manifest(k8s_dynclient, m, {}, 30)
    assert not (await list_cm_names())


# get_resource()
