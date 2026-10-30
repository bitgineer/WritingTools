import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from WritingToolApp import WritingToolApp


class FakeProviderForm:
    def __init__(self):
        self.focused = 0

    def setFocus(self):
        self.focused += 1


class FakeSettings:
    def __init__(self):
        self.provider_form = FakeProviderForm()


class FakeShell:
    def __init__(self):
        self.settings = FakeSettings()


class FakeApp:
    def __init__(self, provider=None):
        self.current_provider = provider
        self.shell = FakeShell()
        self.destinations = []

    def show_dashboard(self, view=None):
        self.destinations.append(view)


class SettingsRoutingTests(unittest.TestCase):
    def test_settings_with_a_provider_is_a_shell_view(self):
        app = FakeApp(provider=object())
        WritingToolApp.show_settings(app)
        self.assertEqual(app.destinations, ["settings"])

    def test_settings_without_a_provider_returns_to_home_setup(self):
        app = FakeApp(provider=None)
        WritingToolApp.show_settings(app)
        self.assertEqual(app.destinations, ["home"])

    def test_providers_only_focuses_the_same_provider_form(self):
        app = FakeApp(provider=object())
        WritingToolApp.show_settings(app, providers_only=True)
        self.assertEqual(app.destinations, ["settings"])
        self.assertEqual(app.shell.settings.provider_form.focused, 1)


if __name__ == "__main__":
    unittest.main()
