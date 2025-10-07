"""Utility script to bootstrap dependencies and run Interview Copilot with one command.

Usage:
    python start.py

The script will:
- ensure a local virtual environment exists in .venv and install Python dependencies;
- install Node.js dependencies (npm workspaces);
- launch `npm run dev`, wiring the virtual environment so that Electron can reuse it
  to spawn the python_core process.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
PYTHON_REQUIREMENTS = PROJECT_ROOT / "app" / "python_core" / "requirements.txt"
NODE_MODULES = PROJECT_ROOT / "node_modules"


class SetupError(RuntimeError):
    """Raised when required tooling is missing."""


def log(message: str) -> None:
    print(f"[start] {message}")


def get_venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def ensure_virtualenv() -> Path:
    if not VENV_DIR.exists():
        log(f"creating virtual environment at {VENV_DIR}")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])

    python_exec = get_venv_python()
    if not python_exec.exists():
        raise SetupError("virtual environment is corrupted: python executable not found")

    log("updating pip")
    subprocess.check_call([str(python_exec), "-m", "pip", "install", "--upgrade", "pip"])

    log("installing python_core requirements")
    subprocess.check_call([str(python_exec), "-m", "pip", "install", "-r", str(PYTHON_REQUIREMENTS)])
    return python_exec


def ensure_node_dependencies() -> None:
    if shutil.which("npm") is None:
        raise SetupError("npm is not available in PATH. Please install Node.js >= 18.")

    if not NODE_MODULES.exists():
        log("installing npm dependencies (first run may take a while)")
    else:
        log("updating npm dependencies")

    subprocess.check_call(["npm", "install"], cwd=PROJECT_ROOT)


def check_python_version() -> None:
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 10):
        raise SetupError("Python 3.10 or newer is required.")


def detect_ollama() -> None:
    if shutil.which("ollama") is None:
        log("warning: Ollama is not in PATH. The application will not be able to generate hints.")


def launch_dev_server(python_exec: Path) -> int:
    env = os.environ.copy()
    venv_bin = python_exec.parent
    env["PATH"] = os.pathsep.join([str(venv_bin), env.get("PATH", "")])
    env["VIRTUAL_ENV"] = str(VENV_DIR)

    log("starting development environment (Ctrl+C to stop)")
    process = subprocess.Popen(["npm", "run", "dev"], cwd=PROJECT_ROOT, env=env)

    try:
        return process.wait()
    except KeyboardInterrupt:
        log("stopping...")
        send_signal = signal.SIGINT
        if os.name == "nt":
            send_signal = signal.CTRL_BREAK_EVENT  # type: ignore[attr-defined]
        process.send_signal(send_signal)
        return process.wait()


def main() -> int:
    try:
        check_python_version()
        python_exec = ensure_virtualenv()
        ensure_node_dependencies()
        detect_ollama()
        return_code = launch_dev_server(python_exec)
        log(f"npm run dev exited with code {return_code}")
        return return_code or 0
    except SetupError as error:
        log(f"setup error: {error}")
        return 1
    except subprocess.CalledProcessError as error:
        log(f"command failed with exit code {error.returncode}: {' '.join(error.cmd)}")
        return error.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
