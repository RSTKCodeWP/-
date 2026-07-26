# 03-fpv / contracts — граница оператор -> FPV (потребительская сторона)

Здесь живёт **потребительская** сторона контрактов границы между Блоком 02
(оператор/инфраструктура) и Блоком 03 (FPV-перехватчик). Перехватчик ЧИТАЕТ эти
сообщения; он их не выпускает.

## Что есть (перенесено из `cuas/interop/contracts/outbound`)

- **`outbound/operator_authorization.py`** — `operator_authorization.v1`.
  Авторизационная нагрузка калитки кинетического действия: подписи двух операторов
  (Ed25519), `physical_keypress_recorded`, `roe_engine_pass`, `civcas_estimate`,
  оценка пропорциональности, `expires_at_utc`. **Это и есть ключ, который
  разблокирует кинетический канал** (см. `../fpv/safety/`).
- **`outbound/effector_cue.py`** — `effector_cue.v1`. Несёт
  `trajectory_prediction`, `search_box_at_terminal`, `launch_recommendation`,
  `threat_assessment` — вход для геометрии перехвата.
- **`outbound/observation_state.py`** — `observation_state.v1`. Канал
  разведки/наблюдения (задача миссии №1): координаты есть, командного действия
  нет.
- **`outbound/effector_cue_delta.py`** — инкрементальные обновления cue.
- **`codec/`** — `jcs.py` (`canonical_json`, `sha256_hex`) и `envelope.py`.
  Зависимость контрактов выше; без неё они не импортируются.

## `engagement_handoff.v1` — РЕАЛИЗОВАН (2026-07-08, `engagement_handoff.py`)

Аудитом-помеченный пробор закрыт: схема **`engagement_handoff.v1`** теперь на диске
(`03-fpv/contracts/engagement_handoff.py`, 10 тестов). Это формальная, аудируемая
передача операторского commit'а перехватчику для конкретного боя; кинетическая
ветка гейтится на ней.

Контракт несёт: ссылку на подтверждённую авторизацию (`authorization_id` +
`authorization_hash` — точный дважды-подписанный Ed25519 `operator_commit`),
задачу миссии (`recon`/`contact`/`kill`), **`target_reference_hash`** (привязка к
immutable `TargetReference`, замороженному на commit в
`fpv_ai.betaflight_link.mission_fsm` — Ось III, верность цели), `kill_box`
(гео keep-out, CIVCAS), окно действия и явные `abort_conditions`.

Калитка `kinetic_permitted(handoff, now_utc, authorization_valid)` — **allow-on-
authorization**: True ТОЛЬКО для `kill`-handoff, ссылающегося на ВАЛИДНУЮ,
НЕИСТЁКШУЮ авторизацию, с привязанным эталоном цели и kill-box, при подтверждённой
неотвечающей угрозе. Всё иное → default-DENY.

**Архитектурное решение (важно):** наземная sense-only анти-оружейная калитка
`../fpv/safety/verifier.py` НЕ инвертируется. Allow-on-authorization живёт ЗДЕСЬ,
в handoff-валидаторе + арминг-авторитете (`betaflight_link/authorization.py`), а
`verifier.py` остаётся deny-all наземным гейтом (см. его REFRAME_NOTES и
рациональ в `authorization.py`). Так безопасная-по-умолчанию калитка не переписывается.

Поток: mission-supervisor commit → `TargetReference.reference_hash` → `build_kill_handoff(...)`
→ `kinetic_permitted(...)` гейтит эмиссию effector-cue. Корневой `/contracts/` должен
зеркалить эту схему как каноническую (эта обёртка — потребительская сторона fpv).
