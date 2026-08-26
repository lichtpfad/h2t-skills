---
title: "Research Fetch URL — Provider Ladder Core CLI"
status: "draft"
owner: "lichtpfad"
date: "2026-05-07"
milestone: "Phase-2 research tooling"
related_issue: "lichtpfad/h2t-skills#103"
parent_issue: "lichtpfad/h2t-skills#98"
umbrella_issue: "lichtpfad/h2t-skills#97"
related_pr: "lichtpfad/h2t-skills#106 (merged: provider envelope core)"
related_adr: "C:/work/TD/docs/adr/0005-phase-2-script-extraction-backlog.md (Candidate 3 — fetch ladder)"
downstream:
  - "lichtpfad/h2t-skills#105 (AllTouchDesigner adapter)"
  - "lichtpfad/h2t-skills#104 (IIHQ adapter)"
supersedes: null
---

# Research Fetch URL — Provider Ladder Core CLI

**Goal.** Реализовать `fetch_url.py` — reusable CLI provider-ladder, который пытается получить содержимое произвольного URL через серию провайдеров (`direct → jina → playwright → optional paid`) и возвращает honest envelope с `status ∈ {OK, DEGRADED, FAILED}`, провайдером, который сработал, и per-attempt телеметрией. Это база для site-adapters AllTouchDesigner (#105) и IIHQ (#104).

**Scope (PR #1):** только generic URL fetcher. Сайт-специфичные парсеры — отдельные PR (#105, #104). Baseline implementation покрывает `direct` + `jina`. `playwright` / `crawl4ai` / `firecrawl` / `browserless` — провайдер-абстракция готова, но в PR#1 либо stubbed (выбрасывает `ProviderNotConfigured`), либо реализован минимально под config-flag.

**Non-goals.**

- Не реализуем `crawl4ai`, `firecrawl`, `browserless` clients в PR#1 — только провайдер-интерфейс + config gating.
- Не делаем robots.txt-чекер (см. §13 Open questions).
- Не обходим auth/paywall. Никогда. Login/payment-walls возвращают `FAILED` с `content_gate`.
- Не реализуем CAPTCHA-solving.
- Не вводим site-specific selectors (это #104/#105).
- Не меняем `exa_search.py` (envelope core уже merged via PR #106).
- Не вводим cache (есть `~/.h2t/research/` для sidecar; full caching — отдельная задача).

---

## 1. Context & Problem

### 1.1 Что выявил TD POP run

`C:/work/TD/pipeline-log/td-pop/0003-iteration-3-harvest.md` зафиксировал failure-class на нескольких high-signal источниках:

| Сайт | Класс ошибки | Пример URL |
|---|---|---|
| `alltd.org` | HTTP 403 на plain WebFetch / curl | `https://alltd.org/glsl-for-pops-in-touchdesigner-lesson-0-introduction-to-glsl-for-pops/` |
| `interactiveimmersive.io` | JS-rendered shell без body | `https://interactiveimmersive.io/blog/touchdesigner-3d/pops-in-touchdesigner-faq/` |
| `iihq.tv` | redirect → JS shell | `https://iihq.tv/4nFDCKc` |
| `forum.derivative.ca` (часть кейсов) | auth-required attachments | `_approved-harvest.md` rows |

Plain WebFetch → harvest пометил эти источники `failed-harvest`. Wiki-консумер вынужден был помечать Evidence как `availability: failed-harvest`. Проблема **повторится** на любом следующем topic'е (td-glsl, td-compute, любая research-сессия по live-веб-источникам).

### 1.2 Почему это не "просто Firecrawl"

ADR-0005 Candidate 3 рассматривает Firecrawl, но фиксирует **vendor-skill hijacking** как анти-паттерн: "let a vendor API become the research pipeline". Альтернатива — own thin abstraction с провайдерами под config:

1. Большая часть HTTP-фейлов решается local providers (direct + Jina Reader).
2. Playwright/Crawl4AI закрывают JS-rendered cases без external billing.
3. Paid providers (Firecrawl/Browserless) — escalation path, не default.
4. Telemetry должна показать **какой провайдер сработал** — иначе невозможно оценить, нужны ли вообще paid providers в проде.

### 1.3 Связь с merged envelope (#100 / PR #106)

Envelope core реализован в `exa_search.py` (`build_envelope`, `ENVELOPE_VERSION = "1"`). `fetch_url.py` использует **тот же `envelope_version`** и **те же status semantics** (`OK | DEGRADED | FAILED`), но **другую schema** для `results` (одиночный article vs Exa results-list). Подробности — §4.

---

## 2. Architecture Overview

### 2.1 Layout

```
plugins/h2t-ops/skills/research/
├── scripts/
│   ├── exa_search.py          # existing, не трогаем
│   └── fetch_url.py           # NEW — этот спек
└── tests/
    ├── test_exa_search.py     # existing
    ├── test_fetch_url.py      # NEW
    └── fixtures/
        └── fetch/             # NEW — HTML fixtures
            ├── public_article.html
            ├── public_article_jina.md
            ├── js_shell.html
            ├── short_body.html
            ├── login_wall.html
            ├── paywall.html
            └── alltd_403_body.html
```

`fetch_url.py` — **single-file CLI**, по конвенции `exa_search.py`. Адаптеры (#104/#105) могут импортировать его публичные функции (`fetch_via_ladder`, `build_fetch_envelope`, классы провайдеров).

### 2.2 Высокоуровневый поток

```
URL + provider="auto"
    ↓
ProviderLadder.run()
    ├── DirectProvider          ← stdlib urllib + extraction (trafilatura | inline fallback)
    ├── JinaProvider            ← https://r.jina.ai/<url> + JINA_API_KEY (optional)
    ├── PlaywrightProvider      ← optional, gated by config + import availability
    ├── Crawl4AIProvider        ← stub в PR#1 (raises ProviderNotConfigured)
    ├── FirecrawlProvider       ← stub в PR#1 (raises ProviderNotConfigured)
    └── BrowserlessProvider     ← stub в PR#1 (raises ProviderNotConfigured)
    ↓
ContentClassifier
    ├── is_substantive(text)
    ├── detect_js_shell(html)
    ├── detect_login_wall(html)
    └── detect_paywall(html)
    ↓
build_fetch_envelope(...) → JSON
    ↓
stdout (markdown summary | --json envelope) + sidecar `.sources.json`
```

### 2.3 Ladder decision logic (`--provider auto`)

```
attempts = []
for provider in enabled_providers_in_order:
    result = provider.fetch(url, timeout)
    attempts.append(telemetry(result))
    
    if result.is_substantive_ok:
        return OK_envelope(provider, result, attempts)
    
    if result.is_hard_gated:               # login / paid → не пытаемся следующих
        return FAILED_envelope(content_gate, attempts)
    
    # otherwise: DEGRADED, fall through to next provider
    continue

# Exhausted ladder
best = pick_best_degraded(results)        # most body, prefer non-shell
if best is not None:
    return DEGRADED_envelope(best, attempts)
return FAILED_envelope("all_providers_failed", attempts)
```

**Hard-gated short-circuit:** если direct-провайдер уверенно детектит login/paywall (е.g. HTTP 401, или meta-refresh на login-page, или известные paywall-tokens в DOM) — сразу `FAILED` без обхода. Bypass auth/paywall запрещён.

**Soft-gated (cookie banner only):** не считается gated. Извлечённый body пройдёт substantive-check. Если за баннером больше ничего нет → DEGRADED с reason=`no_content_behind_banner`, ladder пробует следующего.

---

## 3. CLI Surface

### 3.1 Subcommands

```bash
# Default subcommand: fetch (single URL)
python plugins/h2t-ops/skills/research/scripts/fetch_url.py \
  --url "https://alltd.org/..." \
  [--provider auto|direct|jina|playwright|crawl4ai|firecrawl|browserless] \
  [--format markdown|text|html] \
  [--json] \
  [--keep-raw] \
  [--timeout-ms 15000] \
  [--min-body-chars 200] \
  [--user-agent "h2t-research-fetch/0.0.1 (+https://github.com/lichtpfad/h2t-skills)"] \
  [--output-dir ~/.h2t/research/] \
  [--project default] \
  [--config ~/.h2t/config/research/fetch_providers.yaml]

# Preflight (env + connectivity)
python ... fetch_url.py preflight [--config PATH]
```

В PR#1 — только `fetch` (default) + `preflight`. `--url` обязателен в `fetch`. Subcommand-хранилище оставляем расширяемым — `list-by-tag` появится в адаптерах.

### 3.2 Default behavior

| Условие | stdout | stderr | exit |
|---|---|---|---|
| OK (substantive body) | markdown summary (title + provider_used + body excerpt 500 chars + length stats) | (empty) | 0 |
| DEGRADED (short body / shell / candidate-best) | markdown summary с DEGRADED label + reason | (empty) | 0 |
| FAILED — gated | (empty) | `FETCH_ERROR:GATED url=... gate=login_required\|paid` | 5 |
| FAILED — http error | (empty) | `FETCH_ERROR:HTTP url=... http=403` | 2 |
| FAILED — network | (empty) | `FETCH_ERROR:NETWORK url=... attempts=N` | 3 |
| FAILED — args | (empty) | `FETCH_ERROR:ARGS ...` | 1 |
| FAILED — env / preflight | (empty) | `FETCH_ERROR:ENV ...` | 4 |

`--json`: stdout — envelope в виде `json.dumps(envelope, indent=2)` для **всех** статусов (включая FAILED, чтобы machine-callers видели telemetry). Markdown summary в этом случае не печатается. Stderr `FETCH_ERROR:*` пишется независимо от флага (legacy-fail-loud).

**Combo `--json` + FAILED gated:** stdout содержит full envelope (с `status: FAILED`, `content_gate: login_required|paid`, `telemetry.attempts`). Stderr содержит `FETCH_ERROR:GATED url=... gate=...`. Exit code 5. Покрывается тестом #4-json в §8.

**`--keep-raw` flag:**

| `--keep-raw` | `metadata.raw_html_path` | Файл на диске |
|---|---|---|
| Off (default) | `null` | Raw HTML не сохраняется. После extraction отбрасывается. |
| On | абсолютный путь к `~/.h2t/research/{project}-fetch-{slug}-{date}.raw.html` | Сохраняется raw HTML провайдера, который сработал (последняя удачная attempt'а). Для FAILED — raw last attempt'ы. Размер не лимитирован в PR#1. |

Адаптеры (#104/#105) ставят `--keep-raw` под капотом, чтобы делать site-specific selector-based парсинг на DOM. Generic CLI пользователь обычно не нуждается в raw — поэтому default off.

**Exit code 5 — новый.** Мотивация: gated-content — не баг скрипта (request не сломан), но и не recoverable retry. Caller должен различать "сеть упала" (exit 3) от "контент legitimately gated" (exit 5). 4 уже занят preflight, 0/1/2 заняты.

### 3.3 Backward compat

`fetch_url.py` — новый файл, существующих consumers нет. Backward-compat ограничения отсутствуют. Но envelope-shape должна быть stable с момента merge: следующие PR могут только **добавлять** поля, не удалять/переименовывать. `envelope_version: "1"` фиксируем; breaking changes требуют `envelope_version: "2"`.

---

## 4. Envelope Schema

### 4.1 Shape

```json
{
  "status": "OK | DEGRADED | FAILED",
  "url": "https://...",
  "final_url": "https://...",
  "provider_used": "direct | jina | playwright | crawl4ai | firecrawl | browserless | none",
  "content_type": "article | listing | js_shell | gated | short_body | unknown",
  "content_gate": "none | login_required | paid | unknown",
  "title": "...",
  "body_markdown": "...",
  "body_text": "...",
  "body_chars": 4321,
  "links": [
    {"href": "https://...", "text": "...", "rel": "next"}
  ],
  "metadata": {
    "canonical_url": "...",
    "site": "alltd.org",
    "lang": "en",
    "detected_reason": null,
    "site_adapter": null
  },
  "telemetry": {
    "attempts": [
      {
        "provider": "direct",
        "http": 403,
        "latency_ms": 321,
        "error": "fetch_http_4xx_nonretryable"
      },
      {
        "provider": "jina",
        "http": 200,
        "latency_ms": 1450,
        "error": null
      }
    ],
    "reason_for_degraded": null,
    "reason_for_failed": null,
    "total_latency_ms": 1771,
    "providers_skipped": ["playwright", "crawl4ai"],
    "providers_skipped_reason": {
      "playwright": "not_configured",
      "crawl4ai": "not_configured"
    }
  },
  "meta": {
    "primary_engine": "fetch_ladder",
    "envelope_version": "1",
    "fetch_envelope_version": "1",
    "timestamp": "2026-05-07T12:34:56+00:00",
    "user_agent": "h2t-research-fetch/0.0.1 ..."
  }
}
```

### 4.2 Compatibility with #100 envelope

| Поле | exa_search envelope | fetch_url envelope | Заметка |
|---|---|---|---|
| `status` | `OK\|DEGRADED\|FAILED` | identical | Same semantics. |
| `primary_engine` | `"exa"` (top-level) | `"fetch_ladder"` (под `meta`) | **Различие:** в exa-envelope `primary_engine` top-level; в fetch — внутри `meta`. Причина: top-level в fetch занят полями url/title/body, чтобы CLI consumer мог быстро прочесть статью без vendor-spoof. Для evals/telemetry — `meta.primary_engine` остаётся источником истины. |
| `fallback_engine_used` | top-level | заменено `provider_used` + `telemetry.attempts` | `provider_used` точнее: указывает который из ладдера сработал. |
| `results` | list | заменено flat-полями (title/body/links) | Нет смысла в list[1] для single-URL fetch. Адаптер `list-by-tag` (#105) использует **другой** envelope-вариант — см. §11. |
| `telemetry.attempts[*].engine` | `"exa"` | заменено `"provider"` (`direct\|jina\|...`) | Семантика одинаковая, имя более точное для контекста. |
| `meta.envelope_version` | `"1"` | `"1"` | Same. Дублируется как `meta.fetch_envelope_version` для кросс-схемы dispatch'а consumer'ами, которым важно различать exa vs fetch. |
| `telemetry.total_latency_ms` | sum of attempts | identical | |
| `telemetry.total_cost_usd` | float | **отсутствует в PR#1** | Direct/Jina free; добавится при включении paid providers в follow-up. |

`build_envelope` из `exa_search.py` **не используется** напрямую — schema различная. Реализуем `build_fetch_envelope` в `fetch_url.py`. Если позже окажется, что shared-builder нужен — рефакторим в общий модуль.

### 4.3 `status` Decision Matrix

| Условие | `status` | exit | `content_type` | `content_gate` |
|---|---|---|---|---|
| Substantive body, ≥1 substantive provider успешен | `OK` | 0 | `article` или `listing` (детектит классификатор) | `none` |
| Все провайдеры вернули short body / JS shell, **нет** gated-сигнала | `DEGRADED` | 0 | `js_shell\|short_body\|unknown` | `none\|unknown` |
| Login/paid wall детектится | `FAILED` | 5 | `gated` | `login_required\|paid` |
| HTTP 4xx (кроме 401/403 → определяется как gated) на всех провайдерах | `FAILED` | 2 | `unknown` | `none` |
| HTTP 5xx на всех провайдерах после retries | `FAILED` | 2 | `unknown` | `none` |
| Network timeout / URLError на всех | `FAILED` | 3 | `unknown` | `none` |
| Args validation | `FAILED` | 1 | n/a | n/a |
| Preflight / env error | `FAILED` | 4 | n/a | n/a |
| Malformed response (e.g. Jina вернул не-utf8 / не-markdown) | `FAILED` | 2 | `unknown` | n/a |

**HTTP 401/403 trick:** изначально классифицируются как HTTP-fail, **но** если direct-провайдер видит `WWW-Authenticate` header или login-redirect — конвертируется в `gated`. См. §6.4.

### 4.4 `content_type` Classifier

| Сигналы | `content_type` |
|---|---|
| `body_chars >= min_body_chars` И есть `<article>`/`<main>` или Trafilatura успешно извлекла | `article` |
| Много `<a>` внутри `<ul>/<li>` относительно текста, тег `<title>` похож на rubric | `listing` |
| `body_chars < 200` И present `<script src="...">` ≥ 5 (типичная SPA-страница) | `js_shell` |
| `body_chars < min_body_chars`, но не SPA | `short_body` |
| Login form / WWW-Authenticate / known-paywall token | `gated` |
| Иначе | `unknown` |

`detect_js_shell` в PR#1 — простая эвристика: `body_text < 200 chars AND len(soup.find_all("script")) >= 5`. Расширяется в адаптерах.

---

## 5. Provider Ladder

### 5.1 Default order для `--provider auto`

```
1. direct                       (always enabled — no way to disable without --provider override)
2. jina                         (enabled by default; disabled only if config.jina.enabled: false)
3. playwright                   (PR#1: stub, never enabled — see §5.5)
4. crawl4ai                     (PR#1: stub, never enabled)
5. firecrawl                    (PR#1: stub, never enabled — but config gate documented for follow-up)
6. browserless                  (PR#1: stub, never enabled)
```

В PR#1 active providers ладдера = **`direct` + `jina`**. Все остальные — stubs, skipped с reason `not_configured_stub` (или `disabled_in_config` если выключен явно). Это упрощает scope первого PR и оставляет ladder-architecture готовой к расширению.

`--provider <name>` — single-provider mode, ladder отключён. Для `<name>` в `{playwright, crawl4ai, firecrawl, browserless}` (любой stub) → `FETCH_ERROR:ARGS provider=<name> not configured (stub in this version)`, exit 1.

### 5.2 Per-provider hard timeout

Default: 15000 ms на провайдера, override через `--timeout-ms`. Ladder cumulative cap: `4 × timeout-ms` (т.е. `60s` default). При превышении cumulative — текущий провайдер довыполняется или прерывается (зависит от провайдера; для urllib — `socket.timeout`), оставшиеся skip с reason `cumulative_timeout_exhausted`.

### 5.3 Direct provider

Реализация — stdlib `urllib.request`, без `requests`/`httpx` (та же конвенция, что у `exa_search.py`).

```python
def direct_fetch(url, timeout_ms, user_agent) -> ProviderResult:
    req = Request(url, headers={"User-Agent": user_agent, "Accept": "text/html,..."})
    with urlopen(req, timeout=timeout_ms/1000) as resp:
        body = resp.read()
        ctype = resp.headers.get("Content-Type", "")
        ...
    # 200 → extract markdown via trafilatura (or fallback) + classify
    # 401/403 with WWW-Authenticate → gated:login_required
    # 401/403 without auth header → just http_4xx_nonretryable (NOT gated)
    # 5xx → http_5xx_retryable (но retry на уровне ladder, не direct)
    # 429 → http_5xx_retryable (semantic alias)
    # URLError / timeout → fetch_network_timeout
```

**Extraction strategy (PR#1):**

- **Baseline (always works, no deps):** inline parser на stdlib `html.parser` + минимальный HTML→markdown converter (см. §10.1). Покрывает большинство `<article>`-style pages "достаточно хорошо".
- **Optional uplift:** если `trafilatura` (https://trafilatura.readthedocs.io/) импортируется в `~/.h2t/venv`, скрипт **поверх** baseline'а пробует `trafilatura.extract()` и берёт результат, если у него больше body chars. Иначе остаётся inline.

**Trafilatura не required.** `pip install trafilatura` — opt-in. Baseline tests, CI, и любой `git clone && pytest` — работают без неё. При первом fetch'е, когда trafilatura недоступна, скрипт пишет однократный `FETCH_WARN:NO_TRAFILATURA inline parser only` в stderr (не блокер; не меняет exit code). Когда установлена — никаких сообщений.

Тесты в §8:
- baseline (`test_direct_ok_extracts_article`) — обязан быть зелёным без install trafilatura.
- trafilatura uplift — отдельный `@pytest.mark.optional` тест `test_trafilatura_used_when_available_uplifts_body` mock'ает import успешным.

### 5.4 Jina Reader provider

```
GET https://r.jina.ai/<URL>
Headers:
  Accept: text/markdown
  X-Return-Format: markdown
  Authorization: Bearer <JINA_API_KEY>   ← optional, free tier работает без
```

Jina возвращает чистый markdown. Парсер в этом случае минимальный: title из первого `# ...` или `<title>` (Jina эмитит `Title:` heading). Длина body — `len(markdown)`.

Особенность: Jina Reader **сам** рендерит JS на их side. Это закрывает большинство IIHQ-кейсов без локального Playwright. Free-tier rate limit ~20 RPM, потому имеет смысл как второй провайдер в ладдере.

**Enable policy (explicit для PR#1):**

| Сигнал | Состояние jina в auto-ладдере |
|---|---|
| Default (нет config-файла) | **Enabled.** `default_jina_enabled = True` зашит в скрипте. Используется free-tier (без `JINA_API_KEY`). |
| `JINA_API_KEY` установлен | Enabled, header `Authorization: Bearer <key>` посылается, ratelimit поднят. |
| Config `providers.jina.enabled: false` | **Disabled.** Skipped в auto, в `telemetry.providers_skipped["jina"] = "disabled_in_config"`. Single-provider mode `--provider jina` всё равно вызывает (явный пользовательский opt-in). |
| Config `providers.jina.enabled: true`, без env-key | Enabled, free-tier. Same как default. |

**Privacy note (для пользователя SKILL.md):** Jina Reader — third-party URL-relay; URL и (для приватных URL) часть содержимого видны Jina'у. Для public web research-сценариев это допустимо; для anything sensitive — отключать через config. Это объясняется в обновлении SKILL.md (§9).

`jina_fetch` raises `ProviderTransientError` на 5xx/429/timeout (retry on next provider step), `ProviderPermanentError` на 4xx (не retryable).

### 5.5 Playwright provider — stub в PR#1

В PR#1 — **stub**, идентичный по поведению с Crawl4AI/Firecrawl/Browserless:

```python
class PlaywrightProvider:
    name = "playwright"
    
    def is_configured(self, env, config) -> bool:
        # Никогда не True в PR#1.
        return False
    
    def fetch(self, url, timeout_ms, user_agent) -> ProviderResult:
        raise ProviderNotConfigured(
            "PlaywrightProvider stub: implementation deferred to follow-up PR. "
            "When implemented, will require: pip install playwright && playwright install chromium."
        )
```

**Почему отложено:** browser-runtime тащит heavy install (~150 MB chromium), удлиняет CI, требует platform-specific бинарник. Direct + Jina покрывают ~80% TD POP failed-harvest backlog (Jina Reader сам рендерит JS). Если post-merge smoke на TD POP URL'ах покажет, что Playwright реально нужен — отдельный issue + spec amendment.

PR#1 поведение: `--provider playwright` → exit 1 `FETCH_ERROR:ARGS provider=playwright not configured (stub in this version)`. В `--provider auto` skipped с `providers_skipped["playwright"] = "not_configured_stub"`.

Тестов на реальный Playwright в PR#1 **нет**. Stub-test покрывает skip-в-ладдере + ошибку при explicit `--provider playwright`.

### 5.6 Crawl4AI / Firecrawl / Browserless — stubs

В PR#1: классы существуют, реализованы как:

```python
class FirecrawlProvider:
    name = "firecrawl"
    
    def is_configured(self, env, config) -> bool:
        return bool(env.get("FIRECRAWL_API_KEY")) and config.get("firecrawl", {}).get("enabled", False)
    
    def fetch(self, url, timeout_ms, user_agent) -> ProviderResult:
        raise ProviderNotConfigured(
            "FirecrawlProvider stub: implementation deferred to follow-up PR. "
            "Set FIRECRAWL_API_KEY + config.firecrawl.enabled=true after implementation."
        )
```

Тесты проверяют, что stub-провайдеры **не** включаются в `auto`-ладдер по умолчанию (даже если env-key выставлен — config-flag должен быть тоже true). Это снижает риск accidental billing.

### 5.7 Provider error classes

```python
class ProviderTransientError(Exception):
    """Retryable within or across providers: 5xx, 429, network timeout, URLError."""

class ProviderPermanentError(Exception):
    """Non-retryable for THIS provider, ladder may try next: 4xx, malformed response."""

class ProviderHardGate(Exception):
    """Bypass forbidden: 401/403 with auth header, paywall token, login redirect.
    Ladder STOPS — does not try further providers."""
    def __init__(self, msg, *, gate: str):  # gate ∈ {login_required, paid}
        ...

class ProviderNotConfigured(Exception):
    """Provider exists but not enabled by config/env. Ladder skips silently
    and records in telemetry.providers_skipped."""
```

---

## 6. Gating, Auth, Robots Policy

### 6.1 Hard rule

**Не обходим auth.** Не передаём cookies, не делаем session impersonation, не используем `--user-agent` для притворства браузером сверх того, что нужно для public-content fetch (default UA — h2t-research-fetch с opt-in URL до репозитория).

### 6.2 Login wall detection

Любой из сигналов → `ProviderHardGate(gate="login_required")`:

- HTTP 401 с `WWW-Authenticate: Basic|Bearer|Digest|...`
- HTTP 200 с `<form>` где `action` matches `/login`/`/signin`/`/auth` И response отсутствует expected article tags
- HTTP 302/303 redirect на `/login` или `/signin` location
- Известные tokens в DOM: `class="login-required"`, `data-paywall="true"`, и т.п. — список в §6.5.

### 6.3 Paywall detection

- HTTP 402 (теоретически)
- DOM-tokens: `data-paid="true"`, `class="paywall-active"`, `<meta name="article:opinion-paid" content="true">`, `Schema.org/Paywall`
- **Известные paywalled domains** (NYT, FT, Bloomberg) — таблица в §6.5; даже без DOM-токена возвращается `paid`. В PR#1 — пустая таблица + расширение в follow-up.

### 6.4 401/403 disambiguation

`HTTP 401 with WWW-Authenticate header` → `ProviderHardGate(gate="login_required")`.
`HTTP 403 with login link in body` → `ProviderHardGate(gate="login_required")`.
`HTTP 403 plain (e.g. Cloudflare/WAF)` → `ProviderPermanentError("fetch_http_4xx_nonretryable")` — не gated, ladder пробует следующего провайдера. Это критично для AllTouchDesigner, где 403 = WAF, не auth.

### 6.5 Tokens & domains lists

Файл `plugins/h2t-ops/skills/research/scripts/_fetch_signals.py` (или константа в `fetch_url.py`):

```python
LOGIN_DOM_TOKENS = [
    'class="login-required"',
    'data-auth="required"',
    'id="login-form"',
]

PAYWALL_DOM_TOKENS = [
    'data-paid="true"',
    'class="paywall-active"',
    'class="article-paywall"',
    'itemtype="https://schema.org/Paywall"',
]

KNOWN_PAYWALLED_DOMAINS: set[str] = set()  # populate в follow-up
```

В PR#1 списки минимальны; расширение по эвиденции.

### 6.6 Robots.txt

**В PR#1 не реализуется.** Спек фиксирует: `fetch_url.py` предполагает, что caller (research agent) уже проверил, что URL legitimate to fetch (через research workflow / manual selection). Robots.txt-чекер — отдельный `--respect-robots` флаг в follow-up issue.

Эта позиция честная: research-pipeline harvest'ит конкретные опубликованные URL'ы (с `--full-text` от Exa, с research-agent links) — это не crawler. Generalised robots-checker нужен для bulk crawling, чего PR#1 не делает.

---

## 7. Configuration

### 7.1 Config file (optional)

`~/.h2t/config/research/fetch_providers.yaml`:

```yaml
providers:
  direct:
    enabled: true
    user_agent: "h2t-research-fetch/0.0.1 (+https://github.com/lichtpfad/h2t-skills)"
    timeout_ms: 15000
  jina:
    enabled: true
    endpoint: "https://r.jina.ai/"
    timeout_ms: 20000
  playwright:
    enabled: false
    timeout_ms: 30000
    headless: true
  crawl4ai:
    enabled: false
  firecrawl:
    enabled: false
    endpoint: "https://api.firecrawl.dev"
  browserless:
    enabled: false
    endpoint: "https://chrome.browserless.io"

ladder:
  default_order: [direct, jina, playwright, crawl4ai, firecrawl, browserless]
  cumulative_timeout_ms: 60000
  per_provider_timeout_ms: 15000
  min_body_chars: 200

gating:
  abort_on_login_required: true
  abort_on_paid: true
```

Если файла нет → дефолты hardcoded в скрипте (см. §5.1). `--config PATH` overrides default location.

### 7.2 Env vars

| Var | Назначение | Required? |
|---|---|---|
| `JINA_API_KEY` | Jina Reader auth (выше rate limits) | Optional |
| `FIRECRAWL_API_KEY` | Firecrawl provider | Required для firecrawl |
| `BROWSERLESS_TOKEN` | Browserless | Required для browserless |
| `H2T_PYTHON` | resolved by SKILL.md | inherited |

Env-keys никогда не required для baseline tests. Тесты, требующие реальных ключей, помечены `@pytest.mark.optional` и читают `os.environ` lazily.

---

## 8. Tests

### 8.1 Расположение

`plugins/h2t-ops/skills/research/tests/test_fetch_url.py` + fixtures под `tests/fixtures/fetch/`.

### 8.2 Network/browser policy

- **Все unit-тесты — без сети**. Mock `urllib.request.urlopen` для direct/jina.
- **Никаких paid-API ключей** в baseline.
- **Никаких browser-runtime install** в baseline. Playwright — stub в PR#1; тестов на реальный browser нет.
- **Trafilatura — НЕ требуется для baseline**. Все основные тесты должны проходить без неё установленной. Inline parser — обязательная baseline-extraction. Тесты, относящиеся к trafilatura uplift, помечены `@pytest.mark.optional` и `monkeypatch`-ят `import trafilatura` как успешный (не требуют реального install).
- **CI green criteria:** `pytest plugins/h2t-ops/skills/research/tests/test_fetch_url.py` зелёный на чистом `~/.h2t/venv` после `/h2t-core:setup` без дополнительных pip-установок.

### 8.3 Test matrix

| # | Test | Сценарий | Ожидание |
|---|---|---|---|
| 1 | `test_direct_ok_extracts_article` | direct 200 + public_article fixture, **trafilatura НЕ установлена** | status=OK, provider_used=direct, content_type=article, body_chars≥200, extraction = inline |
| 2 | `test_direct_ok_skips_jina` | direct OK | telemetry.attempts.len=1, jina не вызывался |
| 3 | `test_direct_403_falls_through_to_jina` | direct 403 → jina 200+md | status=OK, provider_used=jina, attempts.len=2, attempts[0].error="fetch_http_4xx_nonretryable" |
| 4 | `test_direct_401_with_auth_header_short_circuits` | direct 401 + WWW-Authenticate | status=FAILED, exit=5, content_gate=login_required, jina **не** вызывался |
| 4j | `test_failed_gated_with_json_flag` | direct 401 gated, `--json` | stdout = full envelope (status=FAILED, content_gate=login_required), stderr содержит `FETCH_ERROR:GATED url=... gate=login_required`, exit=5 |
| 5 | `test_jina_5xx_then_no_more_active_providers` | direct 200 short_body → jina 503 (playwright/crawl4ai/firecrawl/browserless = stubs) | status=DEGRADED (best from candidates), provider_used = провайдер с лучшим body, attempts.len=2, providers_skipped содержит остальные с reason="not_configured_stub" |
| 6 | `test_all_active_providers_fail_returns_failed` | direct 503, jina 503 | status=FAILED, exit=2, attempts.len=2 |
| 7 | `test_js_shell_degraded_fallthrough_then_recover` | direct js_shell → jina OK | status=OK, attempts[0].error="fetch_js_shell" |
| 8 | `test_short_body_below_threshold_degraded` | direct 200 + short_body fixture, jina также short, --min-body-chars 200 | status=DEGRADED, content_type=short_body |
| 9 | `test_login_wall_short_circuits` | direct 200 + login_wall fixture | status=FAILED, exit=5, content_gate=login_required, jina не вызван |
| 10 | `test_paywall_short_circuits` | direct 200 + paywall fixture | status=FAILED, exit=5, content_gate=paid |
| 11 | `test_provider_explicit_skips_ladder` | --provider direct, direct 403 | status=FAILED, exit=2, attempts.len=1, jina не вызван |
| 12 | `test_explicit_stub_provider_returns_args_error` | --provider firecrawl (или playwright/crawl4ai/browserless) | exit=1, FETCH_ERROR:ARGS provider=... not configured (stub in this version) |
| 13 | `test_stub_providers_skipped_in_auto` | auto, env пуст, config дефолтный | playwright/crawl4ai/firecrawl/browserless в `providers_skipped` с reason="not_configured_stub"; **никакой исходящий HTTP** к ним не сделан |
| 14 | `test_paid_provider_not_called_when_key_set_but_stubbed` | FIRECRAWL_API_KEY set | firecrawl всё ещё skipped (PR#1 stub игнорирует env), assert mock не вызывалась |
| 15 | `test_envelope_json_flag_to_stdout` | direct OK, --json | stdout — валидный JSON, начинается `{`, markdown summary не печатается |
| 16 | `test_envelope_in_sources_json_always_written` | direct OK, без --json | `.sources.json` содержит `meta.envelope` с правильной shape |
| 17 | `test_failed_envelope_printed_with_json_flag` | all providers fail, --json | stdout печатает FAILED-envelope с telemetry |
| 18 | `test_failed_no_json_flag_stderr_only` | all providers fail, без --json | stdout пуст, stderr содержит `FETCH_ERROR:HTTP url=...` |
| 19 | `test_args_validation_no_url` | без --url | exit=1, FETCH_ERROR:ARGS |
| 20 | `test_preflight_ok` | preflight с mocked HEAD | exit=0 при успехе, exit=4 при недоступности |
| 21 | `test_envelope_version_field_present` | любой OK | envelope.meta.envelope_version == "1", meta.fetch_envelope_version == "1", meta.primary_engine == "fetch_ladder" |
| 22 | `test_provider_used_correct_in_telemetry` | direct OK | provider_used="direct", attempts[0].provider="direct" |
| 23 | `test_total_latency_ms_sums_attempts` | 2 attempts | total_latency_ms == sum(latency) |
| 24 | `test_inline_extraction_baseline_works_without_trafilatura` | trafilatura unimportable, direct OK + public_article fixture | status=OK, body via inline parser, **однократный** `FETCH_WARN:NO_TRAFILATURA` в stderr |
| 24a | `@pytest.mark.optional` `test_trafilatura_used_when_available_uplifts_body` | monkeypatch import trafilatura успешный + сильнее inline | extraction = trafilatura, body_chars ≥ inline result |
| 25 | `test_known_paywall_domain_short_circuits` (PR#1 — пустой список, fixture готов; тест проверяет, что при добавлении домена в KNOWN_PAYWALLED_DOMAINS триггерит gate) | inject domain | content_gate=paid, exit=5 |
| 26 | `test_cumulative_timeout_skips_remaining_active_providers` | mock direct OK с large latency, остальные skipped | telemetry.providers_skipped может содержать active-провайдеров с reason="cumulative_timeout_exhausted"; FETCH_WARN:CUMULATIVE_TIMEOUT_EXHAUSTED в stderr |
| 27 | `test_url_normalization_https_redirect` | direct 301 → 200 | final_url != url, status=OK |
| 28 | `test_html_extraction_unicode_safe` | direct 200 + non-ASCII article | body_text/markdown contain non-ASCII chars без mojibake |
| 29 | `test_telemetry_skipped_reason_for_jina_disabled_in_config` | direct OK, config.providers.jina.enabled=false | jina не в attempts, в `providers_skipped` с reason="disabled_in_config" |
| 30 | `test_keep_raw_off_by_default_no_raw_file` | direct OK, без --keep-raw | `metadata.raw_html_path` is null, `.raw.html` файл не существует |
| 31 | `test_keep_raw_on_writes_raw_file` | direct OK, --keep-raw | `metadata.raw_html_path` указывает на существующий файл с full HTML |
| 32 | `test_keep_raw_on_failed_writes_last_attempt_raw` | all providers fail, --keep-raw | `metadata.raw_html_path` указывает на raw response последней attempt'ы (если был body) или null если все были network-only failures |
| 33 | `test_403_without_auth_header_is_not_gated` | direct 403 без `WWW-Authenticate` (Cloudflare-style 403 fixture) | content_gate=none, error=fetch_http_4xx_nonretryable, ladder проходит к jina |

(Финальное число тестов и порядок утверждаются в plan-stage. Перечисленные — обязательный baseline.)

### 8.4 Fixtures schema

`tests/fixtures/fetch/` — статические HTML-файлы. Один тестовый сервер не поднимаем; fixtures читаются монкипатчем `urllib.request.urlopen`.

| Fixture | Цель |
|---|---|
| `public_article.html` | Базовый article с `<article>`/`<main>`, body ≥ 1000 chars |
| `public_article.markdown.txt` | Ожидаемая markdown-форма после trafilatura (для assert) |
| `public_article_jina.md` | Что Jina Reader вернёт (для mock'а) |
| `js_shell.html` | `<script>` x10, body < 100 chars |
| `short_body.html` | `<article>` с body 50 chars |
| `login_wall.html` | `<form action="/login">`, `<input name="username">` |
| `paywall.html` | `data-paid="true"` token in DOM |
| `alltd_403_body.html` | Cloudflare-style 403 page (для теста disambiguation: НЕ gated) |
| `redirect_to_login.html` | meta-refresh на `/login` |
| `non_ascii_article.html` | UTF-8 non-Latin content |

---

## 9. SKILL.md Changes

### 9.1 New section after "Provider Status Envelope"

```markdown
## Fetching Specific URLs (`fetch_url.py`)

`exa_search.py` находит URL'ы; `fetch_url.py` доставляет их содержимое.

Когда использовать:
- ✅ Известный конкретный URL, нужен полный текст статьи (не только highlight).
- ✅ Plain WebFetch вернул shell / 403 / пустоту.
- ✅ JS-rendered страницы.

Когда НЕ использовать:
- ❌ Поиск по теме (используй `$EXA_CLI search`).
- ❌ Bulk crawl сайта (используй адаптеры — alltd.py, iihq.py — после их реализации).
- ❌ Auth/paid контент. Скрипт вернёт FAILED + content_gate; не пытайся обойти.

CLI:
$FETCH_CLI --url "https://..." [--provider auto] [--json] [--project NAME]

Envelope status (тот же контракт, что у `exa_search.py`):
| envelope.status | Действие агента |
|---|---|
| OK | Continue: synthesize from body_markdown. |
| DEGRADED | Report STATUS: DEGRADED + reason. Можно: (a) попробовать другой --provider (новый CLI вызов), (b) пометить источник failed-harvest и идти дальше. |
| FAILED + content_gate=login_required\|paid | STOP. Не fetch'и через WebFetch. Источник legitimately gated. |
| FAILED иное | STOP. Report exact FETCH_ERROR. |
```

### 9.2 Antipatterns update

Добавить:

- **Bypass auth/paywall via WebFetch fallback** — content_gate=login/paid означает legitimately gated. Substitute via WebFetch — нарушение интегритета.
- **Synthesize article from short_body / js_shell** — если status=DEGRADED, body не пригоден для wiki ingest. Помечай failed-harvest.

### 9.3 Step 0 preflight extension

`fetch_url.py preflight` добавляется к Step 0 (опционально). Проверяет:
1. Reachability `https://r.jina.ai/` (если jina enabled).
2. `trafilatura` import.
3. Optional `playwright` import (warn-only, не блокер).

---

## 10. Implementation Notes

### 10.1 Inline HTML→markdown fallback

Когда trafilatura недоступна:

```python
def _inline_extract(html: str) -> tuple[str, str, dict]:
    """Returns (markdown, text, metadata). Minimal fallback.
    
    Strategy: parse with html.parser, drop <script>/<style>/<noscript>,
    take <article> if present else <main> else <body>, convert to plain
    text by walking children. Markdown = same plain text wrapped with
    H1 from <title>. Honest minimum — лучше чем raw HTML, хуже чем 
    trafilatura, документировано как degraded extraction.
    """
```

Этот fallback покрыт тестом #24. Цель — graceful degradation, не qualitative parity.

### 10.2 `final_url` tracking

`urllib`'s `urlopen` возвращает `response.geturl()` — финальный URL после редиректов. Запоминаем; если `final_url != url`, кладём оба в envelope. Используется для detect login-redirects (если final_url содержит `/login` → gated).

### 10.3 Public API for adapters (#104/#105)

```python
# fetch_url.py exports
__all__ = [
    "fetch_via_ladder",      # high-level: url → envelope
    "build_fetch_envelope",
    "ProviderResult",        # dataclass
    "ProviderTransientError",
    "ProviderPermanentError",
    "ProviderHardGate",
    "ProviderNotConfigured",
    "DirectProvider",
    "JinaProvider",
    "PlaywrightProvider",
    "load_config",
]
```

`#105 alltd.py` импортирует `fetch_via_ladder(url)`, получает envelope, добавляет `metadata.site_adapter = "alltd"`, и — если is_substantive — запускает свой site-specific extractor для `<article>`/tag-list. Если ladder вернул FAILED — адаптер просто прокидывает envelope как есть.

`#104 iihq.py` — то же, но плюс site-specific signals для IIHQ-paywall.

### 10.4 Sidecar files

Аналогично `exa_search.py`:

- `~/.h2t/research/{project}-fetch-{slug}-{date}.partial.md` — markdown summary (только для OK/DEGRADED).
- `~/.h2t/research/{project}-fetch-{slug}-{date}.sources.json` — `{meta, envelope, body}`. Для FAILED — без body, только envelope. Slug = sanitized hostname + path-tail.

### 10.5 Versioning

- `fetch_url.py __version__ = "0.0.1"` — новый файл, начинаем с 0.0.x.
- `plugins/h2t-ops/skills/research/SKILL.md metadata.version` бамп с `0.1.1` → `0.1.2` (patch — добавляем новый CLI без breaking changes).
- `plugins/h2t-ops/.claude-plugin/plugin.json version` бамп `1.1.1` → `1.1.2` (patch).
- Per user CLAUDE.md: **никаких minor бампов до live-подтверждения** на реальных URL'ах из TD POP backlog.

### 10.6 Dependency declaration

PR#1 имеет **ноль** обязательных pip-зависимостей сверх stdlib. `trafilatura` — opt-in extraction uplift; baseline inline parser работает на чистом `~/.h2t/venv`.

В SKILL.md `compatibility:` поле обновляется:

```yaml
compatibility: "Requires $EXA_API_KEY env var. Get key at https://dashboard.exa.ai/api-keys. Requires ~/.h2t/venv (run /h2t-core:setup if missing). Optional: pip install trafilatura inside ~/.h2t/venv for richer article extraction (script falls back to stdlib inline parser if absent)."
```

Никаких изменений в `/h2t-core:setup` PR#1 не требует.

---

## 11. Reuse Plan для #104 / #105

### 11.1 Shared core

Адаптеры импортируют из `fetch_url`:

```python
from fetch_url import fetch_via_ladder, build_fetch_envelope, ProviderHardGate
```

И запускают свой extraction поверх envelope:

```python
def alltd_fetch_article(url: str) -> dict:
    envelope = fetch_via_ladder(url)
    if envelope["status"] == "FAILED":
        return _wrap_with_adapter_metadata(envelope, "alltd")
    
    # Re-extract with site-specific selectors (DOM available in metadata.raw_html
    # — or re-fetch markdown body and re-parse).
    enriched = _alltd_extract(envelope["body_markdown"], envelope["url"])
    envelope["title"] = enriched.title
    envelope["metadata"]["author"] = enriched.author
    envelope["metadata"]["date"] = enriched.date
    envelope["metadata"]["site_adapter"] = "alltd"
    return envelope
```

**Resolved для PR#1:** `metadata.raw_html_path` есть в envelope всегда. Default — `null` (raw HTML не сохраняется, отбрасывается после extraction). С флагом `--keep-raw` пишется файл `~/.h2t/research/{project}-fetch-{slug}-{date}.raw.html` и path кладётся в envelope. Адаптеры (#104/#105) включают `--keep-raw` под капотом. Тесты #30–32 в §8 покрывают оба режима.

### 11.2 Adapter envelope extension

Адаптер envelope = base envelope + дополнительные поля под `metadata`:

```json
{
  ...base envelope...,
  "metadata": {
    ...base metadata...,
    "site_adapter": "alltd",
    "author": "...",
    "date": "...",
    "tags": [...]
  }
}
```

`#105 alltd list-by-tag` — **отдельный** envelope-вариант (list of stubs):

```json
{
  "status": "OK | DEGRADED | FAILED",
  "site_adapter": "alltd",
  "subcommand": "list-by-tag",
  "tag": "pops",
  "items": [
    {"title": "...", "url": "...", "author": "...", "date": "..."}
  ],
  "telemetry": {...}
}
```

Это **не** ломает PR#1 — адаптер сам вводит свою schema; base `fetch_url` остаётся single-URL.

### 11.3 Implementation order для downstream

PR#1 (этот спек, #103): core fetch_url.py
PR#2 (#105 AllTouchDesigner): отдельный спек, отдельный плэн, импортирует из fetch_url
PR#3 (#104 IIHQ): то же, после #105 для maturity ladder

---

## 12. Acceptance Criteria

Из issue #103 + добавленные в спеке:

- [ ] Spec написан до кода — **этот документ**
- [ ] CLI `fetch_url.py` существует, callable independently
- [ ] Envelope включает `status / provider_used / telemetry / content_gate / content_type / metadata.raw_html_path`
- [ ] Baseline tests **не требуют** paid keys / browser install / network / pip-install сверх stdlib
- [ ] Нет hard dep на Firecrawl / Browserless / Crawl4AI / Playwright (все stubs в PR#1)
- [ ] Issue #98 закомментирован с финальной ladder-design (post-merge step)
- [ ] SKILL.md секция объясняет когда `fetch_url.py` vs `exa_search.py search/crawl`, плюс privacy note по Jina
- [ ] `envelope_version: "1"` совместим с merged #100 schema (status semantics одинаковы)
- [ ] Auth/paywall detection не bypass'ит — гарантия в тестах #4, #4j, #9, #10
- [ ] Provider attempts видимы в `telemetry.attempts` — гарантия в тестах #2, #3, #6, #22, #23
- [ ] Stub providers (playwright/crawl4ai/firecrawl/browserless) не вызывают исходящий HTTP — гарантия в тестах #13, #14
- [ ] Inline extraction baseline зелёный без trafilatura — гарантия в тесте #24
- [ ] Trafilatura uplift корректен когда установлена — гарантия в тесте #24a (optional mark)
- [ ] `--keep-raw` flag default off / on writes raw — гарантия в тестах #30, #31, #32
- [ ] Combo `--json + FAILED gated` — гарантия в тесте #4j
- [ ] 403 без auth header не классифицируется как gated — гарантия в тесте #33

---

## 13. Open Questions

### Resolved до plan-stage (закрыто review 2026-05-07)

1. ✅ **Trafilatura vs inline?** → **Inline baseline always; trafilatura opt-in uplift.** Никаких pip-deps в PR#1. Тесты не требуют trafilatura.
2. ✅ **Playwright в PR#1?** → **Stub.** Browser-runtime отложен в follow-up issue после post-merge smoke на TD POP backlog.
3. ✅ **`--respect-robots` flag в PR#1?** → **Нет.** PR#1 предполагает, что caller (research agent) selects URL'ы legitimately; bulk-crawl-checker — отдельный issue.
4. ✅ **`--keep-raw` flag** → **В PR#1, default off.** Адаптеры (#104/#105) включают опцию. См. §3.2 / §11.1 / тесты #30–32.
5. ✅ **`FETCH_WARN:CUMULATIVE_TIMEOUT_EXHAUSTED`** → **Да**, печатается в stderr при skip remaining providers. Не блокер, exit code не меняется. Покрыто тестом #26.

### Остаются открытыми (решает plan-author или отдельный issue)

A. **Cache layer (per-URL cache по hash)?** Не в этом PR. Sidecar `.sources.json` уже даёт post-hoc retrieval; full cache — отдельная Phase-2 задача.
B. **`KNOWN_PAYWALLED_DOMAINS` initial seed.** В PR#1 — пустой. Когда появится первый use-case (адаптер или real-world block) — добавляется domain + тест. Плану писать пустой список.
C. **`--user-agent` polite default vs `Mozilla` impersonation.** Спек выбрал polite identifying UA. Если AllTouchDesigner/Cloudflare блокирует polite UA — это smoke-finding для follow-up, не PR#1 blocker. Не impersonate без эвиденции.

---

## 14. References

- Issue #103: https://github.com/lichtpfad/h2t-skills/issues/103
- Parent ladder #98: https://github.com/lichtpfad/h2t-skills/issues/98
- Phase-2 umbrella #97: https://github.com/lichtpfad/h2t-skills/issues/97
- Provider envelope merged PR #106: https://github.com/lichtpfad/h2t-skills/pull/106
- Envelope spec: `docs/superpowers/specs/2026-05-07-research-provider-envelope.md`
- ADR-0005 Candidate 3: `C:/work/TD/docs/adr/0005-phase-2-script-extraction-backlog.md`
- TD POP failed-harvest evidence:
  - `C:/work/TD/corpus/td-pop/manifest.jsonl`
  - `C:/work/TD/pipeline-log/td-pop/0003-iteration-3-harvest.md`
  - `C:/work/TD/wiki/sources/td-pop/_approved-harvest.md`
  - `C:/work/TD/docs/reports/2026-05-07-source-recovery-backlog.md`
- Provider docs:
  - Trafilatura: https://trafilatura.readthedocs.io/
  - Jina Reader: https://jina.ai/reader/
  - Crawl4AI: https://docs.crawl4ai.com/core/quickstart/
  - Firecrawl scrape: https://docs.firecrawl.dev/advanced-scraping-guide
  - Browserless Smart Scrape: https://docs.browserless.io/rest-apis/smart-scrape
- Existing `exa_search.py` envelope: `plugins/h2t-ops/skills/research/scripts/exa_search.py` lines 168–389
- SKILL.md envelope section: `plugins/h2t-ops/skills/research/SKILL.md` §"Provider Status Envelope"
