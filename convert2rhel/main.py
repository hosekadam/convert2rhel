__metaclass__ = type

import logging
import os

from convert2rhel import backup, cert
from convert2rhel import logger as logger_module
from convert2rhel import pkghandler, pkgmanager, repo, subscription, systeminfo, toolopts, utils
from convert2rhel.systeminfo import system_info


loggerinst = logging.getLogger(__name__)

_REDHAT_CDN_CACERT_SOURCE_DIR = utils.DATA_DIR
_REDHAT_CDN_CACERT_TARGET_DIR = "/etc/rhsm/ca/"

_RHSM_PRODUCT_CERT_SOURCE_DIR = os.path.join(utils.DATA_DIR, "rhel-certs")
_RHSM_PRODUCT_CERT_TARGET_DIR = "/etc/pki/product-default"


def main():
    initialize_logger("convert2rhel.log", logger_module.LOG_DIR)
    toolopts.CLI()
    prepare_system()
    gather_system_info()

    backup_repository()
    remove_excluded_pkgs()
    install_red_hat_gpg_keys()
    install_red_hat_cert_for_yum()
    pre_subscription()
    remove_repository_files_packages()
    subscribe_system()

    utils.run_subprocess(["yum", "swap", "centos-logos", "redhat-logos", "--releasever=7Server", "-y"])

    validate_transaction()


def prepare_system():
    """Setup the environment to do the conversion within"""
    loggerinst.task("Prepare: Clear YUM/DNF version locks")
    pkghandler.clear_versionlock()

    loggerinst.task("Prepare: Clean yum cache metadata")
    pkgmanager.clean_yum_metadata()


def initialize_logger(log_name, log_dir):
    """
    Entrypoint function that aggregates other calls for initialization logic
    and setup for logger handlers.

    .. warning::
        Setting log_dir underneath a world-writable directory (including
        letting it be user settable) is insecure.  We will need to write
        some checks for all calls to `os.makedirs()` if we allow changing
        log_dir.
    """

    try:
        logger_module.archive_old_logger_files(log_name, log_dir)
    except (IOError, OSError) as e:
        print("Warning: Unable to archive previous log: %s" % e)

    logger_module.setup_logger_handler(log_name, log_dir)


def gather_system_info():
    """Retrieve information about the system to be converted"""
    # gather system information
    loggerinst.task("Prepare: Gather system information")
    systeminfo.system_info.resolve_system_info()
    systeminfo.system_info.print_system_information()


def install_red_hat_gpg_keys():
    loggerinst.task("Convert: Import Red Hat GPG keys")
    pkghandler.install_gpg_keys()


def install_red_hat_cert_for_yum():
    loggerinst.task("Convert: Install cdn.redhat.com SSL CA certificate")
    repo_cert = cert.PEMCert(_REDHAT_CDN_CACERT_SOURCE_DIR, _REDHAT_CDN_CACERT_TARGET_DIR)
    backup.backup_control.push(repo_cert)


def remove_excluded_pkgs():
    loggerinst.task("Convert: Remove excluded packages")
    loggerinst.info("Searching for the following excluded packages:\n")
    try:
        pkgs_to_remove = sorted(pkghandler.get_packages_to_remove(system_info.excluded_pkgs))
        # this call can return None, which is not ideal to use with sorted.
        pkgs_removed = sorted(pkghandler.remove_pkgs_unless_from_redhat(pkgs_to_remove) or [])

        # TODO: Handling SystemExit here as way to speedup exception
        # handling and not refactor contents of the underlying function.
    except SystemExit as e:
        # TODO(r0x0d): Places where we raise SystemExit and need to be
        # changed to something more specific.
        #   - When we can't remove a package.
        return

    # shows which packages were not removed, if false, all packages were removed
    pkgs_not_removed = sorted(frozenset(pkghandler.get_pkg_nevras(pkgs_to_remove)).difference(pkgs_removed))
    if pkgs_not_removed:
        message = "The following packages were not removed: %s" % ", ".join(pkgs_not_removed)
        loggerinst.warning(message)

    else:
        message = "The following packages were removed: %s" % ", ".join(pkgs_removed)
        loggerinst.info(message)


