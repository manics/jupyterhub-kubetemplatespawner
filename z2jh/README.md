# Z2JH example

Edit the Z2JH configuration file [`config.yaml`](config.yaml) if you want, then deploy Z2JH:

```
helm upgrade --namespace dev --install jupyterhub --repo=https://hub.jupyter.org/helm-chart/ \
  --version=4.1.0 jupyterhub -f config.yaml --wait
```

After deploying Z2JH you must add an additional role [`hub-role.yaml`](hub-role.yaml) to the hub ServiceAccount:

```
kubectl --namespace dev apply -f hub-role.yaml
```
