"""pytest config for kubetemplatespawner tests"""

from pathlib import Path

# from jupyterhub.tests.mocking import MockHub

ROOT_DIR = Path(__file__).absolute().parent.parent

# make Hub connectable by default
# MockHub.hub_ip = "0.0.0.0"


# https://docs.pytest.org/en/latest/example/parametrize.html#apply-indirect-on-particular-arguments
# @pytest.fixture
# async def app(request):
#     """
#     Mock a jupyterhub app for testing

#     Takes a parameter indicating the template directory
#     """
#     c = Config()
#     c.JupyterHub.spawner_class = KubeTemplateSpawner
#     # c.KubeTemplateSpawner.template_path = str(ROOT_DIR / "example")
#     # c.JupyterHub.hub_connect_ip = _get_host_default_ip()

#     mocked_app = MockHub.instance(config=c)

#     await mocked_app.initialize([])
#     await mocked_app.start()

#     try:
#         yield mocked_app
#     finally:
#         # disconnect logging during cleanup because pytest closes captured FDs
#         # prematurely
#         mocked_app.log.handlers = []
#         MockHub.clear_instance()
#         try:
#             mocked_app.stop()
#         except Exception as e:
#             print("Error stopping Hub: %s" % e, file=sys.stderr)
