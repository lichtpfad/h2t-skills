from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

import pytest

from h2t_ops import cli
from h2t_ops.connectors.research import commands
from h2t_ops.core.errors import ProviderError, UsageError
from h2t_ops.core.registry import discover


def _remove_research_provider_modules() -> None:
    package = sys.modules.get("h2t_ops.connectors.research")
    for name in (
        "h2t_ops.connectors.research.client",
        "h2t_ops.connectors.research.exa",
        "h2t_ops.connectors.research.fetch",
    ):
        sys.modules.pop(name, None)
        if package is not None:
            attr = name.rsplit(".", 1)[-1]
            if hasattr(package, attr):
                delattr(package, attr)


def test_research_connector_registered_without_provider_imports():
    _remove_research_provider_modules()

    specs = {spec.name: spec for spec in discover()}

    assert "research" in specs
    assert specs["research"].client == "h2t_ops.connectors.research.client:ResearchClient"
    assert "h2t_ops.connectors.research.client" not in sys.modules
    assert "h2t_ops.connectors.research.exa" not in sys.modules
    assert "h2t_ops.connectors.research.fetch" not in sys.modules


def test_parser_registration_for_research_subcommands():
    parser = cli.build_parser()

    search = parser.parse_args(
        [
            "research",
            "search",
            "--query",
            "research connector",
            "--mode",
            "news",
            "--include-domains",
            "example.com,h2t.ai",
            "--json",
        ]
    )
    fetch = parser.parse_args(
        [
            "research",
            "fetch",
            "--url",
            "https://example.com",
            "--provider",
            "crawl4ai",
            "--format",
            "md",
        ]
    )

    assert search.connector == "research"
    assert search.research_cmd == "search"
    assert search.as_json is True
    assert search._handler is commands.run
    assert fetch.research_cmd == "fetch"
    assert fetch.fmt == "md"
    assert fetch.provider == "crawl4ai"


def test_parser_registration_for_research_visual_ocr():
    parser = cli.build_parser()

    parsed = parser.parse_args(
        [
            "research",
            "visual-ocr",
            "--fetch-sidecar",
            "artifact.sources.json",
            "--image-path",
            "capture.png",
            "--json",
        ]
    )

    assert parsed.connector == "research"
    assert parsed.research_cmd == "visual-ocr"
    assert parsed.fetch_sidecar == "artifact.sources.json"
    assert parsed.image_path == "capture.png"
    assert parsed.project == "default"
    assert parsed.as_json is True
    assert parsed._handler is commands.run