def pre_subscription():
    if toolopts.tool_opts.no_rhsm:
        # Note: we don't use subscription.should_subscribe here because we
        # need the subscription-manager packages even if we don't subscribe
        # the system.  It's only if --no-rhsm is passed (so we rely on
        # user configured repos rather than system-manager configured repos
        # to get RHEL packages) that we do not need subscription-manager
        # packages.
        loggerinst.warning("Detected --no-rhsm option. Skipping.")
        return

    loggerinst.task("Convert: Subscription Manager - Check for installed packages")
    subscription_manager_pkgs = subscription.needed_subscription_manager_pkgs()
    if not subscription_manager_pkgs:
        loggerinst.info("Subscription Manager is already present")
    else:
        loggerinst.task("Convert: Subscription Manager - Install packages")
        # Hack for 1.4: if we install subscription-manager from the UBI repo, it
        # may require newer versions of packages than provided by the vendor.
        # (Note: the function is marked private because this is a hack
        # that should be replaced when we aren't under a release
        # deadline.
        update_pkgs = subscription._dependencies_to_update(subscription_manager_pkgs)
        backup.backup_control.push(backup.backup_control.partition)

        # Part of another hack for 1.4 that allows us to rollback part
        # of the backup control, then do old rollback items that
        # haven't been ported into the backup framework yet, and then
        # do the rest.
        # We need to do this here so that subscription-manager packages
        # that we install are uninstalled before other packages which
        # we may install during rollback.

        subscription.install_rhel_subscription_manager(subscription_manager_pkgs, update_pkgs)

    loggerinst.task("Convert: Subscription Manager - Verify installation")
    subscription.verify_rhsm_installed()

    loggerinst.task("Convert: Install a RHEL product certificate for RHSM")
    product_cert = cert.PEMCert(_RHSM_PRODUCT_CERT_SOURCE_DIR, _RHSM_PRODUCT_CERT_TARGET_DIR)
    backup.backup_control.push(product_cert)


def remove_repository_files_packages():
    """
    Remove those non-RHEL packages that contain YUM/DNF repofiles
    (/etc/yum.repos.d/*.repo) or affect variables in the repofiles (e.g.
    $releasever).

    Red Hat cannot automatically remove these non-RHEL packages with other
    excluded packages. While other excluded packages must be removed before
    installing subscription-manager to prevent package conflicts, these
    non-RHEL packages must be present on the system during
    subscription-manager installation so that the system can access and
    install subscription-manager dependencies. As a result, these non-RHEL
    packages must be manually removed after subscription-manager
    installation.
    """
    loggerinst.task("Convert: Remove packages containing .repo files")
    loggerinst.info("Searching for packages containing .repo files or affecting variables in the .repo files:\n")
    try:
        pkgs_to_remove = sorted(pkghandler.get_packages_to_remove(system_info.repofile_pkgs))
        # this call can return None, which is not ideal to use with sorted.
        pkgs_removed = sorted(pkghandler.remove_pkgs_unless_from_redhat(pkgs_to_remove) or [])

        # TODO: Handling SystemExit here as way to speedup exception
        # handling and not refactor contents of the underlying function.
    except SystemExit as e:
        # TODO(r0x0d): Places where we raise SystemExit and need to be
        # changed to something more specific.
        #   - When we can't remove a package.
        return

    # shows which packages were not removed, if false, all packages were removed
    pkgs_not_removed = sorted(frozenset(pkghandler.get_pkg_nevras(pkgs_to_remove)).difference(pkgs_removed))
    if pkgs_not_removed:
        message = "The following packages were not removed: %s" % ", ".join(pkgs_not_removed)
        loggerinst.warning(message)
    else:
        message = "The following packages were removed: %s" % ", ".join(pkgs_removed)
        loggerinst.info(message)


def subscribe_system():
    if not subscription.should_subscribe():
        if toolopts.tool_opts.no_rhsm:
            loggerinst.warning("Detected --no-rhsm option. Skipping subscription step.")
            return

        loggerinst.task("Convert: Subscription Manager - Reload configuration")
        # We will use subscription-manager later to enable the RHEL repos so we need to make
        # sure subscription-manager knows about the product certificate. Refreshing
        # subscription info will do that.
        try:
            subscription.refresh_subscription_info()
        except subscription.RefreshSubscriptionManagerError as e:
            if "not yet registered" in str(e):
                return
            raise

        loggerinst.warning("No rhsm credentials given to subscribe the system. Skipping the subscription step.")

        # In the future, refactor this to be an else on the previous
        # condition or a separate Action.  Not doing it now because we
        # have to disentangle the exception handling when we do that.
    if subscription.should_subscribe():
        loggerinst.task("Convert: Subscription Manager - Subscribe system")
        restorable_subscription = subscription.RestorableSystemSubscription()
        backup.backup_control.push(restorable_subscription)

    loggerinst.task("Convert: Get RHEL repository IDs")
    rhel_repoids = repo.get_rhel_repoids()

    loggerinst.task("Convert: Subscription Manager - Disable all repositories")
    subscription.disable_repos()

    # we need to enable repos after removing repofile pkgs, otherwise
    # we don't get backups to restore from on a rollback
    loggerinst.task("Convert: Subscription Manager - Enable RHEL repositories")
    subscription.enable_repos(rhel_repoids)


def validate_transaction():
    loggerinst.task("Prepare: Validate the %s transaction", pkgmanager.TYPE)
    transaction_handler = pkgmanager.create_transaction_handler()
    transaction_handler.run_transaction(
        validate_transaction=True,
    )


def backup_repository():
    loggerinst.task("Prepare: Backup Repository Files")
    repo.backup_yum_repos()
    repo.backup_varsdir()
