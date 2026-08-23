from lib.practice_harvest.lineage import canonical_lineage


def test_crypto_variants_collapse():
    assert canonical_lineage("crypto-regime-spike-dmde") == "crypto-regime-spike"
    assert canonical_lineage("crypto-regime-test") == "crypto-regime-spike"
    assert canonical_lineage("crypto-regime-spike") == "crypto-regime-spike"

def test_h2t_skills_variants_collapse():
    assert canonical_lineage("agent-skills") == "h2t-skills"
    assert canonical_lineage("h2t-skills-119-editorial-pilot") == "h2t-skills"
    assert canonical_lineage("h2t-skills-editorial-wireframe") == "h2t-skills"

def test_memory_project_bucket_collapses():
    # ~/.claude/projects/C--dev-h2t-skills/memory → h2t-skills, не отдельный lineage
    assert canonical_lineage("C--dev-h2t-skills") == "h2t-skills"

def test_unknown_passthrough():
    assert canonical_lineage("quant-kb") == "quant-kb"
    assert canonical_lineage("rejuve") == "rejuve"

def test_worktree_path_collapses():
    # директории worktree тоже сворачиваются к родителю
    assert canonical_lineage("h2t-skills/.worktrees/pre-release-audit") == "h2t-skills"
