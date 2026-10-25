#!/usr/bin/env bash
# Copy .env.prod (local, never committed) to the instance as .env with mode 600.
# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
load_ops_env SSH_KEY_PATH SSH_USER ELASTIC_IP REMOTE_DIR
need scp "Install an OpenSSH client."

file="${ENV_PROD_FILE:-${REPO_ROOT}/.env.prod}"
[ -f "${file}" ] || die "missing ${file}. Copy docs/spec/env.prod.example to .env.prod and fill in the secrets."
if git -C "${REPO_ROOT}" ls-files --error-unmatch "${file}" >/dev/null 2>&1; then
    die ".env.prod is tracked by git. Run: git rm --cached .env.prod"
fi
if grep -q '<' "${file}"; then
    die ".env.prod still has <placeholders>. Fill in every value first."
fi
if command -v uv >/dev/null 2>&1; then
    # Names only; values are never printed.
    (cd "${REPO_ROOT}" && ENV_PROD_CHECK="${file}" uv run python - <<'PY'
import os
import sys
from pathlib import Path
from crewbie.config import collect_raw_values, startup_problems

problems = startup_problems(collect_raw_values(Path(os.environ["ENV_PROD_CHECK"]), {}))
for problem in problems:
    sys.stderr.write(f"  {problem}\n")
sys.exit(1 if problems else 0)
PY
    ) || die ".env.prod would not start in production. Fix the variables listed above."
else
    say "uv not found; skipping the local .env.prod check"
fi

say "Copying .env.prod to ${ELASTIC_IP}:${REMOTE_DIR}/.env"
scp -i "${SSH_KEY}" "${SSH_OPTS[@]}" "${file}" "${SSH_USER}@${ELASTIC_IP}:${REMOTE_DIR}/.env"
ssh_cmd "chmod 600 '${REMOTE_DIR}/.env'"
say "Done. Run scripts/ops/deploy.sh to apply it."
