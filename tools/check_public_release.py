"""Validate tracked public source without printing any matched secret values."""

import ast
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_DIRS = {
    "venv", ".venv", ".venv-dev", "__pycache__", "data", "logs", "backups",
    "uploads", "debug_html", "progress", "demo-output", ".pytest_cache", ".hypothesis",
}
FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".log", ".pem", ".key", ".p12", ".pfx", ".pyc"}
FORBIDDEN_FILES = {"config.json", "wecom_config.json", "telegram_config.json", "secret-scan.json"}
TOKEN_PATTERNS = {
    "telegram token": re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"),
    "wecom webhook": re.compile(r"qyapi\.weixin\.qq\.com/cgi-bin/webhook/send\?key=[a-fA-F0-9-]{32,}"),
    "github token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def main():
    os.chdir(ROOT)
    files = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    files = [name for name in files if name]
    if not files:
        raise SystemExit("No tracked files: run from a Git checkout with staged or committed source")
    errors = []
    python_count = 0
    for name in files:
        relative = PurePosixPath(name)
        path = ROOT / name
        if (any(part in FORBIDDEN_DIRS for part in relative.parts)
                or relative.suffix.lower() in FORBIDDEN_SUFFIXES
                or relative.name in FORBIDDEN_FILES
                or "cookies" in relative.name.lower()
                or (relative.name.startswith(".env") and relative.name != ".env.example")
                or name.startswith("docs/pdf/PDF/")):
            errors.append(f"Forbidden runtime file: {name}")
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue  # Screenshot and other non-text assets.
        except OSError as exc:
            errors.append(f"Cannot read {name}: {exc.__class__.__name__}")
            continue
        if "\0" in text:
            continue
        if path.suffix == ".py":
            try:
                ast.parse(text, filename=name)
                python_count += 1
            except SyntaxError as exc:
                errors.append(f"Syntax error: {name}:{exc.lineno}")
        for label, pattern in TOKEN_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"Potential {label}: {name} (value withheld)")

    try:
        from detect_secrets import SecretsCollection
        from detect_secrets.settings import default_settings
    except ImportError:
        raise SystemExit("Install requirements-dev.txt to enable the mandatory secret scan")
    secrets = SecretsCollection()
    with default_settings() as settings:
        # Never attempt remote credential verification during a source scan.
        settings.disable_filters("detect_secrets.filters.common.is_ignored_due_to_verification_policies")
        for name in files:
            secrets.scan_file(name)
    findings = secrets.json()
    for name, matches in findings.items():
        for match in matches:
            errors.append(f"detect-secrets: {name}:{match['line_number']} ({match['type']}; value withheld)")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"PUBLIC_SOURCE_OK: {len(files)} tracked files; {python_count} Python files parsed; 0 secret findings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
