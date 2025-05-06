from time import sleep

import pytest
import requests


@pytest.mark.z2jh
def test_z2jh(jupyterhub_host):
    username = "test"

    s = requests.Session()
    # This should initialise the XSRF cookie
    r = s.get(f"{jupyterhub_host}hub/login")
    r.raise_for_status()

    # Login
    r = s.post(
        f"{jupyterhub_host}hub/login",
        data={"username": username, "password": "", "_xsrf": s.cookies["_xsrf"]},
    )
    r.raise_for_status()

    r = s.get(f"{jupyterhub_host}hub/spawn/{username}")
    r.raise_for_status()
    for _ in range(60):
        if r.url == f"{jupyterhub_host}hub/spawn-pending/{username}":
            assert "<p>Your server is starting up.</p>" in r.text
            sleep(2)
        else:
            break
        r = s.get(f"{jupyterhub_host}hub/spawn-pending/{username}")

    # Either started, or timedout
    assert r.url == f"{jupyterhub_host}user/{username}/lab"
    assert "<title>JupyterLab</title>" in r.text
