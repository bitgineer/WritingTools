"""Integration contract for the one-window shell.

These tests bind the real WritingToolApp entry points to a stub host. They
pass only when WritingToolApp routes show_dashboard, show_history,
show_settings, and show_about to the shell and reuses one AppShell. They do
not touch the user's config or history database.
"""

import os
import sys
import unittest
from types import MethodType

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shell_fixtures import ShellTestCase

from PySide6 import QtWidgets

from WritingToolApp import WritingToolApp
from core.workflow import WorkflowController
from ui.AppShell import AppShell


class AppStub:
    def __init__(self):
        self.config = {"shortcut": "ctrl+space", "provider": "Gemini (Recommended)"}
        self.providers = []
        self.current_provider = None
        self.history_enabled = True
        self.paused = False
        self.workflow = WorkflowController()
        self.tray_icon = None
        self.shell = None
        self.dashboard_window = None
        self.history_window = None
        self.settings_window = None
        self.about_window = None
        self.onboarding_window = None
        self.startup_error = None
        self.calls = []

    def create_tray_icon(self):
        self.calls.append("create_tray_icon")

    def register_hotkey(self):
        self.calls.append("register_hotkey")

    def save_config(self, config=None):
        self.calls.append("save_config")

    def show_onboarding(self):
        self.calls.append("show_onboarding")

    def _history_config_changed(self, config):
        self.calls.append("history_config_changed")

    def _refresh_dashboard(self):
        self.calls.append("refresh_dashboard")

    def _abandon_setup(self):
        self.calls.append("abandon_setup")

    def provider_changed(self):
        self.calls.append("provider_changed")


class ShellIntegrationTests(ShellTestCase):
    def setUp(self):
        super().setUp()
        self.stub = AppStub()
        self.stub.providers = self.host.providers
        self.stub.current_provider = self.host.providers[0]
        self.stub.history_store = self.host.history_store
        for name in (
            "show_dashboard",
            "show_history",
            "show_settings",
            "show_about",
            "_ensure_shell",
        ):
            method = getattr(WritingToolApp, name, None)
            if method is not None:
                setattr(self.stub, name, MethodType(method, self.stub))

    def call(self, name, *args, **kwargs):
        method = getattr(self.stub, name, None)
        if method is None:
            self.fail(f"WritingToolApp.{name} is missing; the shell has no entry point for it")
        try:
            method(*args, **kwargs)
        except Exception as error:
            self.fail(f"{name} did not open the shell: {type(error).__name__}: {error}")
        QtWidgets.QApplication.processEvents()

    def assert_shell(self):
        self.assertIsInstance(
            self.stub.shell,
            AppShell,
            "the app must own one AppShell, not an old top-level window",
        )
        return self.stub.shell

    def test_repeated_show_dashboard_reuses_one_shell(self):
        self.call("show_dashboard")
        first = self.assert_shell()
        self.call("show_dashboard")
        second = self.assert_shell()

        self.assertIs(first, second, "show_dashboard must reuse the existing shell")
        self.assertIs(
            self.stub.dashboard_window,
            first,
            "dashboard_window is only an alias for the shell",
        )
        self.assertEqual(type(self.stub.dashboard_window).__name__, "AppShell")

    def test_show_history_navigates_the_shell(self):
        self.call("show_dashboard")
        shell = self.assert_shell()
        self.call("show_history")

        self.assertEqual(shell._current, "rewrites")
        self.assertIs(shell.stack.currentWidget(), shell.rewrites)
        self.assertIsNone(self.stub.history_window, "HistoryWindow must not be constructed")

    def test_show_settings_navigates_the_shell(self):
        self.call("show_dashboard")
        shell = self.assert_shell()
        self.call("show_settings")

        self.assertEqual(shell._current, "settings")
        self.assertIs(shell.stack.currentWidget(), shell.settings)
        self.assertIsNone(self.stub.settings_window, "SettingsWindow must not be constructed")

    def test_show_about_navigates_the_shell(self):
        self.call("show_dashboard")
        shell = self.assert_shell()
        self.call("show_about")

        self.assertEqual(shell._current, "about")
        self.assertIs(shell.stack.currentWidget(), shell.about)
        self.assertIsNone(self.stub.about_window, "AboutWindow must not be constructed")

    def test_show_settings_with_providers_only_focuses_the_provider_form(self):
        self.call("show_dashboard")
        shell = self.assert_shell()
        self.call("show_settings", True)

        self.assertEqual(shell._current, "settings")
        self.assertIsNone(self.stub.settings_window)


if __name__ == "__main__":
    unittest.main()
