import asyncio
import re
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import (
    Any,
    AsyncGenerator,
)

import yaml
from jupyterhub.spawner import Spawner
from kubernetes_asyncio.client import ApiClient
from kubernetes_asyncio.dynamic import DynamicClient

# from .slugs import multi_slug, safe_slug
from kubespawner.slugs import multi_slug, safe_slug
from traitlets import (
    Callable,
    Dict,
    Int,
    TraitError,
    Unicode,
    Union,
    default,
    validate,
)

from ._kubernetes import (
    ResourceInstance,
    YamlT,
    delete_manifest,
    deploy_manifest,
    get_resource,
    load_config,
    manifest_summary,
    stream_events,
)
from ._version import __version__

# alphanumeric chars, space, some punctuation
SERVER_NAME_PATTERN = r"^[\w \.\-\+_]*$"


class KubeTemplateException(Exception):
    def __init__(self, message: str):
        super().__init__(message)

    def __str__(self):
        return f"KubeTemplateException: {self.args[0]}"


class KubeTemplateSpawner(Spawner):
    template_path = Unicode(
        allow_none=False,
        config=True,
        help="Directory containing a Helm chart for the singleuser server.",
    )

    deletion_annotation_key = Unicode(
        "kubetemplatespawner/delete",
        config=True,
        help="Annotation key for the delete policy",
    )

    connection_annotation_key = Unicode(
        "kubetemplatespawner/connection",
        config=True,
        help="Annotation key for the resource used for connecting to server",
    )

    namespace = Unicode(config=True, help="Kubernetes namespace to spawn user pods in")

    @default("namespace")
    def _default_namespace(self):
        """
        Set namespace default to current namespace if running in a k8s cluster
        """
        p = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
        if p.exists():
            return p.read_text()
        return "default"

    @validate("template_path")
    def _validate_template_path(self, proposal):
        directory = proposal["value"]
        if not Path(directory).is_dir():
            raise TraitError("template_path must be a directory")
        if not len(list(Path(directory).glob("*.yaml"))):
            raise TraitError("No *.yaml files found in template_path")
        return directory

    extra_vars = Union(
        [Dict(), Callable()],
        default_value={},
        allow_none=True,
        config=True,
        help=(
            "Dictionary of additional parameters passed to template, or a callable "
            "`def extra_vars(spawner: Spawner) -> dict[str, Any]`"
        ),
    )

    k8s_timeout = Int(180, config=True, help="Kubernetes API timeout")

    # Override Spawner ip and port defaults
    @default("ip")
    def _default_ip(self):
        return "0.0.0.0"

    @default("port")
    def _default_port(self):
        return 8888

    # Server name is provided by the user, add some sanitisation
    @validate("orm_spawner")
    def _validate_orm_spawner(self, proposal):
        servername = proposal["value"].name
        if not re.match(SERVER_NAME_PATTERN, servername):
            raise TraitError(
                f"Invalid server name {servername}, must match {SERVER_NAME_PATTERN}"
            )
        return proposal["value"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Queue for Kubernetes events that are shown to the user
        # https://asyncio.readthedocs.io/en/latest/producer_consumer.html
        self.events = asyncio.Queue()

        self._manifests: list[dict[str, YamlT]] = []
        self._connection_manifest: dict[str, YamlT] | None = None
        load_config()

    async def _render_manifests(self, path: str, vars: dict[str, YamlT]) -> list[YamlT]:
        with NamedTemporaryFile(suffix=".yaml", mode="w") as values:
            self.log.debug(f"Rendering {path} with {vars}")
            yaml.dump(vars, values)
            cmd = ["helm", "template", path, "-f", values.name]
            self.log.info(f"Running command {cmd}")
            helm = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await helm.communicate()
            if helm.returncode != 0:
                raise RuntimeError(f"Templating failed: {stderr.decode()}")
            docs = yaml.safe_load_all(stdout)

        return [doc for doc in docs if doc]

    async def manifests(self) -> list[YamlT]:
        if self._manifests:
            self.log.info("Using cached manifests")
        else:
            vars = self.template_namespace()
            self._manifests = await self._render_manifests(self.template_path, vars)
        return self._manifests

    def get_names(self) -> dict[str, str]:
        raw_servername = self.name or ""

        _slug_max_length = 48

        if raw_servername:
            safe_servername = safe_slug(raw_servername, max_length=_slug_max_length)
        else:
            safe_servername = ""

        raw_username = self.user.name
        safe_username = safe_slug(raw_username, max_length=_slug_max_length)

        # compute safe_user_server = {username}--{servername}
        if (
            # double-escape if safe names are too long after join
            len(safe_username) + len(safe_servername) + 2 > _slug_max_length
        ):
            # need double-escape if there's a chance of collision
            safe_user_server = multi_slug(
                [raw_username, raw_servername], max_length=_slug_max_length
            )
        else:
            if raw_servername:
                safe_user_server = f"{safe_username}--{safe_servername}"
            else:
                safe_user_server = safe_username

        vars = dict(
            # Raw values
            userid=self.user.id,
            unescaped_username=self.user.name,
            unescaped_servername=raw_servername,
            # Escaped values (kubespawner 'safe' scheme)
            escaped_username=safe_username,
            escaped_servername=safe_servername,
            escaped_user_server=safe_user_server,
        )
        return vars

    async def deploy_all_manifests(self, dyn_client: DynamicClient) -> None:
        """Deploy all manifests concurrently"""
        now = datetime.now(UTC)
        # K8s only supports seconds precision
        # https://github.com/kubernetes/kubernetes/issues/81026
        now = now.replace(microsecond=0)

        manifests = await self.manifests()
        summaries = [manifest_summary(m) for m in manifests]
        self.log.info(f"Deploying manifests {summaries}")
        events = asyncio.create_task(
            stream_events(self.events, summaries, now, self.k8s_timeout)
        )

        try:
            async with asyncio.TaskGroup() as tg:
                for manifest in manifests:
                    tg.create_task(
                        deploy_manifest(dyn_client, manifest, self.k8s_timeout)
                    )
        except ExceptionGroup:
            self.log.exception("Deploy failed")
            raise
        finally:
            events.cancel()

        try:
            await events
        except asyncio.CancelledError:
            self.log.info(f"Cancelled: events({summaries})")

    async def delete_all_manifests(
        self, dyn_client: DynamicClient, annotations: dict[str, str]
    ) -> None:
        manifests = await self.manifests()
        summaries = [manifest_summary(m) for m in manifests]
        self.log.info(f"Deleting manifests {summaries}")

        try:
            async with asyncio.TaskGroup() as tg:
                for manifest in manifests:
                    tg.create_task(
                        delete_manifest(
                            dyn_client, manifest, annotations, self.k8s_timeout
                        )
                    )
        except ExceptionGroup:
            self.log.exception("Delete failed")
            raise

    def template_namespace(self) -> dict[str, YamlT]:
        d = super().template_namespace()
        d.update(self.get_names())
        d["namespace"] = self.namespace
        d["ip"] = self.ip
        self.port: int
        d["port"] = self.port
        d["env"] = self.get_env()
        if callable(self.extra_vars):
            d.update(self.extra_vars(self))
        else:
            d.update(self.extra_vars)
        return d

    def get_connection(self, obj: ResourceInstance) -> tuple[str, int]:
        if obj.kind == "Pod":
            ip = obj.status.podIP
        elif obj.kind == "Service":
            if not obj.metadata.name or not obj.metadata.namespace:
                raise RuntimeError(f"{obj.metadata.name=} {obj.metadata.namespace=}")
            ip = f"{obj.metadata.name}.{obj.metadata.namespace}"
        else:
            raise NotImplementedError(f"Unable to connect to {obj.kind}")
        return ip, self.port

    async def _get_connection_object(
        self, dyn_client: DynamicClient
    ) -> ResourceInstance:
        if not self._connection_manifest:
            for manifest in await self.manifests():
                k = (
                    manifest["metadata"]
                    .get("annotations")
                    .get(self.connection_annotation_key)
                )
                if k == "true":
                    if self._connection_manifest:
                        raise ValueError(
                            f"Multiple manifests with {self.connection_annotation_key}=true found"
                        )
                    self._connection_manifest = manifest

        m = manifest_summary(self._connection_manifest)
        obj = await get_resource(dyn_client, m.api_version, m.kind, m.name, m.namespace)
        return obj

    # JupyterHub Spawner

    @default("env_keep")
    def _env_keep_default(self) -> list:
        """Don't inherit any env from the parent process"""
        return []

    def load_state(self, state: dict) -> None:
        super().load_state(state)
        # TODO: Assert type of state.get("manifests")
        self._manifests = state.get("manifests")  # type: ignore[assignment]
        self._connection_manifest = state.get("connection_manifest")
        kubetemplatespawner_version = state.get("kubetemplatespawner_version")
        self.log.info(f"Loaded state {kubetemplatespawner_version=}")

    def get_state(self) -> Any:
        state = super().get_state()
        state["kubetemplatespawner_version"] = __version__
        if self._manifests:
            state["manifests"] = self._manifests
        if self._connection_manifest:
            state["connection_manifest"] = self._connection_manifest
        return state

    def clear_state(self) -> None:
        super().clear_state()
        self._manifests = []
        self._connection_manifest = None

    async def start(self) -> str:
        if not self.port:
            self.port = 8888

        async with ApiClient() as api:
            async with DynamicClient(api) as dyn_client:
                await self.deploy_all_manifests(dyn_client)
                connection_obj = await self._get_connection_object(dyn_client)
                if not connection_obj:
                    raise KubeTemplateException("Failed to get connection object")
                ip, port = self.get_connection(connection_obj)

        self.log.info(f"Started server on {ip}:{port}")
        self.events.put_nowait(None)
        proto = "http"
        if ":" in ip:
            ip = f"[{ip}]"
        return f"{proto}://{ip}:{port}"

    async def stop(self, now=False) -> None:
        # now=False: shutdown the server gracefully
        # now=True: terminate the server immediately (not implemented)
        async with ApiClient() as api:
            async with DynamicClient(api) as dyn_client:
                await self.delete_all_manifests(
                    dyn_client, {self.deletion_annotation_key: "server"}
                )

    async def delete_forever(self):
        # This is called when deleting a user, or when deleting a named server.
        # If this is a named server we should not delete user resources.

        # TODO: This doesn't yet delete named server resources with label
        # deletion_annotation_key=user
        # that don't match a default server manifest
        if self.name:
            # server resources should already be deleted in stop()
            self.log.warn(f"Ignoring delete_forever of named server {self.name}")
        else:
            async with ApiClient() as api:
                async with DynamicClient(api) as dyn_client:
                    await self.delete_all_manifests(
                        dyn_client, {self.deletion_annotation_key: "user"}
                    )

    async def poll(self) -> None | int:
        # None: single-user process is running.
        # Integer: not running, return exit status (0 if unknown)
        # Spawner not initialized: behave as not running (0).
        # Spawner not finished starting: behave as running (None)
        # May be called before start when state is loaded on Hub launch,
        #   if spawner not initialized via load_state or start: unknown (0)
        # If called while start is in progress (yielded): running (None)

        async with ApiClient() as api:
            async with DynamicClient(api) as dyn_client:
                try:
                    obj = await self._get_connection_object(dyn_client)
                    if not obj:
                        # clear state if the process is done
                        self.clear_state()
                        return 0
                    return None
                except RuntimeError:
                    self.log.exception("Failed to get server")
        # Probably not running
        self.clear_state()
        return 0

        # TODO: PodIP is not guaranteed to be fixed
        # https://github.com/kubernetes/kubernetes/issues/108281#issuecomment-1058503524
        # Update if necessary

    async def progress(self) -> AsyncGenerator[int, None]:
        """
        https://github.com/jupyterhub/jupyterhub/blob/5.2.1/jupyterhub/spawner.py#L1368
        """
        while True:
            event = await self.events.get()
            if event is None:
                break
            yield event
