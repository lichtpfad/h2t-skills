# Credential Sync Policy

This repo treats credentials as runtime machine/user state, not repository
state.

## Canonical Layout

Runtime key-value secrets live in:

```text
~/.dor/secrets/secrets.env
```

The legacy file remains supported as a fallback during migration:

```text
~/.dor/secrets.env
```

`H2T_SECRETS_FILE` can point a process or test run at an explicit env file.
Shell-exported environment variables still win over file values.

## What Can Sync Between Machines

These may be synced by Syncthing or another private machine-to-machine channel:

- API keys in `~/.dor/secrets/secrets.env`
- non-secret registry/docs about where keys come from
- per-user config that is intentionally shared across machines

Never commit real key values to this repository.

## What Should Stay Per-Machine

Some credentials are session/device state and should be generated on each
machine:

- Google OAuth token files used by Gmail/Calendar/Drive
- Telegram Telethon session files
- browser/device-bound auth state

If a token/session is missing on a new machine, run the provider auth/bootstrap
flow on that machine instead of copying a stale session file.

## Setup Responsibility

`h2t-core:setup` owns onboarding and repair guidance:

- install/repair the `~/.h2t/venv` runtime used by legacy skills;
- install/repair the `h2t-ops` CLI where needed;
- check for required secret files;
- guide explicit provider re-auth for per-machine OAuth/session credentials.

An interactive secrets wizard remains a separate backlog item (#112). The
current closure target is the policy and loader behavior, not a full setup UI.

## Connector Responsibility

`h2t-ops` connectors and legacy scripts should read secrets in this order:

1. existing process environment;
2. `H2T_SECRETS_FILE` if set;
3. `~/.dor/secrets/secrets.env`;
4. legacy `~/.dor/secrets.env`;
5. provider-specific token files where applicable.

This keeps existing Windows installs working while making the Mac path explicit.
