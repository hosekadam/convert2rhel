import pytest


try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

from envparse import env


def test_yum_patch(convert2rhel, shell):
    shell("echo '#random text' >> /etc/yum.conf")

    with convert2rhel(
        ("-y --no-rpm-va --serverurl {} --username {} --password {} --pool {} --debug").format(
            env.str("RHSM_SERVER_URL"),
            env.str("RHSM_USERNAME"),
            env.str("RHSM_PASSWORD"),
            env.str("RHSM_POOL"),
        )
    ) as c2r:
        c2r.expect("/etc/yum.conf patched.")
    assert c2r.exitstatus == 0

    assert shell("yum update -y").returncode == 0
