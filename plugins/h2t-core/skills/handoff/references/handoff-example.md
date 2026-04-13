# Handoff Output Example

This is the canonical format for handoff summaries. Follow it exactly.

---

## Handoff: dev-h2t-evals-m13-deploy-2026-04-13

### Что сделано

- Диагностировал падение CI (#92): FK violation в test_process_one_job_success — mock возвращал candidate_id=42, которого нет в gt_candidates
- Создал migration 015_drop_optimizer_jobs_candidate_fk.sql — убрал FK на optimizer_jobs.candidate_id (audit-поле, без DB-level integrity)
- Починил deploy.sh permissions на VPS (chmod +x), CI зазеленел
- Migrations 014 + 015 применены на VPS, optimizer_jobs таблица активна без FK
- Создал API токен для optimizer-worker (64a2872d), добавил H2T_EVALS_WORKER_TOKEN в .env на VPS; воркер стартует и шатдаунится чисто
- M13 onboarding h2t-transcription: токен cf9d2fb3, 2 кастомные метрики зарегистрированы, eval-gate.yml переписан под evals.lichtpfadstudio.com; eval-gate CI зелёный (25s)

### Что передаём в следующую сессию

- [ ] Лендинг evals.hou2touch.ai — нужен отдельный чат (Caddy route + страница)
- [ ] Настроить optimizer-worker как постоянный процесс на VPS (docker restart policy или systemd)
- [ ] #73 gt label-ui UX pass 2 — запаркован

### Артефакты

- commit: 2c00d2d (migration 015, h2t-evals)
- commit: ccdf736 (eval-gate update, h2t-transcription)
- file: migrations/pg/015_drop_optimizer_jobs_candidate_fk.sql
- file: h2t-transcription/.github/workflows/eval-gate.yml
