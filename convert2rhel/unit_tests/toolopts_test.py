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

# Required imports:


import sys
import unittest

import pytest
import six

import convert2rhel.toolopts
import convert2rhel.utils

from convert2rhel import unit_tests  # Imports unit_tests/__init__.py
from convert2rhel.toolopts import tool_opts


six.add_move(six.MovedModule("mock", "mock", "unittest.mock"))
from six.moves import mock


def mock_cli_arguments(args):
    """Return a list of cli arguments where the first one is always the name of the executable, followed by 'args'."""
    return sys.argv[0:1] + args


class TestToolopts(unittest.TestCase):
    def setUp(self):
        tool_opts.__init__()

    @unit_tests.mock(sys, "argv", mock_cli_arguments(["--username", "uname"]))
    def test_cmdline_interactive_username_without_passwd(self):
        convert2rhel.toolopts.CLI()
        self.assertEqual(tool_opts.username, "uname")
        self.assertFalse(tool_opts.credentials_thru_cli)

    @unit_tests.mock(sys, "argv", mock_cli_arguments(["--password", "passwd"]))
    def test_cmdline_interactive_passwd_without_uname(self):
        convert2rhel.toolopts.CLI()
        self.assertEqual(tool_opts.password, "passwd")
        self.assertFalse(tool_opts.credentials_thru_cli)

    @unit_tests.mock(
        sys,
        "argv",
        mock_cli_arguments(["--username", "uname", "--password", "passwd"]),
    )
    def test_cmdline_non_ineractive_with_credentials(self):
        convert2rhel.toolopts.CLI()
        self.assertEqual(tool_opts.username, "uname")
        self.assertEqual(tool_opts.password, "passwd")
        self.assertTrue(tool_opts.credentials_thru_cli)

    @unit_tests.mock(sys, "argv", mock_cli_arguments(["--serverurl", "url"]))
    def test_custom_serverurl(self):
        convert2rhel.toolopts.CLI()
        self.assertEqual(tool_opts.serverurl, "url")

    @unit_tests.mock(sys, "argv", mock_cli_arguments(["--enablerepo", "foo"]))
    def test_cmdline_disablerepo_defaults_to_asterisk(self):
        convert2rhel.toolopts.CLI()
        self.assertEqual(tool_opts.enablerepo, ["foo"])
        self.assertEqual(tool_opts.disablerepo, ["*"])


@pytest.mark.parametrize(
    ("argv", "warn", "keep_rhsm_value"),
    (
        (mock_cli_arguments(["--keep-rhsm"]), False, True),
        (mock_cli_arguments(["--keep-rhsm", "--disable-submgr", "--enablerepo", "test_repo"]), True, False),
    ),
)
@mock.patch("convert2rhel.toolopts.tool_opts.keep_rhsm", False)
def test_keep_rhsm(argv, warn, keep_rhsm_value, monkeypatch, caplog):
    monkeypatch.setattr(sys, "argv", argv)
    convert2rhel.toolopts.CLI()
    if warn:
        assert "Ignoring the --keep-rhsm option" in caplog.text
    else:
        assert "Ignoring the --keep-rhsm option" not in caplog.text
    assert convert2rhel.toolopts.tool_opts.keep_rhsm == keep_rhsm_value


@pytest.mark.parametrize(
    ("argv", "warn", "ask_to_continue"),
    (
        (mock_cli_arguments(["-v", "Server"]), True, True),
        (mock_cli_arguments(["--variant", "Client"]), True, True),
        (mock_cli_arguments(["-v"]), True, True),
        (mock_cli_arguments(["--variant"]), True, True),
        (mock_cli_arguments(["--version"]), False, False),
        (mock_cli_arguments([]), False, False),
    ),
)
def test_cmdline_obsolete_variant_option(argv, warn, ask_to_continue, monkeypatch, caplog):
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(convert2rhel.utils, "ask_to_continue", mock.Mock())
    convert2rhel.toolopts.warn_on_unsupported_options()
    if warn:
        assert "variant option is not supported" in caplog.text
    else:
        assert "variant option is not supported" not in caplog.text
    if ask_to_continue:
        convert2rhel.utils.ask_to_continue.assert_called_once()
    else:
        convert2rhel.utils.ask_to_continue.assert_not_called()


@pytest.mark.parametrize(
    ("argv", "raise_exception", "no_rhsm_value"),
    (
        (mock_cli_arguments(["--disable-submgr"]), True, True),
        (mock_cli_arguments(["--no-rhsm"]), True, True),
        (mock_cli_arguments(["--disable-submgr", "--enablerepo", "test_repo"]), False, True),
        (mock_cli_arguments(["--no-rhsm", "--disable-submgr", "--enablerepo", "test_repo"]), False, True),
    ),
)
@mock.patch("convert2rhel.toolopts.tool_opts.no_rhsm", False)
@mock.patch("convert2rhel.toolopts.tool_opts.enablerepo", [])
def test_both_disable_submgr_and_no_rhsm_options_work(argv, raise_exception, no_rhsm_value, monkeypatch, caplog):
    monkeypatch.setattr(sys, "argv", argv)

    if raise_exception:
        with pytest.raises(SystemExit):
            convert2rhel.toolopts.CLI()
            assert "The --enablerepo option is required when --disable-submgr or --no-rhsm is used." in caplog.text
    else:
        convert2rhel.toolopts.CLI()

    assert convert2rhel.toolopts.tool_opts.no_rhsm == no_rhsm_value
