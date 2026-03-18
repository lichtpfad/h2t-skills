#!/usr/bin/env python3
"""
process_transcripts.py — LLM-enrichment для MeetGeek транскриптов.

Что делает:
  1. Парсит только секцию "Meeting Transcript", выбрасывает MeetGeek metadata
  2. Детектирует тип: A (реальные имена) vs B (Speaker_01)
  3. Вызывает Claude Haiku через CLI для обогащения
  4. Пишет frontmatter + чистый транскрипт
  5. Создаёт context/actions/ и context/decisions/ файлы
  6. Роутит личные/коуч-сессии в SELFWORK/transcripts/
  7. Обновляет context/meetings/INDEX.md
"""

import os
import re
import sys
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run: pip install pyyaml")
    raise

try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / '.dor' / 'secrets.env', override=False)
    load_dotenv(override=False)  # fallback: .env in cwd
except ImportError:
    pass  # python-dotenv optional — можно передать GEMINI_API_KEY вручную

import requests

try:
    from google import genai
    from google.genai import types
    _GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    _GEMINI_AVAILABLE = False

# ── Пути ──────────────────────────────────────────────────────────────────────

DOR_ROOT   = Path(os.environ.get('DOR_ROOT', Path.home() / 'Projects' / 'DOR'))
CONTEXT_ROOT = DOR_ROOT / 'context' if DOR_ROOT.exists() else Path.home() / '.dor' / 'output'
VAULT_ROOT   = Path(os.environ.get('VAULT_ROOT',
    DOR_ROOT / 'vault' if DOR_ROOT.exists() else Path.home() / '.dor' / 'vault'))

MEETINGS_DIR          = CONTEXT_ROOT / "meetings"
SELFWORK_TRANSCRIPTS  = DOR_ROOT / "content" / "SELFWORK" / "transcripts"
ACTIONS_DIR           = CONTEXT_ROOT / "actions"
DECISIONS_DIR         = CONTEXT_ROOT / "decisions"
PROJECTS_FILE         = DOR_ROOT / ".claude" / "projects.yaml"
# Sibling skill script (plugin layout: skills/{name}/scripts/)
CONVERT_SCRIPT = Path(__file__).parent.parent.parent / "convert-meeting-transcript" / "scripts" / "convert_docx_to_md.py"

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:latest"
GEMINI_MODEL = "gemini-2.5-flash-lite"

PERSONAL_CATEGORIES = {"personal", "coaching"}

# ── DOCX авто-конвертация ─────────────────────────────────────────────────────

def docx_to_md_path(docx_path: Path) -> Path:
    return docx_path.with_suffix(".md")

def ensure_md(filepath: Path) -> Path:
    """Если .docx — конвертирует в MD рядом, возвращает MD путь."""
    if filepath.suffix.lower() != ".docx":
        return filepath
    md_path = docx_to_md_path(filepath)
    if md_path.exists():
        return md_path
    result = subprocess.run(
        [sys.executable, str(CONVERT_SCRIPT), str(filepath)],
        input="y\n", capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"DOCX конвертация не удалась: {result.stderr[:200]}")
    return md_path

# ── JSON Schema для structured output ────────────────────────────────────────

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "participants":           {"type": "array", "items": {"type": "string"}},
        "speaker_map":            {"type": "object"},
        "meeting_type":           {"type": "string", "enum": [
            "partner_sync", "coaching", "client_call", "team",
            "creative", "technical", "personal", "teaching", "admin", "other"
        ]},
        "topic":                  {"type": "string"},
        "summary":                {"type": "string"},
        "projects":               {"type": "array", "items": {"type": "string"}},
        "action_items":           {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "owner":    {"type": "string"},
                    "task":     {"type": "string"},
                    "deadline": {"type": "string"}
                },
                "required": ["owner", "task"]
            }
        },
        "key_decisions":          {"type": "array", "items": {"type": "string"}},
        "open_questions":         {"type": "array", "items": {"type": "string"}},
        "category":               {"type": "string", "enum": ["work", "personal", "coaching"]},
        "tags":                   {"type": "array", "items": {"type": "string"}},
        "participants_confidence":{"type": "string", "enum": ["high", "medium", "low"]},
        "date_reliable":          {"type": "boolean"}
    },
    "required": ["participants", "meeting_type", "topic", "summary", "category",
                 "projects", "participants_confidence"]
}

