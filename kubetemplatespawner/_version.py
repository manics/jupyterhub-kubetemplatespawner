# https://setuptools-scm.readthedocs.io/en/v8.2.1/usage/#python-metadata
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("kubetemplatespawner")
except PackageNotFoundError:
    __version__ = "UNKNOWN"
