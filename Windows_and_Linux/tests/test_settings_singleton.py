import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from WritingToolApp import WritingToolApp


class FakeSignal:
    def connect(self, slot):
        self.slot = slot


class FakeSettingsWindow:
    instances = []

    def __init__(self, app, providers_only=False):
        self.app = app
        self.providers_only = providers_only
        self.built_providers_only = providers_only
        self.close_signal = FakeSignal()
        self.visible = False
        self.closed = False
        FakeSettingsWindow.instances.append(self)

    def retranslate_ui(self):
        pass

    def show(self):
        self.visible = True

    def raise_(self):
        pass

    def activateWindow(self):
        pass

    def close(self):
        self.closed = True
        self.visible = False

    def deleteLater(self):
        pass


class FakeApp:
    def __init__(self):
        self.settings_window = None

    def _abandon_setup(self):
        pass

    def exit_app(self):
        pass


class SettingsSingletonTests(unittest.TestCase):
    def setUp(self):
        FakeSettingsWindow.instances.clear()
        self.app = FakeApp()

    def show(self, providers_only=False):
        with mock.patch(
            "ui.SettingsWindow.SettingsWindow", FakeSettingsWindow
        ):
            WritingToolApp.show_settings(self.app, providers_only=providers_only)

    def test_repeated_same_mode_reuses_the_window(self):
        self.show()
        self.show()
        self.assertEqual(len(FakeSettingsWindow.instances), 1)
        self.assertTrue(FakeSettingsWindow.instances[0].visible)

    def test_switching_mode_replaces_the_window(self):
        self.show()
        self.show(providers_only=True)
        self.assertEqual(len(FakeSettingsWindow.instances), 2)
        self.assertTrue(FakeSettingsWindow.instances[0].closed)
        self.assertTrue(FakeSettingsWindow.instances[1].visible)


if __name__ == "__main__":
    unittest.main()
