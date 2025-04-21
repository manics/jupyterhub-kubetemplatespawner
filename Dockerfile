FROM quay.io/jupyterhub/k8s-hub:4.1.0

USER root

ARG HELM_VERSION=3.17.3
RUN MACHINE=$(uname -m) && \
  if [ "$MACHINE" = aarch64 ]; then ARCH=arm64; else ARCH=amd64; fi && \
  curl -sfL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${ARCH}.tar.gz" | \
  tar -zx --strip-components=1 -C /usr/local/bin/ linux-${ARCH}/helm && \
  helm version 

COPY . /src/kubetemplatespawner
RUN python -mpip install -r /src/kubetemplatespawner/requirements.txt /src/kubetemplatespawner

USER jovyan
