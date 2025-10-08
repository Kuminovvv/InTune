"""Bootstrap script to run Interview Copilot entirely with Python UI."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
PYTHON_REQUIREMENTS = PROJECT_ROOT / "app" / "python_core" / "requirements.txt"


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

    log("installing project requirements")
    subprocess.check_call([str(python_exec), "-m", "pip", "install", "-r", str(PYTHON_REQUIREMENTS)])
    return python_exec


def check_python_version() -> None:
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 10):
        raise SetupError("Python 3.10 or newer is required.")


def detect_ollama() -> None:
    if shutil.which("ollama") is None:
        log("warning: Ollama is not in PATH. The application will not be able to generate hints.")


def launch_app(python_exec: Path) -> int:
    env = os.environ.copy()
    venv_bin = python_exec.parent
    env["PATH"] = os.pathsep.join([str(venv_bin), env.get("PATH", "")])
    env["VIRTUAL_ENV"] = str(VENV_DIR)

    log("starting Interview Copilot UI (Ctrl+C to stop)")
    process = subprocess.Popen([str(python_exec), "-m", "app.ui"], cwd=PROJECT_ROOT, env=env)
    try:
        return process.wait()
    except KeyboardInterrupt:
        log("stopping...")
        process.terminate()
        return process.wait()


def main() -> int:
    try:
        check_python_version()
        python_exec = ensure_virtualenv()
        detect_ollama()
        return_code = launch_app(python_exec)
        log(f"UI exited with code {return_code}")
        return return_code or 0
    except SetupError as error:
        log(f"setup error: {error}")
        return 1
    except subprocess.CalledProcessError as error:
        log(f"command failed with exit code {error.returncode}: {' '.join(error.cmd)}")
        return error.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
