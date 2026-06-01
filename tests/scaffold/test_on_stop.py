import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import MagicMock, patch


def _load_on_stop():
    path = Path(__file__).parents[2] / "plugins/h2t-core/hooks-handlers/on-stop"
    spec = importlib.util.spec_from_file_location(
        "h2t_on_stop", path, loader=SourceFileLoader("h2t_on_stop", str(path))
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_resolve_repo_slug_uses_gh_repo_view():
    mod = _load_on_stop()
    with patch.object(mod.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="lichtpfad/h2t-skills\n", stderr="")
        assert mod._resolve_repo_slug() == "lichtpfad/h2t-skills"
    assert mock_run.call_args[0][0][:3] == ["gh", "repo", "view"]


def test_closed_milestones_uses_gh_api():
    mod = _load_on_stop()
    payload = '[{"title":"M1","open_issues":0},{"title":"M2","open_issues":2}]'
    with patch.object(mod.subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=payload, stderr="")
        assert mod._closed_ready_milestones("lichtpfad/h2t-skills") == ["M1"]
    cmd = mock_run.call_args[0][0]
    assert cmd[:2] == ["gh", "api"]
    assert any("repos/lichtpfad/h2t-skills/milestones?state=open" in str(c) for c in cmd)
    assert "-f" not in cmd


def test_check_milestones_never_raises_on_gh_error(capsys):
    mod = _load_on_stop()
    with patch.object(mod, "_resolve_repo_slug", side_effect=RuntimeError("boom")):
        mod._check_milestones()
    assert capsys.readouterr().out == ""
