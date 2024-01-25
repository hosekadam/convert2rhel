import dnf

from convert2rhel.pkgmanager.handlers.dnf.callback import (
    DependencySolverProgressIndicatorCallback,
    PackageDownloadCallback,
    TransactionDisplayCallback,
)


base = dnf.Base()

# set up base
base.conf.substitutions["releasever"] = "8"
base.conf.module_platform_id = "platform:el" + "8"
base.conf.keepcache = True

# enable repos
base.repos.disableRepo("*")
base.repos.enableRepo("rhel-7-server-rpms")
base.repos.setProgressBar(PackageDownloadCallback())
can_update = base.update(pattern="httpd")
print(can_update)

# In test mode to not override the system
base.conf.tsflags.append("test")

# Process transaction and see what happens
base.processTransaction(rpmDisplay=TransactionDisplayCallback())