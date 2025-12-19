from __future__ import annotations

import os
import stat
import subprocess
import textwrap
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_verify_devcontainer_script_exists_and_is_executable() -> None:
    script = _repo_root() / "scripts" / "verify-devcontainer.sh"
    assert script.exists(), "Missing scripts/verify-devcontainer.sh"
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, "scripts/verify-devcontainer.sh must be executable"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_verify_devcontainer_script_passes_with_fake_tools(tmp_path: Path) -> None:
    repo_root = tmp_path
    (repo_root / "backend").mkdir()
    (repo_root / "frontend").mkdir()
    (repo_root / ".devcontainer").mkdir()

    # Marker written by postCreateCommand wrapper.
    (repo_root / ".devcontainer" / ".post-create.status").write_text("0\n", encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    _write_executable(
        fake_bin / "python",
        "#!/usr/bin/env sh\n"
        'echo "Python 3.14.2"\n',
    )
    _write_executable(
        fake_bin / "node",
        "#!/usr/bin/env sh\n"
        'echo "v22.12.0"\n',
    )
    _write_executable(
        fake_bin / "pip",
        "#!/usr/bin/env sh\n"
        "cat <<'EOF'\n"
        "Package    Version\n"
        "---------- -------\n"
        "fastapi    0.115.6\n"
        "pydantic   2.10.4\n"
        "uvicorn    0.27.1\n"
        "EOF\n",
    )
    _write_executable(
        fake_bin / "npm",
        "#!/usr/bin/env sh\n"
        "if [ \"$1\" = \"list\" ]; then\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
    )
    _write_executable(
        fake_bin / "code",
        "#!/usr/bin/env sh\n"
        "if [ \"$1\" = \"--list-extensions\" ]; then\n"
        "  cat <<'EOF'\n"
        "ms-python.python\n"
        "ms-python.vscode-pylance\n"
        "charliermarsh.ruff\n"
        "dbaeumer.vscode-eslint\n"
        "esbenp.prettier-vscode\n"
        "bradlc.vscode-tailwindcss\n"
        "EOF\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
    )

    script_under_test = _repo_root() / "scripts" / "verify-devcontainer.sh"
    assert script_under_test.exists(), "Missing scripts/verify-devcontainer.sh in repo"

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH','')}"

    env["VERIFY_DEVCONTAINER_SKIP_EXTENSIONS"] = "1"

    result = subprocess.run(
        ["bash", str(script_under_test)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, textwrap.dedent(
        f"""
        Expected success but got exit code {result.returncode}
        --- stdout ---
        {result.stdout}
        --- stderr ---
        {result.stderr}
        """
    )


def test_verify_devcontainer_script_fails_on_wrong_python_version(tmp_path: Path) -> None:
    repo_root = tmp_path
    (repo_root / "backend").mkdir()
    (repo_root / "frontend").mkdir()
    (repo_root / ".devcontainer").mkdir()
    (repo_root / ".devcontainer" / ".post-create.status").write_text("0\n", encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    _write_executable(
        fake_bin / "python",
        "#!/usr/bin/env sh\n"
        'echo "Python 3.13.9"\n',
    )
    _write_executable(
        fake_bin / "node",
        "#!/usr/bin/env sh\n"
        'echo "v22.12.0"\n',
    )
    _write_executable(
        fake_bin / "pip",
        "#!/usr/bin/env sh\n"
        "cat <<'EOF'\n"
        "Package    Version\n"
        "---------- -------\n"
        "fastapi    0.115.6\n"
        "pydantic   2.10.4\n"
        "uvicorn    0.27.1\n"
        "EOF\n",
    )
    _write_executable(
        fake_bin / "npm",
        "#!/usr/bin/env sh\n"
        "exit 0\n",
    )
    _write_executable(
        fake_bin / "code",
        "#!/usr/bin/env sh\n"
        "exit 0\n",
    )

    script_under_test = _repo_root() / "scripts" / "verify-devcontainer.sh"

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH','')}"

    result = subprocess.run(
        ["bash", str(script_under_test)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Python 3.14" in (result.stdout + result.stderr)
