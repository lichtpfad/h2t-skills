# Social Connector

Instagram and Threads accounts over the Meta Graph API and the Threads API. This version
reads profiles, posts and per-post metrics, summarizes them, and records every run in a
journal. Its Graph calls are read-only: it never posts, replies, deletes or changes anything
on a network. Two local maintenance commands exist besides the reads: `schedule` (Windows
Task Scheduler) and `tokens refresh` (Threads token upkeep).

## Command Map

| intent | command |
| --- | --- |
| find the accounts the tokens can reach | `h2t-ops social accounts discover --json` |
| save them to `accounts.yaml` (merge) | `h2t-ops social accounts discover --write --json` |
| list the accounts (id, enabled, project, token_key) | `h2t-ops social accounts list --json` |
| smoke test: profile and last 3 posts per enabled account | `h2t-ops social check --json` |
| the same for one account | `h2t-ops social check instagram:acme --json` |
| collect metrics and summarize | `h2t-ops social run insights --json` |
| the same, mirrored into SQLite (`<data>/social/social.db`); `--trigger cli\|schedule` labels step 1 | `h2t-ops social run insights --store --trigger schedule --json` |
| run insights daily at HH:MM in Windows Task Scheduler | `h2t-ops social schedule add insights --daily 07:00` |
| remove that task | `h2t-ops social schedule remove insights` |
| refresh Threads tokens that expire within 7 days | `h2t-ops social tokens refresh --json` |
| one account, N posts (`--limit` must be 1 or more; default 120) | `h2t-ops social run insights --account threads:acme --limit 25 --json` |
| show journal records | `h2t-ops social journal --last 20 --json` |
| the records of one run | `h2t-ops social journal --run <run_id> --json` |

An account id is `<network>:<handle>`, for example `instagram:acme`. `discover --write`
writes new accounts as `enabled: false` and keeps the `enabled` and `project` values
already in the file. After it, edit `accounts.yaml`: set `enabled: true` (and optionally
`project`) on the accounts to use. Then run `social check`, and only then the first
`run insights`; `check` fails with "no enabled accounts" until one is enabled.

## Config files

Both live under the config dir (`h2t-ops paths get` prints it) in `social/`. A file
holds key names only: a `token`/`access_token` key or a token-shaped value is refused
with a config error.

`accounts.yaml`:

```yaml
api:                       # optional override of the API base URLs
  meta_graph: https://graph.facebook.com/v27.0
  threads_graph: https://graph.threads.net/v1.0
accounts:
  - network: threads      # instagram | facebook | threads
    handle: acme
    remote_id: "123"
    token_key: THREADS_TOKEN_ACME   # the secret's key name, never its value;
                                    # THREADS_* for threads, META_* for instagram/facebook
    project: null         # optional project id from your domains
    enabled: true
  - network: instagram
    handle: acme
    remote_id: "456"      # the Instagram account id
    page_id: "789"        # the linked Facebook Page
    token_key: META_H2T_SOCIAL_USER_TOKEN
```

`rules.yaml` (hand-written; read by the decision step, see "Journal"):

```yaml
rules:
  - id: r1
    process: insights
    action: reply          # the action the rule governs
    account: "*"           # default "*"
    kind: "*"              # default "*"
    verdict: ask           # auto | ask | deny
    added: "2026-11-19"
    origin: <the example this rule came from>   # required
```

Without a matching rule the verdict is `ask`; the more specific rule wins (an exact
account counts before an exact kind).

An `api` override must be a plain `https://` URL: a query, fragment or user info is a
config error. A `token_key` of the wrong provider for its network (a `THREADS_*` key on
an Instagram account, or the reverse) is a config error too.

`run insights` also needs a `timezone` setting (`h2t-ops settings get timezone`); posts
are grouped by weekday and hour band in that zone.

## Secrets

Only through the package, never in a config file, a command line or the output.

| file (under `secrets/shared/`) | keys |
| --- | --- |
| `meta.env` | `META_H2T_SOCIAL_USER_TOKEN`, `META_H2T_SOCIAL_APP_SECRET` |
| `threads.env` | `THREADS_TOKEN_<HANDLE>`, one per Threads profile (handle upper-case) |

The key names come from config, not code: defaults in the package's `social/defaults.yaml`
(`secrets:`), overridable in `accounts.yaml` with the same block. Below, each key is
named by its default; an override replaces it everywhere.

```yaml
secrets:                    # optional; key NAMES only, each must keep its META_/THREADS_ prefix
  meta_user_token: META_H2T_SOCIAL_USER_TOKEN
  meta_app_secret: META_H2T_SOCIAL_APP_SECRET
  threads_token_prefix: THREADS_TOKEN_
```

An empty value, a key of the wrong provider or an unknown name is a config error.