class FakeResearchClient:
    instances: list["FakeResearchClient"] = []

    def __init__(self, *, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir
        self.calls: list[tuple[str, dict]] = []
        self.instances.append(self)

    def preflight(self) -> dict:
        self.calls.append(("preflight", {}))
        return {"method": "preflight", "output_dir": str(self.output_dir)}

    def search(self, **kwargs) -> dict:
        self.calls.append(("search", kwargs))
        return {"method": "search", "kwargs": kwargs, "output_dir": str(self.output_dir)}

    def crawl(self, url: str, **kwargs) -> dict:
        self.calls.append(("crawl", {"url": url, **kwargs}))
        return {"method": "crawl", "url": url, "kwargs": kwargs}

    def fetch_url(self, url: str, **kwargs) -> dict:
        self.calls.append(("fetch", {"url": url, **kwargs}))
        return {"method": "fetch", "url": url, "kwargs": kwargs}

    def visual_ocr(self, **kwargs) -> dict:
        self.calls.append(("visual_ocr", kwargs))
        return {"method": "visual_ocr", "kwargs": kwargs}


def _patch_fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    client = importlib.import_module("h2t_ops.connectors.research.client")
    FakeResearchClient.instances = []
    monkeypatch.setattr(client, "ResearchClient", FakeResearchClient)


def test_run_dispatches_preflight(monkeypatch):
    _patch_fake_client(monkeypatch)
    args = argparse.Namespace(research_cmd="preflight", output_dir=None)

    result = commands.run(args)

    assert result == {"method": "preflight", "output_dir": "None"}
    assert FakeResearchClient.instances[0].calls == [("preflight", {})]


def test_run_dispatches_search_and_splits_csv(monkeypatch, tmp_path):
    _patch_fake_client(monkeypatch)
    args = argparse.Namespace(
        research_cmd="search",
        output_dir=str(tmp_path),
        query="research connector",
        mode="news",
        depth="deep",
        num_results=4,
        additional_queries="exa, fetch, ",
        start_date="2026-01-01",
        end_date="2026-05-21",
        include_domains="example.com,h2t.ai",
        exclude_domains="spam.test",
        include_text="alpha",
        exclude_text="beta,gamma",
        country="US",
        full_text=True,
        project="h2t skills",
        no_retry=True,
    )

    result = commands.run(args)

    assert FakeResearchClient.instances[0].output_dir == tmp_path
    kwargs = result["kwargs"]
    assert kwargs["query"] == "research connector"
    assert kwargs["additional_queries"] == ["exa", "fetch"]
    assert kwargs["include_domains"] == ["example.com", "h2t.ai"]
    assert kwargs["exclude_text"] == ["beta", "gamma"]
    assert kwargs["full_text"] is True
    assert kwargs["no_retry"] is True


def test_run_dispatches_crawl(monkeypatch):
    _patch_fake_client(monkeypatch)
    args = argparse.Namespace(
        research_cmd="crawl",
        output_dir=None,
        url="https://example.com/page",
        project="h2t skills",
    )

    result = commands.run(args)

    assert result["method"] == "crawl"
    assert result["url"] == "https://example.com/page"
    assert result["kwargs"] == {"project": "h2t skills"}


def test_run_dispatches_fetch(monkeypatch):
    _patch_fake_client(monkeypatch)
    args = argparse.Namespace(
        research_cmd="fetch",
        output_dir=None,
        url="https://example.com/page",
        provider="crawl4ai",
        keep_raw=True,
        timeout_ms=1234,
        min_body_chars=99,
        user_agent="agent",
        project="h2t skills",
        config_path="fetch.json",
    )

    result = commands.run(args)

    assert result["method"] == "fetch"
    assert result["url"] == "https://example.com/page"
    assert result["kwargs"] == {
        "provider": "crawl4ai",
        "keep_raw": True,
        "timeout_ms": 1234,
        "min_body_chars": 99,
        "user_agent": "agent",
        "project": "h2t skills",
        "config_path": "fetch.json",
    }


def test_run_dispatches_visual_ocr(monkeypatch):
    _patch_fake_client(monkeypatch)
    output_dir = str(Path.cwd() / "tmp" / "research-visual-ocr")
    args = argparse.Namespace(
        research_cmd="visual-ocr",
        output_dir=output_dir,
        fetch_sidecar="artifact.sources.json",
        image_path="capture.png",
        project="demo",
    )

    result = commands.run(args)

    assert FakeResearchClient.instances[0].output_dir == Path(output_dir)
    assert result["method"] == "visual_ocr"
    assert result["kwargs"] == {
        "fetch_sidecar": "artifact.sources.json",
        "image_path": "capture.png",
        "project": "demo",
    }


def test_real_research_client_visual_ocr_missing_sidecar_raises_usageerror(tmp_path):
    from h2t_ops.connectors.research.client import ResearchClient

    with pytest.raises(UsageError, match="fetch sidecar not found"):
        ResearchClient(output_dir=tmp_path).visual_ocr(
            fetch_sidecar="artifact.sources.json",
            image_path="capture.png",
            project="demo",
        )


def test_dispatch_json_error_preserves_details(monkeypatch, capsys):
    client = importlib.import_module("h2t_ops.connectors.research.client")

    class ErrorClient(FakeResearchClient):
        def search(self, **kwargs) -> dict:
            raise ProviderError(
                "Exa failed",
                details={
                    "provider_envelope": {
                        "status": "FAILED",
                        "telemetry": {
                            "attempts": [
                                {
                                    "engine": "exa",
                                    "error": "exa_4xx_nonretryable",
                                }
                            ]
                        },
                    }
                },
            )

    monkeypatch.setattr(client, "ResearchClient", ErrorClient)

    code = cli.dispatch(["research", "search", "--query", "q", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert code == 1
    assert payload["provider"] == "research"
    assert payload["error"]["type"] == "provider"
    assert payload["error"]["details"]["provider_envelope"]["status"] == "FAILED"
    assert (
        payload["error"]["details"]["provider_envelope"]["telemetry"]["attempts"][0]["error"]
        == "exa_4xx_nonretryable"
    )


def test_research_help_does_not_import_or_instantiate_client(capsys):
    _remove_research_provider_modules()

    code = cli.dispatch(["research", "--help"])

    captured = capsys.readouterr()
    assert code == 0
    assert "preflight" in captured.out
    assert "search" in captured.out
    assert "h2t_ops.connectors.research.client" not in sys.modules
    assert "h2t_ops.connectors.research.exa" not in sys.modules
    assert "h2t_ops.connectors.research.fetch" not in sys.modules


def test_research_skill_documents_json_first_local_truth():
    text = Path("plugins/h2t-ops/skills/research/SKILL.md").read_text(encoding="utf-8")

    assert "canonical local truth" in text
    assert "Markdown" in text
    assert "threads.index.json" in text
    assert "documents.index.json" in text
    assert "If index and object disagree, object wins." in text
