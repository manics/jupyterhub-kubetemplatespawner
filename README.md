# KubeTemplateSpawner

[![Build](https://github.com/manics/jupyterhub-kubetemplatespawner/actions/workflows/workflow.yml/badge.svg)](https://github.com/manics/jupyterhub-kubetemplatespawner/actions/workflows/workflow.yml)

**⚠️⚠️⚠️⚠️⚠️ Under development ⚠️⚠️⚠️⚠️⚠️**

A JupyterHub Kubernetes spawner that uses Kubernetes templates.

## How this works

This takes a set of parameterised Helm templates that deploy a JupyterHub singleuser server, then:

- creates a temporary Helm `values.yaml` file with JupyterHub template variables
- runs `helm template ...`
- deploys the templated manifests

### The following template variables are available

Raw user and server:

- `userid`
- `unescaped_username`
- `unescaped_servername`

Escaped user and server (based on the KubeSpawner _safe_ scheme):

- `escaped_username`
- `escaped_servername`
- `escaped_user_server`

Spawner variables:

- `instance`: Instance name to distinguish multiple JupyterHub deployments
- `namespace`: Kubernetes namespace
- `ip`: IP the server should listen on
- `port` Port the server should listen on
- `env`: Dictionary of `key: value` environment variables

Additional variables:

- Variables from `KubeTemplateSpawner.extra_vars` are included, and can override the above

## Labels

All resources must include an instance label to distinguish multiple deployments:

- `app.kubernetes.io/instance: {{ .Values.instance }}`

User resources must include:

- `hub.jupyter.org/username: "{{ .Values.escaped_username }}"`

User server resources (that aren't shared between default and named servers) must also include:

- `hub.jupyter.org/servername: "{{ .Values.escaped_servername }}"`

## Connection annotation:

- `kubetemplatespawner/connection=true`: One resource per server (either a pod or service) must have this annotation to indicate JupyterHub should use this resource to connect to the server

## Lifecycle/deletion

These control when resources are deleted.

- `kubetemplatespawner/lifecycle=user-deleted`: Delete this resource when the user is deleted, typically used for storage volumes
- `kubetemplatespawner/lifecycle=server-stopped`: Delete this resource when the user server is stopped, typically the default for most resources other than persistent storage
- `kubetemplatespawner/lifecycle=server-deleted`: Delete this resource when a named server is deleted, use this if a named server has a separate storage volume that doesn't need to be kept

Resources are deleted by matching all labels:

- `app.kubernetes.io/instance: {{ .Values.instance }}`
- `hub.jupyter.org/username: "{{ .Values.escaped_username }}"`
- `hub.jupyter.org/servername: "{{ .Values.escaped_servername }}"` (servers only)

## Example

https://github.com/manics/jupyterhub-kubetemplatespawner/tree/main/z2jh
