#!/usr/bin/env python3
"""
Generate a lightweight deployment manifest with checksum + last_updated.
"""

import argparse
import hashlib
import json
from pathlib import Path


CRITICAL_PATHS = [
    "agent",
    "strategies_config",
    "deploy",
    "requirements.txt",
    "start.sh",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def iter_manifest_entries(root: Path) -> list[dict]:
    entries = []
    for rel in CRITICAL_PATHS:
        path = root / rel
        if path.is_dir():
            files = sorted(
                p for p in path.rglob("*")
                if p.is_file()
                and "__pycache__" not in p.parts
                and not p.name.endswith(".pyc")
            )
        elif path.exists():
            files = [path]
        else:
            continue
        for file_path in files:
            entries.append(
                {
                    "path": str(file_path.relative_to(root)),
                    "checksum": sha256_file(file_path),
                    "last_updated": file_path.stat().st_mtime,
                    "source": "repo",
                }
            )
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    manifest = {"root": str(root), "files": iter_manifest_entries(root)}
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