# ── Загрузка проектов ─────────────────────────────────────────────────────────

def load_projects():
    with open(PROJECTS_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["projects"]

def build_projects_context(projects):
    lines = []
    for p in projects:
        aliases  = ", ".join(p.get("aliases", [])[:6])
        partners = ", ".join(p.get("partners", []))
        line = f"- {p['id']}: {p['name']}"
        if aliases:  line += f" (алиасы: {aliases})"
        if partners: line += f" [партнёры: {partners}]"
        lines.append(line)
    return "\n".join(lines)

# ── Парсинг транскрипта ───────────────────────────────────────────────────────

def extract_transcript(content: str) -> str:
    match = re.search(r'Meeting Transcript\s*\n(.*)', content, re.DOTALL)
    return match.group(1).strip() if match else content

def extract_meetgeek_sections(content: str) -> str | None:
    """Извлекает Meeting Summary + Meeting Highlights из оригинального MeetGeek файла.

    Возвращает строку с обоими разделами (если есть) или None.
    """
    parts = []
    summary_match = re.search(
        r'^Meeting Summary\s*\n(.*?)(?=^Meeting Highlights|\Z)',
        content, re.DOTALL | re.MULTILINE
    )
    highlights_match = re.search(
        r'^Meeting Highlights\s*\n(.*?)(?=^Meeting Transcript|\Z)',
        content, re.DOTALL | re.MULTILINE
    )
    if summary_match:
        text = summary_match.group(1).strip()
        if text:
            parts.append(f"### Meeting Summary\n\n{text}")
    if highlights_match:
        text = highlights_match.group(1).strip()
        if text:
            parts.append(f"### Meeting Highlights\n\n{text}")
    return "\n\n".join(parts) if parts else None

def detect_transcript_type(transcript: str) -> str:
    return "B" if re.search(r'\bSpeaker_\d+\b', transcript) else "A"

def extract_raw_date(content: str) -> str | None:
    match = re.search(r'^Date:\s*(.+)$', content, re.MULTILINE)
    return match.group(1).strip() if match else None

def is_already_processed(content: str) -> bool:
    return bool(re.match(r'^---\n', content) and 'processed: true' in content[:500])

# ── LLM вызов ────────────────────────────────────────────────────────────────

def build_prompt(transcript_type: str, projects_context: str) -> str:
    speaker_instruction = (
        "В транскрипте использованы Speaker_00, Speaker_01 и т.д. (без имён). "
        "По контексту разговора попробуй определить кто это. "
        "Если не можешь — напиши 'unknown'. Заполни speaker_map."
        if transcript_type == "B"
        else "В транскрипте уже есть реальные имена — используй их как есть."
    )
    return f"""Проанализируй транскрипт встречи. {speaker_instruction}

Известные проекты (используй только эти ID в поле projects):
{projects_context}

Правила:
- projects: только ID из списка выше, не придумывай новые
- category "personal" или "coaching" → конфиденциально
- tags: короткие ключевые слова в нижнем регистре
- topic и summary на языке транскрипта (русский или английский)
- date_reliable: false если встреча была загружена вручную (не авто-запись)

Верни структурированный JSON согласно схеме."""

def _call_ollama(prompt: str, transcript: str, model: str = OLLAMA_MODEL) -> dict:
    """Ollama REST API, JSON output через format='json'.

    Пробует /api/generate (completion-модели), при пустом ответе — /api/chat (chat-модели).
    """
    if len(transcript) > 10000:
        transcript = transcript[:10000] + "\n\n[ТРАНСКРИПТ ОБРЕЗАН]"

    schema_str = json.dumps(OUTPUT_SCHEMA, ensure_ascii=False)
    full_input = (
        f"{prompt}\n\n"
        f"Отвечай ТОЛЬКО валидным JSON по этой схеме:\n{schema_str}\n"
        f"Без markdown-блоков, без комментариев. Только JSON объект.\n\n"
        f"---ТРАНСКРИПТ---\n{transcript}\n---КОНЕЦ---"
    )

    # Попытка 1: /api/generate (completion API)
    resp = requests.post(
        OLLAMA_URL,
        json={"model": model, "prompt": full_input, "format": "json", "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    response_text = resp.json().get("response", "")

    # Попытка 2: /api/chat (chat API — для моделей вроде qwen, gpt-oss)
    if not response_text.strip():
        chat_url = OLLAMA_URL.replace("/api/generate", "/api/chat")
        resp = requests.post(
            chat_url,
            json={"model": model, "messages": [{"role": "user", "content": full_input}],
                  "format": "json", "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        response_text = resp.json().get("message", {}).get("content", "")

    return json.loads(response_text)


def _call_gemini(prompt: str, transcript: str, model: str = GEMINI_MODEL) -> dict:
    """Google Gemini API с нативным response_schema enforcement."""
    if not _GEMINI_AVAILABLE:
        raise RuntimeError("google-genai not installed: pip install google-genai")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")

    if len(transcript) > 10000:
        transcript = transcript[:10000] + "\n\n[ТРАНСКРИПТ ОБРЕЗАН]"

    full_input = f"{prompt}\n\n---ТРАНСКРИПТ---\n{transcript}\n---КОНЕЦ---"

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=full_input,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=OUTPUT_SCHEMA,
        ),
    )
    return json.loads(response.text)


def call_llm(prompt: str, transcript: str,
             backend: str = "gemini", model: str | None = None) -> dict:
    """Диспетчер бэкендов: gemini (default) или ollama."""
    if backend == "ollama":
        return _call_ollama(prompt, transcript, model=model or OLLAMA_MODEL)
    elif backend == "gemini":
        return _call_gemini(prompt, transcript, model=model or GEMINI_MODEL)
    else:
        raise ValueError(f"Unknown backend: {backend!r}. Use 'gemini' or 'ollama'.")

# ── Запись файла ──────────────────────────────────────────────────────────────

def write_processed_file(out_path: Path, metadata: dict, raw_date: str | None,
                          transcript: str, original_name: str,
                          meetgeek_content: str | None = None):
    # Заменяем Speaker_XX на реальные имена
    processed = transcript
    for speaker_id, real_name in metadata.get("speaker_map", {}).items():
        if real_name and real_name != "unknown":
            processed = processed.replace(speaker_id, real_name)

    frontmatter = {
        "title":                   metadata.get("topic", original_name),
        "date_raw":                raw_date or "unknown",
        "date_reliable":           metadata.get("date_reliable", True),
        "meeting_type":            metadata.get("meeting_type", "other"),
        "participants":            metadata.get("participants", []),
        "projects":                metadata.get("projects", []),
        "category":                metadata.get("category", "work"),
        "tags":                    metadata.get("tags", []),
        "transcript_type":         "B" if metadata.get("speaker_map") else "A",
        "participants_confidence": metadata.get("participants_confidence", "medium"),
        "processed":               True,
        "processed_at":            datetime.now().strftime("%Y-%m-%d"),
    }
    if metadata.get("speaker_map"):
        frontmatter["speaker_map"] = metadata["speaker_map"]

    # Summary: MeetGeek контент приоритетен; LLM summary — запасной вариант
    if meetgeek_content:
        summary_section = ["## Summary", "", meetgeek_content, ""]
    else:
        llm_summary = metadata.get("summary", "")
        summary_section = ["## Summary", "", llm_summary, ""] if llm_summary else []

    parts = [
        "---",
        yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False).strip(),
        "---", "",
    ] + summary_section

    if metadata.get("action_items"):
        parts += ["## Action Items", ""]
        for item in metadata["action_items"]:
            owner    = item.get("owner", "?")
            task     = item.get("task", "")
            deadline = f" (к {item['deadline']})" if item.get("deadline") else ""
            parts.append(f"- [ ] **{owner}**: {task}{deadline}")
        parts.append("")

    if metadata.get("key_decisions"):
        parts += ["## Key Decisions", ""]
        for d in metadata["key_decisions"]:
            parts.append(f"- {d}")
        parts.append("")

    if metadata.get("open_questions"):
        parts += ["## Open Questions", ""]
        for q in metadata["open_questions"]:
            parts.append(f"- {q}")
        parts.append("")

    parts += ["## Transcript", "", processed]

    out_path.write_text("\n".join(parts), encoding="utf-8")

# ── Action items / Decisions ──────────────────────────────────────────────────

def _slug(name: str) -> str:
    return re.sub(r'[^\w-]', '-', name.lower())[:50].strip('-')

def save_action_items(meeting_name: str, metadata: dict, source_file: Path):
    items = metadata.get("action_items", [])
    if not items:
        return
    ACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    fp = ACTIONS_DIR / f"{date_str}-{_slug(meeting_name)}.md"
    lines = [
        f"---",
        f"source_meeting: \"{source_file.name}\"",
        f"date: \"{date_str}\"",
        f"projects: {json.dumps(metadata.get('projects', []))}",
        f"status: open",
        f"---", "",
        f"# Action Items: {metadata.get('topic', meeting_name)}", "",
    ]
    for item in items:
        owner    = item.get("owner", "?")
        task     = item.get("task", "")
        deadline = f" (к {item['deadline']})" if item.get("deadline") else ""
        lines.append(f"- [ ] **{owner}**: {task}{deadline}")
    fp.write_text("\n".join(lines), encoding="utf-8")
    print(f"  → actions/{fp.name}")

def save_decisions(meeting_name: str, metadata: dict, source_file: Path):
    decisions = metadata.get("key_decisions", [])
    if not decisions:
        return
    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    fp = DECISIONS_DIR / f"{date_str}-{_slug(meeting_name)}.md"
    lines = [
        f"---",
        f"source_meeting: \"{source_file.name}\"",
        f"date: \"{date_str}\"",
        f"projects: {json.dumps(metadata.get('projects', []))}",
        f"---", "",
        f"# Decisions: {metadata.get('topic', meeting_name)}", "",
    ]
    for d in decisions:
        lines.append(f"- {d}")
    fp.write_text("\n".join(lines), encoding="utf-8")
    print(f"  → decisions/{fp.name}")

# ── INDEX.md ──────────────────────────────────────────────────────────────────

def update_index():
    rows = []
    for f in sorted(MEETINGS_DIR.glob("*.md")):
        if f.name == "INDEX.md":
            continue
        content = f.read_text(encoding="utf-8")
        if "processed: true" not in content[:500]:
            continue
        fm_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not fm_match:
            continue
        try:
            fm = yaml.safe_load(fm_match.group(1))
        except Exception:
            continue
        rows.append({
            "file":         f.name,
            "title":        fm.get("title", f.name)[:55],
            "date":         (fm.get("date_raw") or "")[:10],
            "type":         fm.get("meeting_type", ""),
            "participants": ", ".join(fm.get("participants", []))[:35],
            "projects":     ", ".join(fm.get("projects", [])),
        })

    rows.sort(key=lambda x: x["date"], reverse=True)

    lines = [
        "# Meetings Index",
        "",
        f"*Обновлён: {datetime.now().strftime('%Y-%m-%d')}  |  Встреч: {len(rows)}*",
        "",
        "| Дата | Тип | Участники | Тема | Проекты |",
        "|------|-----|-----------|------|---------|",
    ]
    for r in rows:
        link = f"[{r['title']}]({r['file']})"
        lines.append(f"| {r['date']} | {r['type']} | {r['participants']} | {link} | {r['projects']} |")

    (MEETINGS_DIR / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n→ INDEX.md обновлён ({len(rows)} встреч)")

# ── Обработка одного файла ────────────────────────────────────────────────────

def process_file(filepath: Path, projects_context: str, dry_run: bool, force: bool,
                 dump_json: bool = False, backend: str = "gemini",
                 model: str | None = None) -> bool:
    # Когда --dump-json, диагностика идёт в stderr чтобы stdout был чистым JSON
    log = (lambda *a, **kw: print(*a, **kw, file=sys.stderr)) if dump_json else print

    # Авто-конвертация .docx → .md если нужно
    try:
        filepath = ensure_md(filepath)
    except RuntimeError as e:
        log(f"  ✗ DOCX конвертация: {e}")
        return False

    log(f"\n{'[DRY]' if dry_run else ''}  {filepath.name}")

    content = filepath.read_text(encoding="utf-8")

    if is_already_processed(content) and not force:
        log("  ✓ уже обработан, пропускаю (--force чтобы перезаписать)")
        return False

    raw_date        = extract_raw_date(content)
    meetgeek_content = extract_meetgeek_sections(content)
    transcript      = extract_transcript(content)
    t_type     = detect_transcript_type(transcript)
    log(f"  тип={t_type}  дата={raw_date}")

    if dry_run:
        log(f"  [DRY] пропускаю LLM вызов")
        return True

    prompt = build_prompt(t_type, projects_context)
    try:
        metadata = call_llm(prompt, transcript, backend=backend, model=model)
    except Exception as e:
        log(f"  ✗ LLM ошибка: {e}")
        return False

    # --dump-json: вывести сырой JSON и выйти без записи файла
    if dump_json:
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        return True

    category     = metadata.get("category", "work")
    meeting_type = metadata.get("meeting_type", "other")
    projects     = metadata.get("projects", [])
    log(f"  category={category}  type={meeting_type}  projects={projects}")

    # Определяем путь вывода
    if category in PERSONAL_CATEGORIES:
        SELFWORK_TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
        out_path = SELFWORK_TRANSCRIPTS / filepath.name
        log(f"  → роутинг в SELFWORK/transcripts/")
    else:
        out_path = filepath

    meeting_name = filepath.stem.replace("Meeting Notes- ", "").replace("Meeting Notes-", "")
    write_processed_file(out_path, metadata, raw_date, transcript, meeting_name,
                         meetgeek_content=meetgeek_content)

    # Если переместили — удаляем оригинал
    if out_path != filepath:
        filepath.unlink()

    save_action_items(meeting_name, metadata, filepath)
    save_decisions(meeting_name, metadata, filepath)

    log(f"  ✓ готово")
    return True

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Process MeetGeek transcripts with LLM enrichment"
    )
    parser.add_argument("file",        nargs="?", help="Один файл для обработки")
    parser.add_argument("--all",       action="store_true", help="Обработать все необработанные файлы")
    parser.add_argument("--dry-run",   action="store_true", help="Показать что будет сделано без изменений")
    parser.add_argument("--force",     action="store_true", help="Перезаписать уже обработанные файлы")
    parser.add_argument("--no-index",  action="store_true", help="Не обновлять INDEX.md")
    parser.add_argument("--dump-json", action="store_true",
                        help="Вывести сырой JSON от LLM в stdout (для тестирования с jq)")
    parser.add_argument("--backend", choices=["gemini", "ollama"], default="gemini",
                        help="LLM backend (default: gemini)")
    parser.add_argument("--model", default=None,
                        help="Override model name (e.g. gemini-2.5-flash-lite, llama3.2:latest)")
    args = parser.parse_args()

    projects         = load_projects()
    projects_context = build_projects_context(projects)

    processed_any = False

    if args.file:
        fp = Path(args.file)
        if not fp.is_absolute():
            # Try relative to cwd first (e.g. eval fixtures), fall back to MEETINGS_DIR
            fp_cwd = Path.cwd() / args.file
            fp = fp_cwd if fp_cwd.exists() else MEETINGS_DIR / args.file
        process_file(fp, projects_context, args.dry_run, args.force,
                     dump_json=args.dump_json, backend=args.backend, model=args.model)
        processed_any = True

    elif args.all:
        # MD + DOCX, дедупликация: если есть оба — берём .md (уже конвертирован)
        all_files = sorted(
            list(MEETINGS_DIR.glob("*.md")) + list(MEETINGS_DIR.glob("*.docx"))
        )
        seen: dict[str, Path] = {}
        for f in all_files:
            if f.stem not in seen or f.suffix == ".md":
                seen[f.stem] = f
        files = sorted(f for f in seen.values() if f.name != "INDEX.md")
        print(f"Найдено {len(files)} файлов в context/meetings/", file=sys.stderr if args.dump_json else sys.stdout)
        for f in files:
            ok = process_file(f, projects_context, args.dry_run, args.force,
                              dump_json=args.dump_json, backend=args.backend, model=args.model)
            if ok:
                processed_any = True

    else:
        parser.print_help()
        return

    if processed_any and not args.dry_run and not args.no_index and not args.dump_json:
        update_index()

if __name__ == "__main__":
    main()
