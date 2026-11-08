# Handoff Output Example

This is the canonical format for handoff summaries. Follow it exactly.

---

## Handoff: dev-my-service-deploy-2026-04-13

### Что сделано

- Диагностировал падение CI (#92): FK violation в test_process_one_job_success — mock возвращал candidate_id=42, которого нет в таблице candidates
- Создал migration 015_drop_jobs_candidate_fk.sql — убрал FK на jobs.candidate_id (audit-поле, без DB-level integrity)
- Починил deploy.sh permissions на сервере (chmod +x), CI зазеленел
- Migrations 014 + 015 применены на сервере, таблица jobs активна без FK
- Создал API токен для worker, добавил WORKER_TOKEN в .env на сервере; воркер стартует и шатдаунится чисто
- Onboarding клиентского проекта: токен создан, 2 кастомные метрики зарегистрированы, gate.yml переписан под api.example.com; gate CI зелёный

### Что передаём в следующую сессию

- [ ] Лендинг для сервиса — нужен отдельный чат (reverse-proxy route + страница)
- [ ] Настроить worker как постоянный процесс на сервере (docker restart policy или systemd)
- [ ] #73 label-ui UX pass 2 — запаркован

### Артефакты

- commit: <sha> (migration 015, my-service)
- commit: <sha> (gate update, my-client)
- file: migrations/pg/015_drop_jobs_candidate_fk.sql
- file: my-client/.github/workflows/gate.yml
