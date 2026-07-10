"""Свернуть форки/worktree/переименования проектов к каноничному lineage.

Справочник ведётся вручную; ревьюится оператором до синтеза (спец §Boundaries).
Новый форк без записи здесь → риск инфляции recurrence.
"""
from __future__ import annotations

# canonical -> список variant-имён (директорий проектов / session-папок)
LINEAGE_MAP: dict[str, list[str]] = {
    "crypto-regime-spike": [
        "crypto-regime-spike-dmde",
        "crypto-regime-test",
    ],
    "h2t-skills": [
        "agent-skills",
        "h2t-skills-119-editorial-pilot",
        "h2t-skills-editorial-wireframe",
        "C--dev-h2t-skills",  # ~/.claude/projects/<slug>/memory bucket name
    ],
}

# обратный индекс variant -> canonical
_VARIANT_TO_CANON = {
    variant: canon
    for canon, variants in LINEAGE_MAP.items()
    for variant in variants
}


def canonical_lineage(name: str) -> str:
    """Вернуть каноничное имя lineage для проекта/пути.

    Сворачивает: worktree-подпути (берётся первый сегмент до '/'),
    известные варианты форков, иначе passthrough.
    """
    head = name.replace("\\", "/").split("/", 1)[0].strip()
    return _VARIANT_TO_CANON.get(head, head)
