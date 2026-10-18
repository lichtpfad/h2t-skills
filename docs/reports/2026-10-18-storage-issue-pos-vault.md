---
title: "Текст issue в POS: адрес vault из H2T_PATH_VAULT"
status: "draft"
date: "2026-10-18"
---

Черновик issue для репо POS (spec #548 §6 п. 5, §9; план R26). Этот репо issue не заводит:
заведение — Task 26, шаг владельца. Правку в POS этот репо не делает
(`.claude/rules/repo-boundary.md`).

**Заголовок:** `pos: Read the vault path from H2T_PATH_VAULT`

---

## Контекст

Vault — общий договор двух программ: пишет в него ингест, читают POS и пакет h2t-skills. С
4.0 (lichtpfad/h2t-skills#548) пакет берёт адрес vault из переменной `H2T_PATH_VAULT`, по
умолчанию `~/.dor/vault`. `h2t-ops paths get vault` печатает адрес, который пакет видит
сейчас.

POS держит `~/.dor/vault` зашитым. Места по спеке #548 §1 (здесь не перепроверены, репо
чужое):

- `src/pos_ingest/config.py:4-6`
- `src/pos_meetings/config.py:7,44`
- `src/pos_meetings/routing_review.py:50`

Пока vault лежит по умолчанию, обе программы смотрят в одно место. Если vault переедет и
переменная будет задана только в shell, пакет и POS разойдутся.

## Просьба

1. Читать адрес vault из `H2T_PATH_VAULT` с тем же умолчанием `~/.dor/vault`, в одном месте
   конфига, а не в трёх.
2. Если vault когда-нибудь переедет, добавить `H2T_PATH_VAULT` в plist POS API: launchd не
   наследует окружение shell.
