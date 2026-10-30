import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from ui.AboutView import AboutView
from update_checker import CURRENT_VERSION


class AboutViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_version_and_links_are_the_fork(self):
        view = AboutView()
        view.show()
        labels = [label.text() for label in view.findChildren(QtWidgets.QLabel)]
        self.assertIn(f"Version {CURRENT_VERSION}", labels)
        buttons = {button.text(): button for button in view.findChildren(QtWidgets.QPushButton)}
        with mock.patch("ui.AboutView.webbrowser.open") as opened:
            buttons["View source"].click()
            buttons["See the latest release"].click()
        self.assertEqual(
            [call.args[0] for call in opened.call_args_list],
            [
                "https://github.com/bitgineer/WritingTools",
                "https://github.com/bitgineer/WritingTools/releases",
            ],
        )
        view.close()


if __name__ == "__main__":
    unittest.main()
