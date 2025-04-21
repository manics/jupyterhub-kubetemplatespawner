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

Deletion `kubetemplatespawner/delete`:

- `kubetemplatespawner/delete=user`: Delete this resource when the user is deleted
- `kubetemplatespawner/delete=server`: Delete this resource when the user server is deleted
- Other values are currently ignored, e.g. `kubetemplatespawner/delete=never` can be used to make it clear you haven't forgotten to add the annotation

## Example

https://github.com/manics/jupyterhub-kubetemplatespawner/tree/main/z2jh
