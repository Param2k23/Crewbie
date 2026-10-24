"""Package tests: isolated installation, schema, boundaries and sandbox footprint."""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from integrations.cubbie.validate_skill import validate_skill

SKILL = Path(__file__).resolve().parents[2] / "skills/campus-pulse"


class SkillPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / "campus-pulse"
        shutil.copytree(SKILL, self.folder)

    def change(self, before, after):
        path = self.folder / "SKILL.md"
        path.write_text(path.read_text(encoding="utf-8").replace(before, after), encoding="utf-8")

    def test_isolated_package_without_network(self):
        with patch("socket.socket", side_effect=AssertionError("Network forbidden")):
            result = validate_skill(self.folder)
        self.assertEqual(result["name"], "campus-pulse")
        self.assertEqual(result["files"], 1)
        self.assertFalse(result["scripts"])
        self.assertFalse(result["manifest"])
        self.assertEqual(result["runtime"], "UNVERIFIED")

    def test_invalid_frontmatter_rejected(self):
        self.change("name: campus-pulse", "name: ../campus-pulse")
        with self.assertRaises(ValueError):
            validate_skill(self.folder)

    def test_malformed_description_rejected(self):
        self.change('description: "', 'description: ["')
        with self.assertRaises(ValueError):
            validate_skill(self.folder)

    def test_manifest_requires_explicit_review(self):
        (self.folder / "cubbie.yaml").write_text("cubbie: 1\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            validate_skill(self.folder)

    def test_external_path_rejected(self):
        with (self.folder / "SKILL.md").open("a", encoding="utf-8") as stream:
            stream.write("\nRead [backend](../../integrations/cubbie/core.py).\n")
        with self.assertRaises(ValueError):
            validate_skill(self.folder)

    def test_oversized_package_rejected(self):
        with (self.folder / "SKILL.md").open("a", encoding="utf-8") as stream:
            stream.write("x" * (1024 * 1024))
        with self.assertRaises(ValueError):
            validate_skill(self.folder)


if __name__ == "__main__":
    unittest.main()
