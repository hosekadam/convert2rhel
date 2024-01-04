# Reproducer of httpd issue from Rodolfo Olivieri
# Install httpd on machine and the rpm -e --nodeps centos-logos

import yum

from convert2rhel.pkgmanager.handlers.yum.callback import PackageDownloadCallback, TransactionDisplayCallback


base = yum.YumBase()
base.conf.yumvar["releasever"] = "7Server"
base.repos.disableRepo("*")
base.repos.enableRepo("rhel-7-server-rpms")
base.repos.setProgressBar(PackageDownloadCallback())
can_update = base.update(pattern="httpd")
print(can_update)

# In test mode to not override the system
base.conf.tsflags.append("test")

# Process transaction and see what happens
base.processTransaction(rpmDisplay=TransactionDisplayCallback())
