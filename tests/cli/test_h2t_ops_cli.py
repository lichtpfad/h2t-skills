from h2t_ops.cli import dispatch


def test_top_level_help_uses_h2t_ops_parser(capsys):
    assert dispatch(["--help"]) == 0

    out = capsys.readouterr().out
    assert "usage: h2t-ops" in out
    assert "h2t-ops unified connector CLI" in out
    assert "connectors" in out
    assert "deploy" in out
    assert "h2t unified CLI" not in out


def test_short_top_level_help_uses_h2t_ops_parser(capsys):
    assert dispatch(["-h"]) == 0

    out = capsys.readouterr().out
    assert "usage: h2t-ops" in out
    assert "connectors" in out
    assert "deploy" in out


def test_research_help_lists_visual_ocr_subcommand(capsys):
    assert dispatch(["research", "--help"]) == 0

    out = capsys.readouterr().out
    assert "visual-ocr" in out
    assert "Create a review-required OCR rescue artifact" in out


def test_top_level_deploy_routes_to_deploy_dispatcher(monkeypatch):
    calls = []

    def fake_dispatch(argv):
        calls.append(list(argv))
        return 17

    monkeypatch.setattr("h2t_ops.cli._deploy_dispatch", fake_dispatch)

    assert dispatch(["deploy", "list"]) == 17
    assert calls == [["list"]]
