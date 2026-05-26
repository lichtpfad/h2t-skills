from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

import pytest

from h2t_ops import cli
from h2t_ops.connectors.research import commands, store
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


def test_parser_registration_for_research_navigation_index():
    parser = cli.build_parser()

    parsed = parser.parse_args(
        [
            "research",
            "index",
            "documents",
            "--project",
            "project:demo",
            "--output-dir",
            "/tmp/research",
        ]
    )

    assert parsed.research_cmd == "index"
    assert parsed.index_name == "documents"
    assert parsed.project == "project:demo"
    assert parsed.output_dir == "/tmp/research"
    assert parsed._handler is commands.run


def test_parser_registration_for_research_navigation_show():
    parser = cli.build_parser()

    parsed = parser.parse_args(
        [
            "research",
            "show",
            "document",
            "research-doc:abc",
            "--output-dir",
            "/tmp/research",
            "--json",
        ]
    )

    assert parsed.research_cmd == "show"
    assert parsed.object_type == "document"
    assert parsed.object_id == "research-doc:abc"
    assert parsed.output_dir == "/tmp/research"
    assert parsed.as_json is True
    assert parsed._handler is commands.run


def test_parser_registration_for_research_navigation_resolve_by_url():
    parser = cli.build_parser()

    parsed = parser.parse_args(
        [
            "research",
            "resolve",
            "--url",
            "https://example.com/post",
            "--output-dir",
            "/tmp/research",
        ]
    )

    assert parsed.research_cmd == "resolve"
    assert parsed.url_value == "https://example.com/post"
    assert parsed.alias_value is None
    assert parsed.alias_type == "url"
    assert parsed.output_dir == "/tmp/research"
    assert parsed._handler is commands.run


def test_parser_registration_for_research_navigation_resolve_by_alias_with_type():
    parser = cli.build_parser()

    parsed = parser.parse_args(
        [
            "research",
            "resolve",
            "--alias",
            "abc-uuid",
            "--alias-type",
            "document-id",
            "--output-dir",
            "/tmp/research",
        ]
    )

    assert parsed.research_cmd == "resolve"
    assert parsed.alias_value == "abc-uuid"
    assert parsed.alias_type == "document-id"
    assert parsed.url_value is None


def test_parser_registration_for_research_navigation_resolve_requires_one_of_url_or_alias():
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["research", "resolve"])

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "research",
                "resolve",
                "--url",
                "https://example.com",
                "--alias",
                "abc-uuid",
            ]
        )


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

    def list_research_index(self, index_name: str, project: str | None = None) -> dict:
        self.calls.append(("list_research_index", {"index_name": index_name, "project": project}))
        return {"method": "list_research_index", "index_name": index_name, "project": project}

    def show_research_object(self, object_type: str, object_id: str) -> dict:
        self.calls.append(("show_research_object", {"object_type": object_type, "object_id": object_id}))
        return {"method": "show_research_object", "object_type": object_type, "object_id": object_id}

    def resolve_research_alias(self, alias_value: str, alias_type: str = "url") -> dict:
        self.calls.append(
            (
                "resolve_research_alias",
                {"alias_value": alias_value, "alias_type": alias_type},
            )
        )
        return {
            "method": "resolve_research_alias",
            "alias_value": alias_value,
            "alias_type": alias_type,
        }


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


def test_run_dispatches_navigation_index(monkeypatch, tmp_path):
    _patch_fake_client(monkeypatch)
    args = argparse.Namespace(
        research_cmd="index",
        output_dir=str(tmp_path),
        index_name="documents",
        project="project:demo",
    )

    result = commands.run(args)

    assert FakeResearchClient.instances[0].output_dir == tmp_path
    assert result["method"] == "list_research_index"
    assert result["index_name"] == "documents"
    assert result["project"] == "project:demo"


def test_run_dispatches_navigation_show(monkeypatch, tmp_path):
    _patch_fake_client(monkeypatch)
    args = argparse.Namespace(
        research_cmd="show",
        output_dir=str(tmp_path),
        object_type="document",
        object_id="research-doc:abc",
    )

    result = commands.run(args)

    assert FakeResearchClient.instances[0].output_dir == tmp_path
    assert result["method"] == "show_research_object"
    assert result["object_type"] == "document"
    assert result["object_id"] == "research-doc:abc"


def test_run_dispatches_navigation_resolve_by_url(monkeypatch):
    _patch_fake_client(monkeypatch)
    args = argparse.Namespace(
        research_cmd="resolve",
        output_dir=None,
        url_value="https://example.com/post",
        alias_value=None,
        alias_type="url",
    )

    result = commands.run(args)

    assert FakeResearchClient.instances[0].output_dir is None
    assert result["method"] == "resolve_research_alias"
    assert result["alias_value"] == "https://example.com/post"
    assert result["alias_type"] == "url"


def test_run_dispatches_navigation_resolve_by_alias(monkeypatch):
    _patch_fake_client(monkeypatch)
    args = argparse.Namespace(
        research_cmd="resolve",
        output_dir=None,
        url_value=None,
        alias_value="abc-uuid",
        alias_type="document-id",
    )

    result = commands.run(args)

    assert FakeResearchClient.instances[0].output_dir is None
    assert result["method"] == "resolve_research_alias"
    assert result["alias_value"] == "abc-uuid"
    assert result["alias_type"] == "document-id"


