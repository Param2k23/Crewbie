"""Smoke-test a running Crewbie server (local or deployed) the way a student would.

    uv run python scripts/dev/smoke.py --url https://crewbie.example.com

Checks /healthz, then runs crew.py as a throwaway student: register, link code, submit, accept
(which must stop at LINK_REQUIRED, proving the offer path and the linking rule). Finally it deletes
its own install. Finish AS-1/AS-2 by hand: run the printed `/crew link` command in Discord.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CREW = ROOT / "skills/crewbie-unlocks/scripts/crew.py"
SAMPLE = ROOT / "scripts/dev/sample_intent.py"


def fail(message: str) -> int:
    sys.stderr.write(f"FAIL {message}\n")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument(
        "--expect-discord", default=None, help="require this /healthz discord value"
    )
    args = parser.parse_args()
    base = args.url.rstrip("/")

    with urllib.request.urlopen(f"{base}/healthz", timeout=15) as response:
        health = json.load(response)
    print(f"healthz: {health}")
    if health.get("status") != "ok" or health.get("db") != "ok":
        return fail("server is not healthy")
    if args.expect_discord and health.get("discord") != args.expect_discord:
        return fail(f"discord is {health.get('discord')!r}, expected {args.expect_discord!r}")

    with tempfile.TemporaryDirectory() as home:
        env = {**os.environ, "HOME": home, "CREWBIE_API_URL": base}

        def crew(*cli: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [sys.executable, str(CREW), *cli],
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )

        intent = Path(home) / "intent.json"
        intent.write_text(subprocess.run(
            [sys.executable, str(SAMPLE)], capture_output=True, text=True, check=True
        ).stdout)  # fmt: skip

        steps = [("register", ["register"], 0), ("submit", ["submit", "--file", str(intent)], 0)]
        offer_id = ""
        for name, cli, expected in steps:
            result = crew(*cli)
            print(
                f"crew.py {name}: exit {result.returncode}\n  "
                + result.stdout.replace("\n", "\n  ")
            )
            if result.returncode != expected:
                return fail(f"crew.py {name} exited {result.returncode}: {result.stderr.strip()}")
            for line in result.stdout.splitlines():
                if line.startswith("OFFER "):
                    offer_id = line.split()[1]
        if not offer_id:
            return fail("no offer was returned")

        accept = crew("accept", "--offer", offer_id)
        print(f"crew.py accept: exit {accept.returncode}\n  " + accept.stdout.replace("\n", "\n  "))
        if accept.returncode != 2 or "LINK_CODE" not in accept.stdout:
            return fail("accept should stop at LINK_REQUIRED for an unlinked student")

        state = json.loads((Path(home) / ".config/crewbie/install.json").read_text())
        request = urllib.request.Request(
            f"{base}/v1/installs/me", method="DELETE",
            headers={"Authorization": f"Bearer {state['token']}"},
        )  # fmt: skip
        with urllib.request.urlopen(request, timeout=15) as deleted:
            print(f"cleanup: deleted the smoke-test install (HTTP {deleted.status})")
    print("\nOK: server healthy; register, submit and the link rule work end to end.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
