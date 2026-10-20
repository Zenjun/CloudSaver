"""Fail CI if project text contains common credential forms."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    re.compile("AK" + r"IA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?" + "PRIVATE KEY-----"),
    re.compile("gh" + r"[pousr]_[A-Za-z0-9_]{30,}"),
    re.compile("github" + r"_pat_[A-Za-z0-9_]{30,}"),
)


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    hits: list[str] = []
    for name in result.stdout.decode("utf-8").split("\0"):
        if not name:
            continue
        path = ROOT / name
        if path.is_symlink() or not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(pattern.search(content) for pattern in PATTERNS):
            hits.append(name)
    if hits:
        print("Credential-like text in project files: " + ", ".join(hits))
        return 1
    print("No credential markers found in project text files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
