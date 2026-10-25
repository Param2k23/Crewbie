import ast
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY_ROOTS = {"legacy", "services", "integrations", "apps", "apps_chat_bot"}


def test_src_does_not_import_legacy() -> None:
    offenders = []
    for path in (ROOT / "src").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            offenders += [str(path) for name in names if name.split(".")[0] in LEGACY_ROOTS]
    assert offenders == []


def test_import_linter_contracts_hold() -> None:
    executable = shutil.which("lint-imports", path=str(Path(sys.executable).parent))
    assert executable, "import-linter is not installed"
    result = subprocess.run([executable], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
