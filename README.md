# KubeTemplateSpawner

[![Build](https://github.com/manics/jupyterhub-kubetemplatespawner/actions/workflows/workflow.yml/badge.svg)](https://github.com/manics/jupyterhub-kubetemplatespawner/actions/workflows/workflow.yml)

**⚠️⚠️⚠️⚠️⚠️ Under development ⚠️⚠️⚠️⚠️⚠️**

The following template variables are available:

- `userid`
- `unescaped_username`
- `unescaped_servername`

# Escaped values (kubespawner 'safe' scheme)

- `escaped_username`
- `escaped_servername`
- `escaped_user_server`

## Connection annotation

- `kubetemplatespawner/connection=true`: One resource per server (either a pod or service) must have this annotation to indicate JupyterHub should use this resource to connect to the server

## Deletion annotations

- `kubetemplatespawner/delete=user`: Delete this resource when the user is deleted
- `kubetemplatespawner/delete=server`: Delete this resource when the user server is deleted
  Other values are currently ignored, e.g. `kubetemplatespawner/delete=never` can be used to make it clear you haven't forgotten to add the annotation

## Example

See [`z2jh.yaml`](z2jh.yaml)
