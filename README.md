# KubeTemplateSpawner

[![GitHub Workflow](https://github.com/manics/jupyterhub-kubetemplatespawner/workflows/Build/badge.svg?branch=main&event=push)](https://github.com/manics/jupyterhub-kubetemplatespawner/actions)

The following template variables are available:

- userid
- unescaped_username
- unescaped_servername

# Escaped values (kubespawner 'safe' scheme)

- escaped_username
- escaped_servername
- escaped_user_server

## Connection annotation

- `kubetemplatespawner/connection=true`: One resource per server (either a pod or service) must have this annotation to indicate how JupyterHub should connect to the server

## Deletion annotations

- `kubetemplatespawner/delete=user`: Delete this resource when the user is deleted
- `kubetemplatespawner/delete=server`: Delete this resource when the user server is deleted
  Other values are currently ignored, e.g. `kubetemplatespawner/delete=never` can be used to make it clear you haven't forgotten to add the annotation
