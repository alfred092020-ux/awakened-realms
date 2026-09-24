from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ANDROID_NS = "http://schemas.android.com/apk/res/android"
APP_CATEGORY = f"{{{ANDROID_NS}}}appCategory"

ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = ROOT / "android/app/src/main/AndroidManifest.xml"


def load_application(path: Path):
    root = ET.parse(path).getroot()
    application = root.find("application")
    if application is None:
        raise AssertionError(f"missing <application> in {path}")
    return application


class AndroidGameCategoryTests(unittest.TestCase):
    def test_source_manifest_declares_game_category(self):
        application = load_application(SOURCE_MANIFEST)
        self.assertEqual("game", application.attrib.get(APP_CATEGORY))

    def test_game_category_is_declared_once_on_application(self):
        root = ET.parse(SOURCE_MANIFEST).getroot()
        applications = root.findall("application")
        self.assertEqual(1, len(applications))
        self.assertEqual("game", applications[0].attrib.get(APP_CATEGORY))


if __name__ == "__main__":
    unittest.main()
