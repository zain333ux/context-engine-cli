"""Generate a stress-test directory for context-engine."""

import os
import shutil
from pathlib import Path


ROOT = Path("test_env")


def reset_permissions(function, path, _exc_info) -> None:
    try:
        os.chmod(path, 0o700)
        function(path)
    except OSError:
        pass


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def make_restricted_file(path: Path) -> None:
    write_text(path, "This file is intended to be unreadable when the OS allows it.\n")
    try:
        os.chmod(path, 0)
    except OSError:
        pass


def main() -> None:
    if ROOT.exists():
        shutil.rmtree(ROOT, onerror=reset_permissions)

    deep_dir = ROOT / "level1" / "level2" / "level3" / "level4" / "level5" / "level6"
    write_text(deep_dir / "deep_file.py", "def deep_function():\n    return 'deep context'\n")
    write_text(ROOT / "README.md", "# Test Environment\n")
    write_text(ROOT / "Dockerfile", "FROM python:3.13-slim\n")
    write_text(ROOT / "no_extension", "This file intentionally has no extension.\n")
    write_text(ROOT / "scripts" / "run", "#!/usr/bin/env sh\necho running\n")
    write_bytes(ROOT / "fake_binary.txt", b"\xff\xfe\x00\x00not valid utf-8\x80\x81")
    make_restricted_file(ROOT / "restricted_read.txt")

    ignored_dir = ROOT / "node_modules"
    write_text(ignored_dir / "ignored.js", "console.log('ignored');\n")

    print(f"Created stress-test environment at: {ROOT.resolve()}")
    print("Run: python -m context_engine.main test_env -o test_env_context.txt")


if __name__ == "__main__":
    main()
