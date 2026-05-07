"""Pytest config for h2t-ops:research tests.

Registers custom markers so pytest does not emit PytestUnknownMarkWarning.
"""
from __future__ import annotations


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "optional: label for opt-in scenarios (e.g. real-trafilatura uplift). "
        "Currently still runs in baseline; reserve for future @skipif gating.",
    )
