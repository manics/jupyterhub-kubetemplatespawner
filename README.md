# KubeTemplateSpawner

[![Build](https://github.com/manics/jupyterhub-kubetemplatespawner/actions/workflows/workflow.yml/badge.svg)](https://github.com/manics/jupyterhub-kubetemplatespawner/actions/workflows/workflow.yml)

**⚠️⚠️⚠️⚠️⚠️ Under development ⚠️⚠️⚠️⚠️⚠️**

A JupyterHub Kubernetes spawner that uses Kubernetes templates.

## How this works

This takes a set of parameterised Helm templates that deploy a JupyterHub singleuser server, then:

- creates a temporary Helm `values.yaml` file with JupyterHub variables (e.g. user and server name)
- runs `helm template ...`
- deploys the templated manifests

The following template variables are available:

Raw user and server:

- `userid`
- `unescaped_username`
- `unescaped_servername`

Escaped user and server (based on the KubeSpawner _safe_ scheme):

- `escaped_username`
- `escaped_servername`
- `escaped_user_server`

Runtime variables:

- `namespace`: Kubernetes namespace
- `ip`: IP the server should listen on
- `port` Port the server should listen on
- `env`: Dictionary of `key: value` environment variables

Additional variables:

- Variables from `KubeTemplateSpawner.extra_vars` are included, and can override the above

## Annotations

Connection `kubetemplatespawner/connection`:

- `kubetemplatespawner/connection=true`: One resource per server (either a pod or service) must have this annotation to indicate JupyterHub should use this resource to connect to the server

Deletion `kubetemplatespawner/delete`:

- `kubetemplatespawner/delete=user`: Delete this resource when the user is deleted
- `kubetemplatespawner/delete=server`: Delete this resource when the user server is deleted
- Other values are currently ignored, e.g. `kubetemplatespawner/delete=never` can be used to make it clear you haven't forgotten to add the annotation

## Example

See [`z2jh.yaml`](z2jh.yaml)
