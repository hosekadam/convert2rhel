# -*- coding: utf-8 -*-
#
# Copyright(C) 2016 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import os
import shutil
import unittest

import pytest
import six

from convert2rhel import unit_tests


six.add_move(six.MovedModule("mock", "mock", "unittest.mock"))
from six.moves import mock

from convert2rhel import cert, utils
from convert2rhel.systeminfo import system_info
from convert2rhel.toolopts import tool_opts


class TestCert(unittest.TestCase):

    # Certificates for all the supported RHEL variants
    certs = {
        "x86_64": {"6": "69.pem", "7": "69.pem", "8": "479.pem"},
        "ppc64": {
            "7": "74.pem",
        },
    }

    # Directory with all the tool data
    base_data_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), "../data/"))

    @unit_tests.mock(utils, "DATA_DIR", unit_tests.TMP_DIR)
    def test_get_cert_path(self):
        # Check there are certificates for all the supported RHEL variants
        for arch, rhel_versions in self.certs.items():
            for rhel_version, pem in rhel_versions.items():
                utils.DATA_DIR = os.path.join(self.base_data_dir, rhel_version, arch)
                system_cert = cert.SystemCert()
                cert_path = system_cert._source_cert_path
                self.assertEqual(cert_path, "{0}/rhel-certs/{1}".format(utils.DATA_DIR, pem))

    @unit_tests.mock(cert, "loggerinst", unit_tests.GetLoggerMocked())
    @unit_tests.mock(utils, "DATA_DIR", unit_tests.TMP_DIR)
    @unit_tests.mock(system_info, "arch", "arch")
    def test_get_cert_path_missing_cert(self):
        # Create temporary directory that has no certificate
        cert_dir = os.path.join(utils.DATA_DIR, "rhel-certs", system_info.arch)
        utils.mkdir_p(cert_dir)
        # Check response for the non-existing certificate in the temporary dir
        self.assertRaises(SystemExit, cert.SystemCert._get_cert)
        self.assertEqual(len(cert.loggerinst.critical_msgs), 1)
        # Remove the temporary directory tree
        shutil.rmtree(os.path.join(utils.DATA_DIR, "rhel-certs"))

    @unit_tests.mock(cert, "loggerinst", unit_tests.GetLoggerMocked())
    @unit_tests.mock(utils, "DATA_DIR", unit_tests.NONEXISTING_DIR)
    @unit_tests.mock(system_info, "arch", "nonexisting_arch")
    def test_get_cert_path_nonexisting_dir(self):
        self.assertRaises(SystemExit, cert.SystemCert._get_cert)
        self.assertEqual(len(cert.loggerinst.critical_msgs), 1)

    @unit_tests.mock(tool_opts, "arch", "x86_64")
    @unit_tests.mock(utils, "DATA_DIR", os.path.join(base_data_dir, "6", "x86_64"))
    def test_install_cert(self):
        # By initializing the cert object we get a path to an existing
        # certificate based on the mocked parameters above
        system_cert = cert.SystemCert()
        system_cert._target_cert_dir = unit_tests.TMP_DIR

        system_cert.install()

        installed_cert_path = os.path.join(system_cert._target_cert_dir, system_cert._cert_filename)
        self.assertTrue(os.path.exists(installed_cert_path))
        shutil.rmtree(unit_tests.TMP_DIR)


@pytest.mark.parametrize(
    (
        "create_file",
        "expected_text_in_logs",
    ),
    (
        (True, "/filename removed"),
        (False, "No such file or directory"),
    ),
)
def test_remove_cert(
    monkeypatch,
    create_file,
    expected_text_in_logs,
    caplog,
    tmpdir,
):
    tmp_file = tmpdir / "filename"
    if create_file:
        tmp_file.write(b"some content")

    monkeypatch.setattr(cert.SystemCert, "_get_cert", value=mock.Mock(return_value=("anything", "anything")))
    monkeypatch.setattr(cert.SystemCert, "_get_target_cert_path", value=mock.Mock(return_value=str(tmp_file)))

    sys_cert = cert.SystemCert()
    sys_cert.remove()
    assert expected_text_in_logs in caplog.messages[-1]
