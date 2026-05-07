# ~/.dor/secrets/ — h2t Secrets Vault

This directory is the canonical home for all h2t skill secrets. Loader:
`plugins/h2t-core/scripts/h2t_secrets.py`.

## Layout

```
~/.dor/secrets/
  README.md              # this file
  secrets.env            # KEY=VALUE pairs
  google/                # OAuth JSONs (Gmail, Calendar, Drive)
  meetgeek/              # MeetGeek blobs (if any)
  telegram/              # Telethon session
```

## secrets.env format

Standard dotenv. One `KEY=VALUE` per line. Comments start with `#`.
Quoted values are stripped (both `"..."` and `'...'`). No multiline values.

```env
# Exa search (https://dashboard.exa.ai/api-keys)
EXA_API_KEY=<uuid>
EXA_API_KEY_BACKUP=<uuid>

# Google Gemini (https://aistudio.google.com/apikey)
GEMINI_API_KEY=<key>

# MeetGeek (https://meetgeek.ai/settings/api)
MEETGEEK_API_KEY=<key>
MEETGEEK_BASE_URL=https://api.meetgeek.ai
MEETGEEK_TIMEOUT=30
MEETGEEK_MAX_PAGES=1000
MEETGEEK_WEBHOOK_SECRET=<secret>
```

## Loader behaviour

- Reads file at startup of every Python skill that calls `h2t_secrets.bootstrap()`.
- **Shell-exported env vars take precedence.** If `EXA_API_KEY` is already in `os.environ` (e.g. set in `.bashrc`), the value in `secrets.env` is ignored. This allows ad-hoc experimentation without editing the file.
- Fail-loud if `secrets.env` is missing.
- ValueError on malformed lines (with line number).
- `H2T_SECRETS_FILE` env var override is supported (used by tests).

## Rotation

| Key | Source | Test command |
|---|---|---|
| `EXA_API_KEY` / `EXA_API_KEY_BACKUP` | https://dashboard.exa.ai/api-keys | `~/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/research/scripts/exa_search.py preflight` |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey | (no built-in preflight; run any Gemini-using skill) |
| `MEETGEEK_API_KEY` | https://meetgeek.ai/settings/api | `python plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py meetings --limit 1` |

## Multi-machine

`~/.dor/` is Syncthing-synced between AUTOMATA and MacBook Pro 3 → identical layout, identical keys on both. No need to re-enter on each machine.

## Distribution safety

This directory is **never** committed to any h2t repo. The loader (which IS in the repo) just gives you the convention; the actual key values stay on your machine. When publishing skills externally, distribute loader + this README; the user creates their own `~/.dor/secrets/` from scratch.

## Adding a new key

1. Edit `secrets.env`, add `NEW_KEY=value` line.
2. Update this README's rotation table.
3. (Future) `h2t-core:setup --secrets` will automate this once issue #112 lands.
