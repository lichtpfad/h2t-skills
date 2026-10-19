"""Layout 1, phase verify on a new user's home (#548 §8 «Новый пользователь», plan R25)."""
from __future__ import annotations

from h2t_ops.core import paths
from h2t_ops.setup.layout import engine, verify
from h2t_ops.setup.layout import journal as journal_mod
from h2t_ops.setup.layout.journal import Journal
from h2t_ops.setup.sync import Report


def test_empty_home_verifies_clean():
    assert not (paths.root() / "secrets").exists()
    assert not any(paths.legacy(n).exists() for n in paths.LEGACY if n != "downloads")
    j = Journal(journal_mod.new_run_id())
    assert verify.verify_secrets(j) == []
    assert verify.verify_copies(j) == []
    assert verify.verify_transformed(j) == []
    verify.phase_verify(engine.PhaseContext(journal=j, machine="m", machine_explicit=False,
                                            report=Report()))
    assert not paths.secrets_shared().exists()
