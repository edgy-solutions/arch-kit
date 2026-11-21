"""The version string agrees with the changelog.

`arch_kit.__version__` is the package version `pip` reports. It must equal the newest numbered heading in
CHANGELOG.md (`## X.Y.Z (date)`), so a release that adds a changelog section also moves the version, and the
other way round.
"""
import re
import unittest
from pathlib import Path

import arch_kit

KIT = Path(__file__).resolve().parents[2]
HEADING = re.compile(r"^## (\d+\.\d+\.\d+) \(\d{4}-\d{2}-\d{2}\)$", re.M)


class Version(unittest.TestCase):
    def test_the_version_is_the_newest_changelog_release(self):
        found = HEADING.findall((KIT / "CHANGELOG.md").read_text(encoding="utf-8"))
        self.assertTrue(found, "CHANGELOG.md has no `## X.Y.Z (YYYY-MM-DD)` heading")
        self.assertEqual(arch_kit.__version__, found[0],
                         f"arch_kit.__version__ is {arch_kit.__version__}; the newest changelog release is {found[0]}")


if __name__ == "__main__":
    unittest.main()
