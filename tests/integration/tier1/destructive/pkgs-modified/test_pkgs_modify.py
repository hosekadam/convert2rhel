import os

from envparse import env


def test_pkgs_modify(shell, convert2rhel, c2r_config):
    """
    Test the conversion with installed packages and modified configuration with
    excluded and swapped packages
    """

    pkgs_to_install = os.environ.get("PKGS_TO_INSTALL", "")
    pkgs_to_rm_from_excl_list = os.environ.get("PKGS_TO_RM_FROM_EXCL_LIST", "")
    pkgs_installed_after = os.environ.get("PKGS_INSTALLED_AFTER", "")

    config = c2r_config

    if pkgs_to_rm_from_excl_list:
        config.rm_from_config_file("excluded_pkgs", pkgs_to_rm_from_excl_list)

    # install problematic pkgs before conversion
    if pkgs_to_install:
        assert (
            shell(
                f"yum install -y {pkgs_to_install}",
            ).returncode
            == 0
        )

    # run utility until the reboot
    with convert2rhel(
        "-y --serverurl {} --username {} --password {} --pool {} --debug".format(
            env.str("RHSM_SERVER_URL"),
            env.str("RHSM_USERNAME"),
            env.str("RHSM_PASSWORD"),
            env.str("RHSM_POOL"),
        )
    ) as c2r:
        pass
    assert c2r.exitstatus == 0

    # check if pkgs are present after conversion
    for pkg in pkgs_installed_after.split():
        assert shell(f"rpm -qi {pkg}").returncode == 0
