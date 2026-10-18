#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'USAGE'
Usage: install_aiops.sh --install-dir DIR [--python PYTHON]

The installer copies the current checkout into DIR, creates a virtual environment,
installs declared dependencies, and validates the deployment environment. It does
not provision upstream telemetry, databases, queues, model services, or operational records.

Options:
  --install-dir DIR   Required destination directory.
  --python PYTHON     Python executable to use; defaults to python3.
  --help              Show this message.
USAGE
}

INSTALL_DIR="${AIOPS_INSTALL_DIR:-}"
PYTHON_BIN="${AIOPS_PYTHON_BIN:-python3}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --install-dir)
            [[ $# -ge 2 ]] || { echo "--install-dir requires a value" >&2; exit 2; }
            INSTALL_DIR="$2"
            shift 2
            ;;
        --python)
            [[ $# -ge 2 ]] || { echo "--python requires a value" >&2; exit 2; }
            PYTHON_BIN="$2"
            shift 2
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

[[ -n "$INSTALL_DIR" ]] || { echo "An installation directory is required via --install-dir or AIOPS_INSTALL_DIR" >&2; exit 2; }
command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "Python executable not found: $PYTHON_BIN" >&2; exit 1; }
[[ -f requirements.txt ]] || { echo "Run this script from the repository root" >&2; exit 1; }

SOURCE_DIR="$(pwd -P)"
mkdir -p "$INSTALL_DIR"

if [[ "$SOURCE_DIR" != "$INSTALL_DIR" ]]; then
    tar --exclude='.git' --exclude='.venv' --exclude='__pycache__' -cf - . | tar -xf - -C "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"
"$PYTHON_BIN" -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [[ -z "${AIOPS_ENV:-}" || -z "${AIOPS_SERVICE_NAME:-}" || -z "${AIOPS_VERSION:-}" || -z "${AIOPS_HOST:-}" ]]; then
    echo "AIOPS_ENV, AIOPS_SERVICE_NAME, AIOPS_VERSION, and AIOPS_HOST must be supplied to validate configuration" >&2
    exit 1
fi

PYTHONPATH="$INSTALL_DIR" python -c 'from src.platform.config import Settings; Settings.from_env(); print("configuration valid")'
python -m compileall -q web_dashboard.py src

cat <<EOF
Installation completed.
Directory: $INSTALL_DIR
Virtual environment: $INSTALL_DIR/.venv
Start command: . $INSTALL_DIR/.venv/bin/activate && python $INSTALL_DIR/web_dashboard.py
Readiness requires a reachable configured upstream integration.
EOF
