# Autonomous Plan Execution

Область: только автономное/unattended исполнение многошагового плана
(overnight, «выполни план сам»). НЕ для интерактивной работы и мелких фиксов.

1. Gate-ревью плана (консул судей + codex-проход) до старта.
   Исполнять только если гейт пройден.
2. Codex-валидация после каждого нетривиального гейта.
3. Финальный консул реализации в конце.
4. Сломано → чинить → handoff.

Стоимость council/codex реальна — cost-gate из CLAUDE.md остаётся в силе;
это правило не разрешает multi-agent на тривиальных задачах.

## Canonical protocol source

Полные, переносимые определения гейтов и decision-протокола (allow-list + hard-stops) живут в
скилле `h2t-core:autonomous-run` и штампуются в durable runbook-артефакт каждого прогона:

- Гейты (codex review-gate + council finish-gate + pre-merge-check, `N_gate_attempts`):
  `plugins/h2t-core/skills/autonomous-run/references/gates.md`
- Decision-протокол (auto-resolve allow-list deny-by-default + 4 hard-stops):
  `plugins/h2t-core/skills/autonomous-run/references/decision-protocol.md`

Пункты 1–4 выше — краткая сводка; при расхождении источником истины считать `references/`.
Запуск/резюме автономного прогона — через скилл `h2t-core:autonomous-run` (генерит runbook,
ведёт two-track state, доводит до handoff).
