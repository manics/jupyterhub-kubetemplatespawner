from uuid import uuid4

import pytest
from kubernetes_asyncio import client
from kubernetes_asyncio.dynamic import ResourceInstance

from kubetemplatespawner._kubernetes import (
    ManifestSummary,
    delete_manifest,
    deploy_manifest,
    get_resource_by_labels,
    get_resource_by_name,
    manifest_summary,
    not_found,
)

pytestmark = pytest.mark.asyncio(loop_scope="module")


def config_map(
    name="my-config", namespace="my-namespace", annotations=None, labels=None
):
    manifest = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": name, "namespace": namespace},
        "data": {"abc": "123", "def": "1\n2\n3"},
    }
    if annotations:
        manifest["metadata"]["annotations"] = annotations
    if labels:
        manifest["metadata"]["labels"] = labels
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


async def _list_cm_names(v1, namespace, prefix):
    all_config_maps = await v1.list_namespaced_config_map(namespace)
    return sorted(
        [
            c.metadata.name
            for c in all_config_maps.items
            if c.metadata.name.startswith(prefix)
        ]
    )


async def test_delete_manifest(k8s_client, k8s_dynclient, k8s_namespace):
    v1 = client.CoreV1Api(k8s_client)
    name = f"config-{uuid4()}"

    cm_names = [f"{name}-0", f"{name}-1", f"{name}-2"]

    m0 = config_map(cm_names[0], k8s_namespace)
    await v1.create_namespaced_config_map(k8s_namespace, m0)

    m1 = config_map(cm_names[1], k8s_namespace, {"custom.lifecycle": "delete1"})
    await v1.create_namespaced_config_map(k8s_namespace, m1)

    m2 = config_map(cm_names[2], k8s_namespace, {"custom.lifecycle": "delete2"})
    await v1.create_namespaced_config_map(k8s_namespace, m2)
    assert await _list_cm_names(v1, k8s_namespace, name) == cm_names

    # Nothing matches annotation
    for m in [m0, m1, m2]:
        await delete_manifest(k8s_dynclient, m, {"custom.lifecycle": "delete3"}, 30)
    assert await _list_cm_names(v1, k8s_namespace, name) == cm_names

    # Delete m1
    for m in [m0, m1, m2]:
        await delete_manifest(k8s_dynclient, m, {"custom.lifecycle": "delete1"}, 30)
    assert await _list_cm_names(v1, k8s_namespace, name) == [cm_names[0], cm_names[2]]

    # Delete m0, m2
    for m in [m0, m1, m2]:
        await delete_manifest(k8s_dynclient, m, {}, 30)
    assert not (await _list_cm_names(v1, k8s_namespace, name))


async def test_get_resource_by_name(k8s_client, k8s_dynclient, k8s_namespace):
    v1 = client.CoreV1Api(k8s_client)
    name = f"config-{uuid4()}"

    cm_names = [f"{name}-0", f"{name}-1"]
    for name in cm_names:
        m = config_map(name, k8s_namespace)
        await v1.create_namespaced_config_map(k8s_namespace, m)

    cm = await get_resource_by_name(
        k8s_dynclient, "v1", "ConfigMap", cm_names[0], k8s_namespace
    )
    assert manifest_summary(cm) == ManifestSummary(
        "v1", "ConfigMap", cm_names[0], k8s_namespace
    )

    cm = await get_resource_by_name(
        k8s_dynclient, "v1", "ConfigMap", f"{name}-2", k8s_namespace
    )
    assert cm is None

    cm = await get_resource_by_name(
        k8s_dynclient, "v1", "ConfigMap", f"{name}-1", f"non-existent-{k8s_namespace}"
    )
    assert cm is None


async def test_get_resource_by_labels(k8s_client, k8s_dynclient, k8s_namespace):
    v1 = client.CoreV1Api(k8s_client)
    uuid = uuid4()
    name = f"config-{uuid}"

    cm_names = [f"{name}-0", f"{name}-1", f"{name}-2", f"{name}-3"]

    m0 = config_map(cm_names[0], k8s_namespace, {}, {f"{uuid}/a": "1", f"{uuid}/b": ""})
    await v1.create_namespaced_config_map(k8s_namespace, m0)

    m1 = config_map(
        cm_names[1], k8s_namespace, {}, {f"{uuid}/a": "1", f"{uuid}/b": "2"}
    )
    await v1.create_namespaced_config_map(k8s_namespace, m1)

    m2 = config_map(cm_names[2], k8s_namespace, {}, {f"{uuid}/a": "1"})
    await v1.create_namespaced_config_map(k8s_namespace, m2)

    m3 = config_map(cm_names[3], k8s_namespace, {}, {f"{uuid}/a": "2"})
    await v1.create_namespaced_config_map(k8s_namespace, m3)

    cms = await get_resource_by_labels(
        k8s_dynclient, "v1", "ConfigMap", {f"{uuid}/a": "1"}, k8s_namespace
    )
    assert len(cms) == 3
    summaries = sorted(manifest_summary(cm) for cm in cms)
    assert summaries == [
        ManifestSummary("v1", "ConfigMap", name, k8s_namespace) for name in cm_names[:3]
    ]

    cms = await get_resource_by_labels(
        k8s_dynclient,
        "v1",
        "ConfigMap",
        {f"{uuid}/a": "1", f"{uuid}/b": ""},
        k8s_namespace,
    )
    assert len(cms) == 1
    assert manifest_summary(cms[0]) == ManifestSummary(
        "v1", "ConfigMap", cm_names[0], k8s_namespace
    )

    cms = await get_resource_by_labels(
        k8s_dynclient,
        "v1",
        "ConfigMap",
        {f"{uuid}/a": "1", f"{uuid}/b": "2"},
        k8s_namespace,
    )
    assert len(cms) == 1
    assert manifest_summary(cms[0]) == ManifestSummary(
        "v1", "ConfigMap", cm_names[1], k8s_namespace
    )

    cms = await get_resource_by_labels(
        k8s_dynclient,
        "v1",
        "ConfigMap",
        {f"{uuid}/a": "2", f"{uuid}/b": ""},
        k8s_namespace,
    )
    assert len(cms) == 0

    cms = await get_resource_by_labels(
        k8s_dynclient, "v1", "ConfigMap", {f"{uuid}/a": "2"}, k8s_namespace
    )
    assert len(cms) == 1
    assert manifest_summary(cms[0]) == ManifestSummary(
        "v1", "ConfigMap", cm_names[3], k8s_namespace
    )