def test_cli_dispatch_navigates_research_index_documents(tmp_path, capsys):
    root = tmp_path
    doc_a = store.build_research_document(
        canonical_url="https://example.com/first",
        source_url="https://example.com/first",
        provider="jina",
        title="First",
        fetched_at="2026-05-27T10:00:00Z",
        content_hash="a",
        artifact_refs={
            "metadata": "artifact.json",
            "normalized_text": "sources.json",
            "citation_bundle": None,
            "markdown_mirror": "partial.md",
        },
        project_ids=["project:demo"],
        thread_ids=[],
        entity_ids=[],
    )
    doc_b = store.build_research_document(
        canonical_url="https://example.com/second",
        source_url="https://example.com/second",
        provider="jina",
        title="Second",
        fetched_at="2026-05-27T10:01:00Z",
        content_hash="b",
        artifact_refs={
            "metadata": "artifact.json",
            "normalized_text": "sources.json",
            "citation_bundle": None,
            "markdown_mirror": "partial.md",
        },
        project_ids=["project:other"],
        thread_ids=[],
        entity_ids=[],
    )
    store.write_object(root, "documents", doc_a["document_id"], doc_a)
    store.write_object(root, "documents", doc_b["document_id"], doc_b)
    store.upsert_document_index(root, doc_a)
    store.upsert_document_index(root, doc_b)

    code = cli.dispatch(
        [
            "research",
            "index",
            "documents",
            "--project",
            "project:demo",
            "--output-dir",
            str(root),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
    assert payload["result"]["kind"] == "research_index"
    assert payload["result"]["count"] == 1
    assert payload["result"]["items"][0]["document_id"] == doc_a["document_id"]


def test_cli_dispatch_navigates_show_document_thread_run_synthesis(tmp_path, capsys):
    root = tmp_path
    document = store.build_research_document(
        canonical_url="https://example.com/doc",
        source_url="https://example.com/doc",
        provider="jina",
        title="Example Document",
        fetched_at="2026-05-27T10:00:00Z",
        content_hash="doc",
        artifact_refs={
            "metadata": "artifact.json",
            "normalized_text": "sources.json",
            "citation_bundle": None,
            "markdown_mirror": "partial.md",
        },
        project_ids=["project:demo"],
        thread_ids=[],
        entity_ids=[],
    )
    thread = store.build_research_thread(
        question="What is Exa?",
        created_at="2026-05-27T10:01:00Z",
        context_type="project",
        context_id="project:demo",
        domain="research",
        topics=["exa"],
    )
    run = store.build_research_run(
        thread_id=thread["thread_id"],
        created_at="2026-05-27T10:02:00Z",
        query="exa answer",
        provider_set=["exa"],
        document_ids=[document["document_id"]],
    )
    synthesis = store.build_research_synthesis(
        thread_id=thread["thread_id"],
        run_ids=[run["run_id"]],
        summary="A grounded answer exists.",
        created_at="2026-05-27T10:03:00Z",
    )
    store.write_object(root, "documents", document["document_id"], document)
    store.write_object(root, "threads", thread["thread_id"], thread)
    store.write_object(root, "runs", run["run_id"], run)
    store.write_object(root, "syntheses", synthesis["synthesis_id"], synthesis)

    code_doc = cli.dispatch(
        [
            "research",
            "show",
            "document",
            document["document_id"],
            "--output-dir",
            str(root),
            "--json",
        ]
    )
    doc_payload = json.loads(capsys.readouterr().out)
    assert code_doc == 0
    assert doc_payload["result"]["object_type"] == "document"
    assert doc_payload["result"]["object_id"] == document["document_id"]
    assert doc_payload["result"]["object"]["title"] == document["title"]

    code_thread = cli.dispatch(
        [
            "research",
            "show",
            "thread",
            thread["thread_id"],
            "--output-dir",
            str(root),
            "--json",
        ]
    )
    thread_payload = json.loads(capsys.readouterr().out)
    assert code_thread == 0
    assert thread_payload["result"]["object_type"] == "thread"
    assert thread_payload["result"]["object"]["thread_id"] == thread["thread_id"]

    code_run = cli.dispatch(
        [
            "research",
            "show",
            "run",
            run["run_id"],
            "--output-dir",
            str(root),
            "--json",
        ]
    )
    run_payload = json.loads(capsys.readouterr().out)
    assert code_run == 0
    assert run_payload["result"]["object_type"] == "run"
    assert run_payload["result"]["object"]["run_id"] == run["run_id"]

    code_synthesis = cli.dispatch(
        [
            "research",
            "show",
            "synthesis",
            synthesis["synthesis_id"],
            "--output-dir",
            str(root),
            "--json",
        ]
    )
    synthesis_payload = json.loads(capsys.readouterr().out)
    assert code_synthesis == 0
    assert synthesis_payload["result"]["object_type"] == "synthesis"
    assert synthesis_payload["result"]["object"]["synthesis_id"] == synthesis["synthesis_id"]


def test_cli_dispatch_resolve_stale_alias(tmp_path, capsys):
    root = tmp_path
    store.upsert_alias_index(
        root,
        [
            {
                "alias_type": "url",
                "alias_value": "https://example.com/missing",
                "target_object_type": "document",
                "target_id": "research-doc:missing",
                "confidence": "high",
            }
        ],
    )

    code = cli.dispatch(
        [
            "research",
            "resolve",
            "--url",
            "https://example.com/missing",
            "--output-dir",
            str(root),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["result"]["kind"] == "research_resolution"
    assert payload["result"]["count"] == 1
    assert payload["result"]["matches"][0]["object_exists"] is False
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