`discover` reads `META_H2T_SOCIAL_USER_TOKEN` and every `THREADS_TOKEN_*`. With neither set it exits
3 (config); with tokens set but no account found it exits 1. A Facebook Page gets the
handle `<page name as lower-case words joined by _>`; two Pages with the same handle both
get `_<page_id>` added. Page tokens are not
stored: they are fetched at run time from `me/accounts` with `META_H2T_SOCIAL_USER_TOKEN`.

## Getting the tokens

Meta (Instagram and Facebook), once per app:

1. In your Meta app, open the Graph API Explorer, pick the app and a User token, and
   grant the Instagram and Page read permissions the app has.
2. Exchange that short-lived token for a long-lived one: `GET /oauth/access_token` with
   `grant_type=fb_exchange_token`, the app id, `META_H2T_SOCIAL_APP_SECRET` and the short token.
3. Put the result in `meta.env` as `META_H2T_SOCIAL_USER_TOKEN`, with
   `META_H2T_SOCIAL_APP_SECRET`. Do not
   paste either value into a chat, a command line or a file in a repo.

Threads, per profile:

1. In the app's Threads use case, open **User Token Generator**, add the profile as a
   tester if needed, and generate a token for it.
2. Put it in `threads.env` as `THREADS_TOKEN_<HANDLE>`.
3. Run `social accounts discover --write`, then set `enabled: true` on the account.

## Journal

Every run is recorded in an append-only JSONL journal (`social/journal.jsonl` under the
data dir). Every record carries all of: `id`, `ts`, `run_id`, `process`, `step`, `channel`,
`account`, `action`, `source_ids`, `context_refs`, `rule_id`, `decision`, `approved_by`,
`result` (`remote_id`, `url`, `error`) and `task_id`; a value that does not apply is `null`
or `[]`. The `step` says what the record is:

| step | meaning |
| --- | --- |
| 1 | the run starts: process, trigger |
| 2 | one record per raw API body; `source_ids` point into the raw zone |
| 3 | the finding for an account; `source_ids` of the bodies it rests on |
| 4 | the decision: `rule_id` and `noop`/`auto`/`ask`/`deny` |
| 5 | a claim; it must name at least one source id |
| 6 | the outcome: the per-account result (`schema_version`, `posts`), or the failure in `result.error` |

A run that fails (bad token, network, rate limit, no data, a write error) ends with exactly
one step-6 record whose `result.error` is `<ErrorClass>: <message>`; the error bodies the
API returned are journaled as step 2 before it. `social journal` exits 5 when there is
nothing to show.

Raw API bodies are kept in `social/raw/<process>/<YYYY-MM-DD>.jsonl`, also append-only.
Token fields are stripped from them, and a record containing a secret value is refused.
`discover` and `check` write steps 1, 2 and 6 only. `run insights` writes 1 to 4 and 6;
its step 4 is always `noop` because this version takes no action. `tokens refresh` is a
maintenance run: it makes no decision, so it writes steps 1, 2 and 6 only. `run insights`
returns its result as JSON (`result.schema_version` is `h2t_social_insights/v1`) and writes
no report file. With `--store` the run is also mirrored into SQLite: journal, raw bodies and
one `results` row per account, written after the whole run succeeded. If the SQLite mirror
fails, mirroring stops for that run, the JSONL journal still ends with a step-6 failure, and
the original error is raised.

## Schedule and token upkeep

`schedule add insights --daily HH:MM` registers the task `h2t-social-insights` in Windows
Task Scheduler; it runs `h2t-ops social run insights --trigger schedule --store`. `h2t-ops`
must be on PATH. Other platforms get a usage error until the VPS stage.

`tokens refresh` refreshes every Threads token that expires within 7 days or has no recorded
expiry. Expiry dates live in `state/social/token-expiry.json` (key names and ISO dates, no
token values). If the API gives no usable `expires_in`, the new token is still saved, the
expiry is recorded as unknown (`null`) and the next run refreshes it again. A token key set in the process
environment makes the command refuse (config error): the environment would override the
refreshed value. A corrupt expiry file is a config error naming the file.

`h2t-ops setup connectors-check` has a `social` row: each social secret key with the layer it
is read from (`env`, `shared`, `legacy`) or `missing`. No secret value is printed.

## Not built yet

- Facebook Page insights: a `facebook` account is skipped by `run insights` and the
  skip is reported.
- Any write to a network (posting, replying, deleting).
- A command to add a rule: edit `rules.yaml` by hand.

## Common Failures

- An enabled account with no posts that carry metrics fails the whole run
  (`no data for <account>`); disable the account or fix the token.
- `no accounts file`: run `social accounts discover --write`.
- `no page matches this account` (Instagram): the Page behind it is missing from
  `me/accounts`; check `page_id` and the token's Page permissions.
- `no timezone configured`: set `timezone` in `user.yaml`.
