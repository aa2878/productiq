#!/usr/bin/env python3
"""
ProductIQ CLI Wrapper for Claude Skill integration.
Delegates directly to src/cli.py.
"""
import sys
from pathlib import Path

# Resolve repository root
REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cli import main

if __name__ == "__main__":
    main()
