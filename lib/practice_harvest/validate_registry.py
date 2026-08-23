"""Sealed-валидатор реестра синтеза (фаза B). Держит интерпретативный выход
детерминированной схемой + проверкой существования source-path + coverage-гейтом."""
from __future__ import annotations

import json
import sys
from pathlib import Path

TRACKS = {"process", "technical"}
INDEP = {"high", "medium", "low"}
SIMPLE_VERDICTS = {"new-standard", "skip", "deferred:code", "deferred:skill"}


class ValidationError(Exception):
    pass


def _valid_verdict(v: str) -> bool:
    if v in SIMPLE_VERDICTS:
        return True
    return v.startswith("append:") and len(v.split(":", 1)[1].strip()) > 0


def validate_finding(f: dict) -> None:
    req = ["practice", "track", "lineage_sources", "recurrence",
           "domain_independence", "current_location", "lift_verdict", "source_paths"]
    for k in req:
        if k not in f:
            raise ValidationError(f"missing field: {k}")
    if f["track"] not in TRACKS:
        raise ValidationError(f"bad track: {f['track']}")
    if f["domain_independence"] not in INDEP:
        raise ValidationError(f"bad domain_independence: {f['domain_independence']}")
    if not _valid_verdict(f["lift_verdict"]):
        raise ValidationError(f"bad lift_verdict: {f['lift_verdict']}")
    if not isinstance(f["recurrence"], int) or f["recurrence"] < 1:
        raise ValidationError(f"bad recurrence: {f['recurrence']}")
    if not f["lineage_sources"]:
        raise ValidationError("lineage_sources empty")
    # recurrence ДОЛЖЕН равняться числу уникальных lineage (спец §3: source-diversity).
    # Без этого метрика может врать и пройти гейт (codex plan-gate P1).
    if f["recurrence"] != len(set(f["lineage_sources"])):
        raise ValidationError(
            f"recurrence {f['recurrence']} != unique lineage_sources "
            f"{len(set(f['lineage_sources']))}")
    if not f["source_paths"]:
        raise ValidationError("source_paths empty")
    for sp in f["source_paths"]:
        if not Path(sp).exists():
            raise ValidationError(f"source_path missing on disk: {sp}")


def validate_coverage(registry: dict, corpus: dict) -> None:
    """Гейт полноты синтеза: каждый lineage корпуса должен быть либо в
    каком-то finding.lineage_sources, либо явно в registry.examined_no_lift.
    Превращает «я посмотрел везде» в проверяемое свойство — форм-валидатор
    один этого не ловит (advisor 2026-07-10)."""
    corpus_lineages = set(corpus.get("lineage_counts", {}))
    covered: set[str] = set(registry.get("examined_no_lift", []))
    for f in registry.get("findings", []):
        covered.update(f.get("lineage_sources", []))
    missing = corpus_lineages - covered
    if missing:
        raise ValidationError(
            f"coverage gap — lineages neither lifted nor examined_no_lift: "
            f"{sorted(missing)}")


def validate_registry(path: str, corpus_path: str | None = None) -> int:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    findings = data["findings"] if isinstance(data, dict) else data
    for i, f in enumerate(findings):
        try:
            validate_finding(f)
        except ValidationError as e:
            print(f"FAIL finding[{i}] ({f.get('practice','?')}): {e}")
            return 1
    if corpus_path:
        corpus = json.loads(Path(corpus_path).read_text(encoding="utf-8"))
        try:
            validate_coverage(data, corpus)
        except ValidationError as e:
            print(f"FAIL coverage: {e}")
            return 1
    print(f"PASS: {len(findings)} findings valid"
          + (" + coverage complete" if corpus_path else ""))
    return 0


if __name__ == "__main__":
    # usage: validate_registry <registry.json> [corpus.json]
    _corpus = sys.argv[2] if len(sys.argv) > 2 else None
    sys.exit(validate_registry(sys.argv[1], _corpus))
