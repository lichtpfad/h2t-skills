"""Put the vendored lib on sys.path for its own tests.

The vendored modules import each other as top level (`from gather.briefing import ...`),
which works at runtime because every script that loads them inserts this directory into
sys.path first. Under pytest nothing does, so collection failed with
`ModuleNotFoundError: No module named 'gather'` and these tests never ran anywhere.

This file sits at `lib/`, not inside `lib/gather/`: tests/core/test_vendored_lib_parity.py
compares every non-test `.py` under lib/eval, lib/gather and lib/activity against the root
copy, and a conftest.py inside one of them would be flagged as having no counterpart.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
