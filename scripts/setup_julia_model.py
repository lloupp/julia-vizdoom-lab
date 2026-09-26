#!/usr/bin/env python3
"""One-time setup: download SupersonicLabs/Julia-1 and install the julia package.

Usage:
    python scripts/setup_julia_model.py

Downloads the model repo (weights + the 'julia' python package source) into
models/Julia-1 (gitignored, ~613 MiB) and installs it editable so that
`from julia import load_model` works.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MODEL_REPO_ID = "SupersonicLabs/Julia-1"
MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "Julia-1"


def main() -> None:
    from huggingface_hub import snapshot_download

    MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {MODEL_REPO_ID} into {MODEL_DIR} ...")
    snapshot_download(MODEL_REPO_ID, local_dir=str(MODEL_DIR))

    print("Installing the 'julia' package (editable) ...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", str(MODEL_DIR)])

    print(f"Julia-1 ready at {MODEL_DIR}")


if __name__ == "__main__":
    main()
