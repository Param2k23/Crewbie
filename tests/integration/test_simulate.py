import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/dev/simulate.py"


@pytest.mark.parametrize("seed", [1, 7, 42])
def test_phase_3_dod_simulation_of_50_intents_across_3_events_has_no_errors(seed: int) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--intents", "50", "--events", "3", "--seed", str(seed)],
        capture_output=True, text=True, timeout=120, check=False,
    )  # fmt: skip
    assert result.returncode == 0, result.stdout + result.stderr
    assert "room summary" in result.stdout and "OK: 50 intents" in result.stdout
    assert "PROBLEMS" not in result.stdout
