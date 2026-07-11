# h2t-core Changelog

## 3.2.13 — 2026-07-11

- eval fallback: `H2T_EVALS_MODE` (auto/off/local/push, default auto); off-by-default
  for adopters without h2t-evals; `h2t-ops evals status`. BREAKING: default is no longer
  implicit local-write — set `H2T_EVALS_MODE=local` to keep local-only telemetry.
