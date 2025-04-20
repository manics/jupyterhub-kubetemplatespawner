import os
from pathlib import Path
from uuid import uuid4

import pytest_asyncio
from kubernetes_asyncio import client, dynamic
from kubernetes_asyncio.config import load_kube_config

ROOT_DIR = Path(__file__).absolute().parent.parent


@pytest_asyncio.fixture(scope="module")
async def k8s_client():
    await load_kube_config()
    async with client.ApiClient() as api:
        yield api


@pytest_asyncio.fixture(scope="module")
async def k8s_dynclient(k8s_client):
    async with dynamic.DynamicClient(k8s_client) as dynclient:
        yield dynclient


@pytest_asyncio.fixture(scope="module")
async def k8s_namespace(k8s_client):
    namespace = os.getenv("PYTEST_K8S_NAMESPACE")
    if namespace:
        yield namespace
    else:
        namespace = "pytest-" + str(uuid4())
        v1 = client.CoreV1Api(k8s_client)
        await v1.create_namespace(
            client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
        )
        yield namespace
        await v1.delete_namespace(name=namespace)
