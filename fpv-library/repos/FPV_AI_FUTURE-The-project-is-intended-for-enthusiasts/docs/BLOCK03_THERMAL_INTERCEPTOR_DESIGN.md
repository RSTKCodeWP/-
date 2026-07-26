> **[SUPERSEDED]** — status as of 2026-07-19. Specifies a FLIR Boson 640 sensor. The actual seeker is a Foxeer FT640(LM) V2 (analog CVBS 8-bit, no Y16 radiometry) -- the optics and detection budgets here do not correspond to the hardware.
>
> **`docs/CHECKPOINT.md` is the source of truth.** Where this document disagrees with it, CHECKPOINT wins.

# Block-03 «Гермес Архангел» — Архитектура ночного тепло-FPV-перехватчика
### Сквозной инженерный проект: сенсор → детекция → ego-motion → трек(LOS) → bearing-rate-наведение → MSP → Betaflight → safety/HITL
*RPi5 CPU-only · FLIR Boson 640 (вариант определяется) · классический CV · оператор-кьюд запуск · бортовой автономный терминал*

---

## 1. Идея в одном абзаце

Ночь — это чит-код для **детекции**. Дрон (моторы, ESC, батарея) светит горячим пятном ~310–340 K на фоне холодного неба ~250–270 K кажущейся температуры; при NETD Boson <20 mK это контраст в десятки «сигм». Поэтому **нейросеть на борту не нужна** — горячую цель ловит классический CV (`top-hat` морфология + перцентильный порог + connected-components) за **~0.5–3 мс на одном ядре Cortex-A76**, и весь сенс-детект-трек-наведение-loop реально влезает в кадр 16.6 мс при 60 Гц **в залоченном ROI-режиме** (вне его — честная деградация до 30 Гц). Архитектура держится на трёх опорах: **(а)** оператор-кьюд запуск — человек на земле через тепловизор видит цель, подтверждает positive-ID и физически жмёт кнопку (это и есть юридический commit `engagement_handoff`), а лок установлен ещё до старта и **непрерывно переносится через запуск** (паттерн Kurbas-640a + The Fourth Law — «зелёная рамка вокруг цели + устойчивый трек»); **(б)** бортовой терминал — после старта сидер сам держит лок и ведёт наведение в body-frame по угловой скорости линии визирования (LOS-rate, λ̇), без мировой системы координат; **(в)** ego-motion-стабилизация по гиро Betaflight (MSP) — то место, где **делается реальная инженерия**: единственная камера на быстро вращающемся FPV даёт чистый λ̇ только если вычесть собственное вращение носителя, и сделать это стабильно на CPU за <2 мс — нетривиально.

**Честная оговорка с первой строки — где НЕ чит-код.** Наведение монокулярное и **пассивное**, поэтому фундаментально ограничено наблюдаемостью: одна камера без собственного манёвра-параллакса **не видит ни дальности, ни скорости сближения**. Классический закон PN `a = N·Vc·λ̇` математически **требует** Vc (closing velocity), и Vc задаёт **величину** команды — направление берётся из знака λ̇, но усиление берётся из Vc. У нас единственный пассивный источник Vc — оптический looming (τ = s/(ds/dt)), а он **вырождается ровно там, где нужен**: на захвате пятно 1–3 px и ds/dt тонет в шуме; у кроссинг-цели dArea/dt → 0 при большом λ̇ (τ→∞, Vc недооценён, команда недобирает); у импакта пятно насыщает FOV и τ коллапсирует. Поэтому мы **не называем это «range-free PN»**: по-честному это **bearing-rate nuller** (обнулитель угловой скорости линии визирования) с **расписанным/предполагаемым** Vc из SpeedPolicy, а не истинный PN-перехватчик с измеренной дальностью. Это сужает достижимый envelope и делает выбор геометрии (head-on/quartering, не high-crossing) частью safety-ROE, а не опцией.

**Где реальная инженерия (не «фурор», а трудная честная работа):** не в том, что мы делаем bearing-rate nulling (его делают seeker'ы с 1950-х), а в том, что **весь стабильный по ego-motion терминал крутится на CPU Raspberry Pi 5 за ~7–15 мс вычислений** при честной деградации, с криптографически-доказуемым human-in-the-loop хребтом **и независимым аппаратным kill ниже FC-софта**. Это «лучший в классе» не по тяге, а по *дисциплине*: воспроизводимый трек, ограниченные команды, fail-closed safety, измеренная (не предположенная) латентность.

---

## 2. Архитектура целиком (сквозная блок-диаграмма)

```
 ЗЕМЛЯ — ПУЛЬТ СТАРТА (Lens 5)                 БОРТ — «Гермес Архангел» (Lens 1-4,6)
 ┌──────────────────────────────┐
 │ Монитор сидера (тепло+overlay)│◄═══ аналог 5.8GHz CVBS ~20-40мс ═══╗
 │  зелёная рамка LOCKED,        │                                     ║
 │  track_id, conf, staleness-clk│              ┌──────────────────────╨─────────────────┐
 │ AIM: pan/tilt сидер-головы    │              │ THREAD 1 — CAPTURE (core 1, isolcpus)   │
 │ COMMIT: [ARM key]+[FIRE guard]│              │ Boson 640 UVC Y16 640x512 @60Hz         │
 │ ABORT: красный грибок (live)  │              │ V4L2 DQBUF, CLOCK_MONOTONIC stamp = t0  │
 │ mission_goal: RECON|CONTACT|  │              │ серийный SLA: manual FFC, gain, cam-temp│
 │              KINETIC (rotary) │              └───────────────┬─────── triple-buffer A ─┘
 └───────┬──────────────────────┘                              ▼
         │ Ed25519 dual-sign + keypress                ┌──────────────────────────────────────┐
         │ → EngagementHandoff.v1                       │ THREAD 2 — PERCEPTION+TRACK (core 2)   │
         ▼                                              │ [2a] EGO-MOTION (Lens 2): гиро MSP     │
 ┌──────────────────────────────┐                       │   de-rotation R=I+[ω]×dt (БАЗА)        │
 │ verifier.py (ИНВЕРТИРОВАН):   │                       │   ⊕ sparse-LK ТОЛЬКО когда есть текстура│
 │ allow-on-authorization,      │◄══════════════════════│ [2b] DETECT (Lens 1): top-hat+перцент. │
 │ default-deny, 8 kinetic cond.│  authorization token  │   относит.порог→CC→subpix (ROI 128²)   │
 └──────────────┬───────────────┘                       │ [2c] TRACK: lock.py FSM + IMM/α-β по    │
                │ allow → разрешён только                │   углам az/el → λ̇ (LOS-rate)          │
                │ этот mission_goal/track                └───────────────┬───── triple-buffer B ──┘
                ▼                                                        ▼
        [kinetic AUX unlock]                                   ┌──────────────────────────────────────┐
        (только в envelope-гейте)                              │ THREAD 3 — GUIDANCE+COMMS (core 3)     │
                                                               │ фикс. 250-500 Гц, развязан от vision   │
                                                               │ bearing-rate null: a_cmd=N·Vc_sched·λ̇ │
                                                               │ pilot.py bounded map → AICommand       │
                                                               │ msp_codec MSP_SET_RAW_RC @100-250Hz    │
                                                               └───────────────┬───────────────────────┘
                                                                               ▼ /dev/ttyAMA0 @230400
                  ┌─────────────────────────────────────┐      ┌──────────────────────────────────────┐
                  │ НЕЗАВИСИМЫЙ HW-KILL (Lens 5)          │      │ Betaflight FORK (Lens 4)               │
                  │ отдельный RX/watchdog-MCU на своём   │─────►│ ANGLE mode, MSP-override + ELRS kill   │
                  │ RF-канале → режет питание моторов /  │ HW   │ 200мс MSP-watchdog → RXFAIL→ELRS       │
                  │ hardware disarm НЕЗАВИСИМО от FC+Pi  │ disarm│ PID-loop 8кГц → моторы                 │
                  │ собств. loss-of-signal таймер        │      └───────────────┬───────────────────────┘
                  └─────────────────────────────────────┘                      ▼ носитель движется → LOS меняется → назад в сидер
```

**Где что живёт:**
- **Борт:** Capture, Perception, Track, Guidance, MSP-TX, Betaflight-fork, ego-motion, geofence/ROE-монитор, локальный inverted verifier-гейт (kinetic unlock), **+ независимый HW-kill ниже FC**. Всё, что должно работать при заглушённой связи, — на борту.
- **Пульт старта:** сидер-монитор + overlay, AIM, физический COMMIT (ARM+FIRE), ABORT (всегда live, **драйвит независимый HW-kill, а не только MSP/ELRS-канал**), сборка и подпись `EngagementHandoff.v1`, журнал.
- **Оператор:** positive-ID глазами по тепло-картинке (с честной оговоркой о дискриминации на 1–3 px, см. 3.5), два раздельных механических акта (ARM-ключ = вторичная власть, FIRE-кнопка = первичная), удержание abort-власти весь полёт.

---

## 3. Каждый блок детально

### 3.1 Тепло-перцепция — «глаз сидера» (Lens 1)

**Ключевые решения:**
- **Интерфейс Boson = USB-UVC в режиме Y16 (16-бит, до-AGC) для пикселей; серийный SLA — управление + телеметрия температуры корпуса.** Подтверждено FLIR: Y16 = pre-AGC, I420 = post-AGC 8-бит, одновременно их не получить. Видео и серийник — два независимых канала, истинные 16-бит counts идут по UVC без сборки параллельного CMOS/CSI-захвата, которого у Pi5 нативно нет.
- **ВАЖНАЯ ПОПРАВКА — порог по Y16 НЕ имеет «фиксированного физического смысла» на стандартном (не-радиометрическом) Boson.** У стандартного core counts **дрейфуют с температурой корпуса камеры и нелинейны к температуре сцены** (FLIR KB). Абсолютный физический порог стабилен **только** на радиометрическом варианте (Boson-R / Boson+), и только пост-FFC в калибровке. Отсюда — **развилка по part-number**, явный deliverable S0:
  - **Если порог по абсолютным counts критичен → требуется радиометрический Boson-R** (с учётом ECCN/цены/доступности, см. 3.4 export-блок).
  - **Если ставим не-R core (дешевле/доступнее) →** порог `99.5-й перцентиль + k·MAD` **переформулируется как явно ОТНОСИТЕЛЬНЫЙ/адаптивный** (top-hat + per-frame percentile это уже почти и есть), а из текста и из обоснования «Y16-over-AGC» убирается формулировка «fixed physical meaning». В детектор **добавляется вход cam-temp + FFC-state**, и **порог ре-базируется после каждого FFC**.
  - В обоих случаях **8-бит AGC отвергнут** не из-за «фиксированного смысла», а потому что AGC каждый кадр заново растягивает гистограмму → горячее пятно может «зажаться» против тёплой сцены, а per-frame относительный порог по сырым counts (top-hat) от этого защищён.
- **Детектор = white top-hat (эллипс SE 9–11 px) + адаптивный перцентильный порог (99.5-й + k·MAD), Otsu только cross-check.** Цель — крошечная доля пикселей против структурированного тёплого клаттера; глобальный Otsu вырождается, top-hat сглаживает низкочастотный фон. Это по природе **относительный** детектор — что и нужно при дрейфе не-R core.
- **Sub-pixel центроид по интенсивно-взвешенным моментам сырых counts**, не центр bbox: ошибка LOS пропорциональна ошибке центроида.
- **MANUAL FFC через SLA, FFC на земле до старта, инхибиция шторки в терминале.** FFC роняет шторку и замораживает видео ~0.5 с (~30 кадров при 60 Гц) — авто-FFC ослепил бы сидер в худший момент. **На не-R core FFC ещё и обязателен для ре-базировки порога** — отсюда конфликт «нужен FFC vs нельзя слепнуть в терминале» решается: FFC только на земле/между прогонами, в терминале — frozen-frame guard + PREDICTIVE_TRACK coast (см. 3.5).
- **Линза ~18–30° HFOV (~24 мм EFL, ~0.5 mrad/px).** Ночь — режим contrast-limited: узкая линза даёт дальность захвата (горячая точка 1–3 px на 100–300 м), широкая 95° схлопывает дальность до десятков метров.

**Конкретные числа / геометрия:**
- IFOV = pixel_pitch/EFL. При 12 µm и 24 мм → ~0.5 mrad/px. Горячая зона квадрокоптера ~0.05–0.15 м. На 100 м пятно 0.1 м ≈ 1 mrad ≈ 2 px; на 50 м ≈ 4 px; на 200 м ≈ 1 px (sub-pixel hot point, high-SNR пик — IRST-style point-target detection). **NB:** именно на этой дальности (1–3 px) морфология почти не несёт shape-информации — см. ограничение positive-ID в 3.5.
- Поток: Y16 640×512, ~640 КБ/кадр, 60 Гц ≈ **39 МБ/с** — тривиально для USB2/Pi5. Boson ~600 mW.

**CPU-бюджет (ROI-режим 128–256 px):** denoise ~0.3 мс · top-hat ~1–2 мс · перцентиль ~0.3 мс · CC ~0.5–1.5 мс · центроид+features ~0.2 мс · association+FSM <0.2 мс → **медиана ~3–5 мс, p99 <8 мс**. Full-frame REACQUIRE (640×512): top-hat ~4–6 мс + CC ~3–5 мс → ~10–14 мс — транзиентно при потере лока (этот транзиент — главный риск для 60 Гц бюджета, см. §4).

**Переиспользуем:** `gates/lock.py` (FSM LOCKED/DEGRADED/PREDICTIVE_TRACK/REACQUIRE/HARD_LOST — меняем `GateDetection(bbox)` → `ThermalBlob(centroid,area,peak_counts,snr,cam_temp,ffc_state)`); `tracking/reacquire.py` (expanding-crop ladder); `perception/detector_output.py` (нормализация → новая схема `fpv_thermal_blob_sequence.v1`, **с полями cam_temp/ffc_state**); `runtime_rpi/device_adapters.py` (+ реальный V4L2/GStreamer Y16 источник и SLA-адаптер с чтением температуры). Block-01: FPS/perf-budget tooling.

---

### 3.2 Ego-motion компенсация + body-frame LOS/LOS-rate — «стабилизированная голова» (Lens 2)

Это **самый важный блок терминала**. На быстро вращающемся FPV (200–1000 °/с) собственное вращение даёт огромный фальшивый λ̇, который наведение будет преследовать. **5 мс ошибки тайм-синка при 200 °/с = 1° фантомной LOS-rate.**

**Ключевые решения:**
- **Body-frame, всегда. Никогда не world-frame.** На единственной вращающейся камере нет доверенной мировой привязки. World-frame fusion Block-01 (наземная станция) нерелевантна — не тащим.
- **ПОПРАВКА ПО ПРИОРИТЕТУ — gyro-only это БАЗОВЫЙ режим, sparse-LK это БОНУС.** Ясное ночное небо, на котором горячий дрон легко детектируется, по той же причине **почти бестекстурно для KLT** — значит «gyro-only» это **частый случай, а не исключение**. Поэтому проектируем наоборот относительно черновика: гиро-деротация — несущая, KLT-остаток включается только когда в кадре есть горизонт/земля/облачная структура.
  - Малоугловая `R = I + [ω]×·dt`; для узкого FOV dx_px ≈ −f·ω_y·dt, dy_px ≈ −f·ω_x·dt, roll = ω_z·dt вокруг главной точки. f = (W/2)/tan(HFOV/2) ≈ **1100–2000 px** для Boson+24мм.
  - Остаток (когда текстура есть) — sparse pyramidal Lucas-Kanade по 60–100 Shi-Tomasi углам ТОЛЬКО на холодном фоне (цель замаскирована) + RANSAC 2–4 DOF similarity. **inliers <~12 → gyro-only (норма, не авария).** Phase-correlation (один FFT) — fallback. Dense Farneback (15–40 мс) **отвергнут**.
- **Поскольку gyro-only — база, точность терминала ЦЕЛИКОМ держится на двух вещах (обе подняты до gating-милестонов):**
  1. **Sub-millisecond cam↔IMU тайм-синк.** Реализуется через аппаратный frame-sync/строб (Boson external-sync это поддерживает) ИЛИ измеренный offset на turntable (S0). Без него 5 мс → 1° фантомного λ̇.
  2. **Soft-mount transfer function.** **КРИТИЧНО и упущено в черновике:** Boson на виброизоляции (soft-mount/gel), а FC-гиро жёстко смонтирован → **гиро НЕ меряет реальное угловое движение камеры под вибрацией** (soft-mount вносит относительное движение, которого гиро не видит). Решения, на выбор и под измерение: (а) охарактеризовать передаточную функцию soft-mount и связать сигнал гиро с реальным движением камеры, ИЛИ (б) **жёстко смонтировать камеру и изолировать раму в другом месте**. Плюс online-оценка gyro scale/bias.
- **Фильтр цели = IMM (CV + Singer-maneuver) на [az, el, az_rate, el_rate], α-β как документированный fallback.** Mode A = constant-velocity LOS, Mode B = Singer/высокий шум для джинков И ego-спайков (FFC, гиро-глитч). **Критично:** инновации гейтятся против гиро-предсказанного движения, чтобы ошибка деротации не выглядела как манёвр цели.
- **Дальность НЕ оцениваем (и честно — пассивно не можем без собственного манёвра-параллакса).** Time-to-go = оптическое τ (looming) — **но τ используется только как СЛАБЫЙ, gated источник, см. ограничение Vc в 3.3, а не как надёжная дальность/скорость.** τ_confidence коллапсирует у детекторного пола (далеко) и при насыщении (близко) — это и есть фундаментальный наблюдаемостный предел, не CPU.

**Выходной контракт (на кадр):** `{t_capture_ns, az_rad, el_rad, az_rate_radps, el_rate_radps, lock_state, lock_confidence, tau_s, tau_confidence, closing_sign, ego_quality, ego_source(gyro|gyro+klt), n_flow_inliers, cam_imu_sync_us}`.

**CPU-бюджет (одно ядро, NEON):** гиро-деротация ~0.05 мс · центроид ROI ~0.2 мс · **sparse KLT ~80–100 pts ~1.5–4 мс (доминанта, когда включён)** · RANSAC ~0.3 мс · IMM 4-state ~0.05 мс · τ+FSM ~0.1 мс → **ego+track ≈ 0.5–1 мс в gyro-only базе, 3–6 мс с KLT**. Поток гиро MSP — на своём ядре; KLT-спайк 4 мс никогда не стопорит LOS-выход (last-good ego при пропуске дедлайна).

**Переиспользуем:** `gates/lock.py` (FSM + coast гонят гиро+IMM); `betaflight_link/{transport,commands,payload_decoder}.py` + **новый high-rate MSP_RAW_IMU(102)/MSP_ATTITUDE(108) reader-thread**; Block-01 IMM-идея (переписать в body/angle frame); FPS/perf-budget tooling.

---

### 3.3 Закон наведения — body-frame bearing-rate null → Betaflight command set (Lens 3)

**Ядро — честная формулировка.** Закон: `a_cmd = N · Vc · λ̇`, перпендикулярно LOS, раздельно по az и el. Обнуление λ̇ = коллизионный треугольник = zero-effort-miss. **Но Vc математически обязателен и задаёт ВЕЛИЧИНУ команды; range-free берётся только НАПРАВЛЕНИЕ (знак λ̇).** Поэтому называем вещи именами: **это bearing-rate nuller, а не истинный PN-перехватчик с измеренной дальностью.** Монокулярная пассивная камера без собственного манёвра-параллакса наблюдаемостно **не восстанавливает Vc** — это фундаментальный предел.

**Ключевые решения (с учётом ограничения Vc):**
- **Vc = РАСПИСАННЫЙ/предполагаемый скаляр из SpeedPolicy, НЕ доверяем τ.** Для быстрого перехватчика против медленной цели собственная воздушная скорость доминирует в скорости сближения, поэтому Vc_sched из SpeedPolicy + own-airspeed — основной источник усиления. Looming-τ используется только как **confidence-gated cross-check знака/порядка**, и при `tau_confidence` low он **не масштабирует** команду.
- **Blend pursuit↔bearing-rate-null.** Когда `tau_confidence` низок (захват, кроссинг, импакт-насыщение) — **pure-pursuit (Vc не нужен) доминирует**; bearing-rate-null с расписанным Vc включается только при адекватной геометрии и confidence. Это прямое следствие наблюдаемостного предела: не делаем вид, что усиление известно, когда оно неизвестно.
- **ЖЁСТКИЙ envelope-гейт по геометрии (часть ROE, не опция).** Демонстрируемый engagement ограничен **благоприятной head-on/quartering** геометрией; **high-crossing цель → ROE-abort**, потому что (а) у кроссинга dArea/dt→0 и Vc недооценён, (б) энергетика не тянет (см. ниже). Этот гейт **тестируется** (F1), а не декларируется.
- **N = 3 (диапазон 3–4), pure pursuit/bearing-rate по умолчанию, APN-член только когда IMM уверенно сигналит манёвр.** **ПОПРАВКА: сенсорная задержка >25 мс + петлевая (см. §4) толкает N ВНИЗ, к 3, а не к 4** — PN/bearing-rate-null чувствителен к loop-delay, большой N усиливает шум λ̇ и delay-induced осцилляцию. APN `+ (N/2)·a_T` режет промах против манёвра вдвое, но впрыскивает шум a_T → confidence-gated, не always-on.
- **Квадрокоптер ≠ ракета — и энергетика это Ахиллес.** Боковое ускорение даётся ТОЛЬКО наклоном тяги: a ≈ g·tan(θ). При 35° → **~0.70 g**, при 45° → **1.0 g**. Против цели, способной на >1 g и смену направления внутри loop+sensor delay (~45–60 мс), перехватчик с тяжёлым payload (130–160 г), уже срезающим тяговый запас, **проигрывает многие crossing/last-jink геометрии**. Отсюда — `θ_cmd = atan(a_cmd/g)`, ограничено **±35–45°**, **и явный envelope-гейт по target-агрессивности** (см. 3.4-вес и таблицу рисков).
- **Boresight держим ≈ на векторе скорости** — предусловие устойчивости single-camera наведения.
- **Фазовый переход angle → body-rate (acro) в терминале <~0.4 с / <15 м** для финальной agility (выигрыш по достижимой g за счёт большего эффективного наклона).
- **Гравитационный feed-forward в throttle** — компенсируем просадку, чтобы боковая команда не корраптилась.
- **Terminal LOS-rate hold (impact freeze):** при ill-conditioned центроиде (<~неск. м) замораживаем последний хороший λ̇ и идём прямо.

**Гейтинг RECON→CONTACT→KINETIC прямо в законе:** один и тот же core на всех уровнях; handoff гейтит committed terminal sink + минимальный standoff. RECON/CONTACT — range-regulated (держим ненулевой standoff). **KINETIC — единственный уровень, где standoff→0**, и только при валидном dual-signed `operator_authorization.v1` **И прохождении envelope-гейта (цель в достижимой-g зоне + геометрия не high-crossing + adequate pixel-on-target для ID)**. Без токена ИЛИ вне envelope — guidance hard-clamped на высший already-authorized non-kinetic standoff (default-deny). Гейт сидит МЕЖДУ командой и throttle/commit, fail-closed.

**CPU:** сам закон — арифметика, **<5 µs/кадр**. Стоимость целиком в тепло-фронтенде и MSP. Реальный риск — **сквозная латентность и наблюдаемость Vc**, не CPU: они аргументируют N≤3, Smith-predictor-style lead (см. §4), узкую полосу и pursuit-blend.

**Переиспользуем:** `control/pilot.py` GateVisualPilot → `LosGuidancePilot` (заменить центрирование позиции на bearing-rate-null по LOS-rate + pursuit-blend, сохранить bounded `AICommand`, `speed.py` SpeedPolicy как **первичный источник Vc_sched и envelope-предела**); `gates/lock.py` (`predicted_center_px`, `_velocity_px_per_ms`); `betaflight_link` (CRC, RC-маппинг); `tracking/prediction/imm_blender.py` (IMM → a_T для APN, body-frame rewrite); `safety/verifier.py` + `engagement_handoff.md`.

---

### 3.4 Интеграция с полётником (Lens 4)

**Ключевые решения:**
- **Несущая управления = MSP_SET_RAW_RC (cmd 200) на фикс. 100 Гц по MSP v2**, НЕ кастомный «guidance-bridge» и НЕ DisplayPort. 100 Гц передискретизирует 60 Гц vision-петлю. Внутренний FPAI/CRC32-фрейм (`transport.py`) остаётся как лог/аудит/bench-формат, транскодируется в MSP-байты на проводе.
- **Baud = 230400**: 36-байтный override-фрейм на 115200 = ~3.1 мс, на 230400 = ~1.5 мс. Betaflight держит `serial_update_rate_hz` до 2000, петля 60–120 Гц комфортна.
- **UART = PL011 `/dev/ttyAMA0` (GPIO14/15), НЕ miniUART** (`/dev/ttyS0` нестабилен по baud).
- **Betaflight FORK — safety-critical deliverable с собственным V&V (не «first-class», а «highest-risk»).** Сток делает RX_MSP и RX_SERIAL **взаимоисключающими** (Issue #8292) — нельзя иметь и MSP-override, и независимый ELRS-failsafe. Форк: (а) принимает MSP-override-каналы, сохраняя ELRS как независимую kill-власть на AUX; (б) делает потерю MSP-heartbeat собственным RXFAIL-источником с **200 мс watchdog** → возврат на ELRS. Патчить против #13416 (MSP_OVERRIDE стопорит моторы после arm) и #13374 (failsafe при валидном MSP).
  - **ПОПРАВКА — форк проходит обязательное bench-V&V до ЛЮБОЙ тяги (B1, props OFF, затем B3 tethered), и каждое из трёх измеряется и логируется:** (1) ELRS AUX-kill disarms за ограниченное время **ПОКА MSP активно оверрайдит**; (2) MSP-тишина → RXFAIL → ELRS-handover **за ≤200 мс, измеренные**; (3) регрессия #13416 (моторы стоп после arm) **не воспроизводится**. **Никакой props-on тест не разрешён, пока эти три не продемонстрированы и не залогированы.**
- **Режим = ANGLE для sim→tether→первый свободный полёт** (self-leveling клампит roll/pitch ~50°); HORIZON для терминального спринта позже; ACRO никогда рано.
- **Кнопка запуска = юридический commit.** FIRE → `physical_keypress_recorded=true`+timestamp в `OperatorAuthorization`; `verifier.py` (inverted) ДОЛЖЕН ПРОЙТИ до того, как Pi поднимет AUX1. Arm-секвенция как в `rc_control.py`: AUX1→2000 только при throttle==1000 µs и `arm_throttle_low_ok`; `manual_kill` форсит AUX1→1000 безусловно. Throttle-handoff: AI_PREARM→ARM_REQUEST→ARMED_IDLE→STABILIZE→THROTTLE_RAMP→AI_ACTIVE.
- **Видео = аналог 5.8GHz CVBS ~20–40 мс glass-to-glass** до И после старта; цифровой HD (DJI/Walksnail 60–130 мс + codec-freeze) **отвергнут** для control/abort-пути. Аналог деградирует в статику, а не во фриз.
- **Часы:** Pi — мастер времени на CLOCK_MONOTONIC; FC нужна только monotonic-свежесть (200 мс watchdog) + sequence_id gap.

**EXPORT-CONTROL — точная классификация (поправка):** Boson 640 — **EAR, не ITAR (NDAA-compliant)**. ECCN зависит от частоты кадров: **60 Hz и 30 Hz core → 6A003.b.4.b** (dual-use, на Commerce Control List, **частота кадров = control trigger**); **9 Hz core → 6A993.a**. То есть **именно 60 Гц — регулируемая фича**, на которой держится весь loop-бюджет, а 9-Гц fallback это **не бесплатная де-контроль-опция** (он рушит частоту петли). Сверх собственного ECCN камеры: тепло-seeker на **kinetic-перехватчике** двигает END-USE в чувствительную категорию (последствия для procurement, re-export, демонстрации иностранным гражданам). **Радиометрический Boson-R** (если выбран в 3.1) — отдельно проверить его классификацию/доступность. **Deliverable:** явный compliance/legal checkpoint в план **до закупки** и **до любого участия не-US-person или off-continent демо**.

**CPU:** слой I/O-bound. MSP-фрейм: encode <50 µs, провод ~1.5 мс. MSP-TX/телеметрия — своё ядро, SCHED_FIFO, ровные 100 Гц независимо от vision-jitter.

**Переиспользуем:** `transport.py` (+ `SerialTransport` за фасадом, флипнуть hardcoded `uart_opened`/`flight_commands_published`/`hardware_test_authorized` на runtime-observed под hw-auth-токеном); `+ msp_codec.py` (MSP v2 `$X<`, CRC8-DVB-S2); `commands.py`; `rc_control.py` (RC-маппер + arm-логика); `mode_state_machine.py`; `fork_contract.py`/`fork_patch_plan.py`/`fork_patch_bundle.py`/`fork_unit_tests.py` (форк-скаффолдинг + V&V-харнесс под три обязательных теста).

---

### 3.5 Пульт старта + Safety/ROE-хребет (Lens 5) — **безопасность = продукт**

Единый наземный «launch console» = сидер-монитор, поверхность positive-ID, физический COMMIT и (после старта) постоянный abort/authority-канал. Консоль существует, чтобы механически сделать истинным «нет валидной auth → нет kinetic», и навсегда auditable.

**Физический layout:**
1. **Сидер-монитор:** живой Boson 640 feed с борта ДО старта. Overlay: LOCKED-рамка (зелёная/янтарь/красный из `gates/lock.py` TrackingState), `track_id`, confidence, area (px + угл. размер + **флаг «ID-grade pixels?» yes/no**), crosshair, **staleness-clock**, link/latency-strip. Паттерн Kurbas-640a + The Fourth Law: зелёный контур вокруг тепло-цели + устойчивый трек.
2. **AIM:** pan/tilt сидер-голова на пусковой рейке. **Дефолт: сидер дрон-смонтирован, его feed = вид консоли** → лок бит-в-бит идентичен борту → **нулевой handoff-gap**. Альтернатива (отдельный сидер + lock-handoff) задокументирована как fallback с параллаксом.
3. **COMMIT = двухступенчатый физический интерлок.** **ARM-ключ** (механический key-switch) = вторичная власть (dual-key floor #2). **FIRE-кнопка** (защищённый debounced GPIO momentary) = первичный акт → `physical_keypress`. **ABORT** = большой красный латчинг-грибок, всегда live, доминантный, **драйвит независимый HW-kill-путь (см. ниже), а не только MSP/ELRS-канал**. Опционально deadman-bar. Разной формы/расположения — FIRE нельзя спутать с ABORT на ощупь.

**ПОПРАВКА — positive-ID: не заявляем ID-уверенность, которой сенсор не даёт на захвате.** На 100–300 м цель = **1–3 px hot point**; морфология даёт почти ноль shape-инфо, и птица, факел, дымоход, выхлоп, звезда или **второй горячий дрон (декой/lock-theft)** дают похожий high-SNR пик. **Человек тоже не может positive-ID 1–3 px пятно как враждебное.** Поэтому kinetic-commit гейт требует **ОБА**:
- **(а) adequate pixel-on-target** — positive-ID разрешён только когда пятно достаточно крупное (ближе/больше px), чтобы показать **motion-signature**, ИЛИ слит со вторым кью (кинематика трека, оператор-визуал через второй сенсор, **IFF/deconfliction-список дружественных треков**);
- **(б) track-kinematics consistency** (поведение трека совместимо с UAV-классом);
- плюс обязательная lock-theft-митигация (no auto-switch, association-margin).
- **Для выставки/демо — жёсткое предусловие:** контролируемая цель, **никаких других горячих объектов в FOV**, и это записано как explicit precondition сценария.
Устойчивый LOCKED ≥ `stable_frame_count` (дефолт 3 → ~50 мс при 60 Гц) — необходим, но **не достаточен**: к нему добавлены (а)+(б). Консоль снапшотит N кадров вокруг COMMIT — positive-ID clip в журнал = тело `target_track_ref`.

**Маппинг на `engagement_handoff.v1`:** на COMMIT консоль собирает ОДИН подписанный `EngagementHandoff`: `mission_goal` (физический 3-поз. rotary RECON|CONTACT|KINETIC, дефолт RECON, **никогда не авто-апгрейд**); `target_track_ref`; `authorization = OperatorAuthorization.v1` (FIRE → keypress+timestamp; ARM+FIRE → две Ed25519-подписи над `dual_key`-payload); `roe_engine_pass`, `civcas_estimate`, `proportionality_assessment`; для LIVE kinetic — `mock_mode`/`dry_run_only`/`operator_review_audit_only`/`synthetic` явно false (каждый — audited act). `roe = {ruleset_id, geofence_enu, abort_conditions, max_engagement_window_s, ground_keepout_footprint}`. Verifier проверяет **все 8 kinetic-условий** + **envelope-гейт** + **ID-grade-pixel флаг**; любой промах → reject → борт держится на высшей non-kinetic фазе (default-deny). `expires_at_utc` = issued_at + **60–120 с**.

**НЕЗАВИСИМЫЙ АППАРАТНЫЙ KILL — НОВЫЙ обязательный блок (закрытие MAJOR-дыры).** В черновике «ELRS overrides everything» **ложно**: ELRS-kill всё равно идёт через тот самый Betaflight-софт (источник багов #13416-класса) и через тот же контестируемый RF. Зависший Pi с stale last-good RC-фреймом, ошибка форка или RF-jam оставят моторы крутящимися без независимого отсечения. **Решение — kill-путь НИЖЕ FC-софта:**
- **Отдельный failsafe-RX или watchdog-MCU на выделенном RF-канале**, который **режет питание моторов** (или тянет hardware-disarm line / smart-ESC kill) **независимо от состояния FC-firmware и Pi**.
- Действует по **СОБСТВЕННОМУ loss-of-signal таймеру** (не зависит от MSP/ELRS).
- **Оператор-ABORT (грибок) драйвит ИМЕННО этот независимый путь.**
- Для tethered-тестов — дополнительно физический **power tether-cut**.

**Разделяем АВТОНОМНЫЙ и ОПЕРАТОРСКИЙ abort (поправка — это не одна гарантия):**
- **(a) АВТОНОМНЫЕ aborts (geofence-exit, auth-expiry, hard-lost, link-loss-timeout) — онборд, командуют SAFE-DITCH/disarm БЕЗ uplink.** Geofence/ROE-монитор онборд, проверка позиции каждый loop.
- **(b) ОПЕРАТОРСКИЕ aborts (грибок/deadman) ТРЕБУЮТ uplink** — физический грибок достаёт борт только по RF. **Если RF заглушён в момент, когда оператор хочет abort, сработает ТОЛЬКО автономная lost-link логика, не интент оператора.** Поэтому: **определён и протестирован link-loss timeout**, авто-триггерящий ditch, когда оператора больше не слышно; для kinetic-фаз таймаут **короткий**. Честный worst-case: **в jam борт уходит в автономный safe-ditch за X мс и НЕ продолжает к last-known цели.** Bench-проверка: потеря ОБОИХ (MSP и ELRS) → моторы-офф за ограниченное, измеренное время **через независимый HW-kill**.

**Lost-lock / ditch — fail-SAFE лестница с КОЛИЧЕСТВЕННОЙ range-safety для kinetic (поправка):**
- (a) краткая потеря → PREDICTIVE_TRACK ~**300–500 мс** (`predictive_track_ms`);
- (b) дольше → REACQUIRE expanding ~**1.5 с** (`reacquire_track_ms`), **kinetic-ветвь suspended, как только confidence < порог**;
- (c) HARD_LOST / AUTH_EXPIRED / geofence-exit → **детерминированный ditch:**
  - **powered fly-to-ditch-sector — ТОЛЬКО пока control authority подтверждённо здорова;**
  - **cut-motors-drop — ТОЛЬКО как терминальный fallback, когда control потеряна И предсказанная точка падения ВНУТРИ расчищенной зоны.**
  - **Для kinetic-конфигурации ОБЯЗАТЕЛЬНО ДО любого kinetic-полёта:** количественный **ground keep-out footprint** (баллистика + ветер) **без людей/имущества**, exclusion-zone range-safety план, range-safety officer. **Не «drop anywhere», а «drop внутри surveyed, cleared, RSO-controlled footprint».**
  - **Если kinetic-payload можно сделать инертным на ditch (fail-safe-inert arming logic) — требуется.**
  - Self-destruct **остаётся отвергнут** (правильно для демо).
  - Edет на Betaflight failsafe Stage-2 (re-arm заблокирован, пока RC не восстановлен ≥3 с и arm-switch OFF), **но финальное отсечение питания — через независимый HW-kill, не только FC.**

**Юридический триатлон для выставки:** (1) человеческий positive-ID **с честной оговоркой о дискриминации** (оператор видел тепло-цель + ID-grade pixels ИЛИ второй кью + lock-evidence, снапшот в журнал), (2) физический commit (два механических акта = две подписи + keypress-timestamp), (3) append-only Ed25519 JSONL-журнал каждого handoff (accept ИЛИ deny) с подписями, решением verifier, ROE/civcas/footprint, positive-ID clip. Цепочка track → подписи → verifier реконструируема end-to-end. **На самой выставке — `synthetic=true`/non-kinetic: тот же pipeline, live-kinetic-условия осознанно fail-closed — гейт доказывается тем, что НЕ стреляет.**

**Крипто-стоимость:** Ed25519 sign ~50–150 µs, verify ~150–300 µs на A76 — раз за COMMIT, вне hot-path. Per-frame safety: TrackingState + пороги + point-in-polygon + staleness-clock — **<1 мс/кадр**. JSONL-append буферизован/async.

**Переиспользуем:** `safety/verifier.py` (Ed25519/HMAC envelope, canonical JSON, JSONL-журнал, schema-validate, recursive scan verbatim; **инвертировать** `FORBIDDEN_FIELD_VALUES` → allow-on-authorization по `REFRAME_NOTES.md`; **+ envelope-гейт + ID-grade-pixel-гейт**); `cue_authorization/dual_key.py` (`software_ed25519_mock` → hardware-backed); `cue_authorization/physical_keypress.py` (`mock_gpio_button` → реальный debounced GPIO-interrupt); `roe_evaluator.py` + `civcas_assessor.py` (**+ ground-keepout-footprint**); `gates/lock.py`; `betaflight_link/rc_control.py`+`mode_state_machine.py` (BUTTON_CONFIRMED); `effector_cue.py`. **Новое (не из текущего кода):** независимый HW-kill MCU/RX-харнесс.

---

### 3.6 Real-time loop + железо + латентность (Lens 6)

**Архитектура:** 3-thread single-process, пиннинг по 4 ядрам A76 @2.4 ГГц, 4-е ядро под OS/IRQ. Связь через **два pre-allocated triple-buffer (lock-free, sequence-swap; без очередей, без malloc в hot-path)**, GIL отпускается вокруг каждого numpy/native-вызова.

- **Thread 1 CAPTURE (core 1):** blocking V4L2 DQBUF, CLOCK_MONOTONIC stamp = t0, ~0.2 мс/кадр.
- **Thread 2 PERCEPTION+TRACK (core 2):** ego-comp + detect + track, fully ROI-gated при локе.
- **Thread 3 GUIDANCE+COMMS (core 3):** фикс. **250–500 Гц tick, развязан от vision** — FC-линк не голодает при дропе кадра. Стандартная seeker-архитектура.

**Hard real-time monitor (поправка):** добавлен **детектор frame-overrun**, который при превышении бюджета **принудительно переводит vision в 30 Гц**, а не даёт петле молча джиттерить. Guidance/comms при этом неизменно 250–500 Гц.

**OS/runtime:** 64-бит Pi OS Bookworm + **PREEMPT_RT**, `isolcpus=1,2,3` (+`nohz_full`,`rcu_nocbs`), governor=performance, DVFS/throttle off под heatsink+fan, USB/UART IRQ на core 0, SCHED_FIFO на воркерах.

**Python vs native:** Python-оркестрация + numpy/OpenCV (C+NEON) для пиксельных операций; Cython/C — ТОЛЬКО проверенно-горячие kernels если профайл покажет Python-overhead >1 мс. `gc.disable()` на миссию.

**Вес/agility (Гермес Архангел):** Pi5 ~45 г + active cooler ~20 г + Boson core 7.5 г + линза ~5–30 г + VPC/breakout ~10–20 г + FC ~8 г + VTX ~5 г + **независимый HW-kill MCU/RX ~10–20 г** + harness ~30 г ≈ **payload 140–180 г**. Тяжело для 5–7″ FPV — режет flight time/agility И **тяговый запас → достижимую боковую g**. **Бюджетировать T/W С ПОЛНЫМ payload и верифицировать lateral-accel margin на intercept-скорости.** Pi5+cooler доминируют → **поднять достижимую g за счёт меньшего compute-веса (CM5/undervolt до 1.5–2.0 ГГц, в ROI-режиме хватает) и большего эффективного наклона (angle→acro terminal).**

**Монтаж (с учётом soft-mount поправки из 3.2):** boresight оптической оси Boson к оси тяги/скорости; калиброванный boresight-offset. **Развилка виброизоляции — решается измерением передаточной функции:** либо (а) soft-mount камеры + охарактеризованная transfer function, связывающая жёстко-смонтированный FC-гиро с реальным движением камеры, либо (б) **жёстко смонтировать камеру** (гиро тогда меряет её реальное движение) и изолировать раму в другом месте. Без этого gyro-only ego (база!) систематически ошибочен под вибрацией.

**Fallback-лестница:** (1) vision 60→30 Гц (overrun-monitor форсит); (2) full-frame→ROI-only; (3) gyro-only ego (**это БАЗА, не fallback** — см. 3.2); (4) Pure-Pursuit вместо bearing-rate-null если λ̇/Vc ненадёжны; (5) perception-stall → guidance держит last-valid LOS с decay → staleness-watchdog → автономный ditch + независимый HW-disarm.

---

## 4. Бюджет латентности (сквозная таблица, Pi5 CPU)

Фотон → команда мотора, **залоченный/ROI-случай**:

| Этап | Источник | Латентность | Природа |
|---|---|---:|---|
| Boson сенсор + AGC/NUC pipeline | Lens 1/6 | **>25 мс** (FLIR app-note: «**более** 25 ms», ~1.5–2 кадра) **+ event-driven jitter вокруг FFC** | bias + **НЕ чистая константа** |
| USB-UVC transfer + V4L2 buffer | Lens 6 | ~3–8 мс (+jitter; MIPI срезал бы до ~1–2 мс) | переменная |
| Ego-motion (гиро read / sparse LK) | Lens 2 | ~0.5–2 мс | переменная (KLT-спайк ≤4 мс) |
| Detection (ROI top-hat+порог+CC) | Lens 1 | **~0.5–1 мс** (full-frame ~3–5 мс) | переменная |
| Track + IMM/α-β → λ̇ | Lens 2 | ~0.5–1 мс | малая |
| Guidance (bearing-rate-null) + mapper + verifier | Lens 3/5 | **~0.2 мс** | малая |
| MSP encode + UART (40 B @230400) | Lens 4 | ~0.4–1.5 мс | малая |
| FC ingest→mixer→ESC (BF 8 кГц) | Lens 4 | ~1–2 мс | малая |
| **COMPUTE+LINK (всё, что мы контролируем)** | | **~7–15 мс** | — |
| **Wall-clock фотон→actuation** | | **~45–60 мс** (из них **>25 мс — несменяемый сенсор + FFC-jitter**) | — |

**ПОПРАВКА ПО СЕНСОРУ (была sign-инверсия):** черновик цитировал «<25 ms» как верхнюю границу — это **ошибка знака**. FLIR-документация даёт пиксель/кадр доступным **через БОЛЕЕ чем 25 мс** (~1.5–2 кадра при 60 Гц). Плюс AGC/NUC/FFC вносят **frame-dependent и event-driven jitter** — это **НЕ чистый константный bias**, поэтому наивный единый predictive-lead optimistic. Правильная модель: **25–35 мс сенсор + jitter**, компенсация — **Smith-predictor-style lead** с явной моделью задержки, а не один offset; и **измерить реальную end-to-end задержку эмпирически на B1** (импульсный тепло-источник/фотодиод → timestamp команды мотора) **до того, как доверять любой lead-компенсации.** Эта задержка одна может форсить **N≤3**.

**Вердикт реализуемости (заголовок = честная формулировка, не сноска):**
- **60 Гц достижимо ТОЛЬКО в залоченном ROI-steady-state и хрупко вне его.** p99-запас тонок: >2 мс маржа съедается KLT-спайком (≤4 мс), транзиентным full-frame REACQUIRE (10–14 мс одной детекции), Python/GIL/GC-jitter, USB-UVC DQBUF-jitter, thermal throttle — и стек этих эффектов рвёт 16.6 мс **именно в моменты (потеря лока, клаттер), когда тайминг важнее всего.**
- **Целевая формулировка (заголовок):** **«60 Гц когда залочен в ROI; детерминированная graceful деградация до 30 Гц на REACQUIRE/клаттере (через hard real-time overrun-monitor); guidance/comms всегда 250–500 Гц независимо от vision».**
- **Доказать на B1 нужно p99 (не медиану) compute < frame** на реальном железе под thermal-soak, с gc.disable, isolcpus, **и реальным (не синтетическим) full-frame REACQUIRE в трейсе.** Cooling специфицировать так, чтобы throttle не сработал в полёте (ambient + airflow на движущейся раме помогают — но верифицировать).
- При 30 Гц (33.3 мс/кадр) бюджет комфортен.
- **Сенсорная задержка >25 мс — доминанта, не лечится на классике Boson** (Boson+ дал бы <6 мс — но это **6A003.b.4.b** export-controlled core и дороже); компенсируем Smith-predictor lead + N≤3 + узкая полоса + angle→rate терминал.

**CPU-нагрузка:** ROI-steady-state ~одно ядро A76 на 30–50% (perception) + второе слегка → headroom есть. Full-frame search ~70–90%. Тепло: Pi5 ~5–8 Вт → **active-cooler обязателен**, иначе throttle убивает бюджет.

---

## 5. Safety / правовой хребет

**Как пульт + физкнопка + positive-ID + inverted verifier + независимый HW-kill реализуют `engagement_handoff`:**

```
positive-ID (глаза + ID-grade pixels ИЛИ 2-й кью + LOCKED≥3 кадра + kinematics + clip)
        │   (НЕ просто LOCKED≥3 — adequate pixel-on-target ОБЯЗАТЕЛЕН)
        ▼
ARM-ключ (secondary Ed25519) ──┐
                               ├─► dual_key payload → 2 подписи
FIRE-кнопка (primary Ed25519) ─┘   + physical_keypress + timestamp
        │
        ▼
EngagementHandoff.v1 {mission_goal, target_track_ref, authorization,
                      roe(+ground_keepout_footprint), synthetic=false(audited)}
        │
        ▼
verifier.py (ИНВЕРТИРОВАН: allow-on-authorization, default-deny)
   ВСЕ 8 kinetic-условий: dual-key ✓ keypress ✓ ROE-pass ✓ civcas ✓
   non-synthetic ✓ unexpired ✓ this-exact-track ✓ non-responsive ✓
   + ENVELOPE-гейт (achievable-g ✓ геометрия не high-crossing ✓)
   + ID-GRADE-PIXEL-гейт ✓
        │
   ┌────┴────┐
 ACCEPT     REJECT
   │           │
 kinetic     hold на высшей already-authorized non-kinetic фазе
 AUX unlock  (default-deny)
 (standoff→0)
   │
   ▼
[моторное отсечение ВСЕГДА доступно через НЕЗАВИСИМЫЙ HW-kill,
 ниже FC-софта, по собственному loss-of-signal таймеру]
```

**Инвариант «один order / одна цель / одно окно»:** authorization привязана к точному `target_track_ref` + tight `expires_at_utc` → захваченный токен не re-fire'ит на другой цели; `AUTH_EXPIRED` — автономный abort.

**Abort-условия — РАЗДЕЛЕНЫ на автономные и операторские (поправка):**
- **Автономные (онборд, БЕЗ uplink, командуют ditch/disarm сами):** `LOST_TRACK`(→HARD_LOST), `LEAVES_GEOFENCE` (point-in-polygon каждый loop), `AUTH_EXPIRED`, `LINK_LOSS_TIMEOUT` (новое — короткий таймаут для kinetic), `CIVILIAN_IN_PATH`.
- **Операторские (ТРЕБУЮТ uplink):** `OPERATOR_ABORT` (грибок/deadman). **Честный worst-case: в RF-jam операторский интент не дойдёт — сработает только автономный LINK_LOSS_TIMEOUT → safe-ditch за X мс, без продолжения к last-known.**

**Lost-lock/abort/geofence/ditch:** см. 3.5 — fail-SAFE лестница PREDICTIVE_TRACK(~300–500 мс)→REACQUIRE(~1.5 с, kinetic suspended)→HARD_LOST→**детерминированный ditch** (powered-to-sector только при здоровом control; cut-motors-drop только в cleared footprint). **Для kinetic — surveyed/cleared/RSO-controlled ground keep-out footprint обязателен ДО полёта.** Финальное отсечение — через **независимый HW-kill**, не только FC. Self-destruct отвергнут.

**Хард-требования перед любым live-kinetic (расширены):**
1. Заменить `software_ed25519_mock` на hardware-backed key backend (secure element/TPM); verifier **отвергает** mock-подписи + uncleared safety-флаги при `synthetic=false`.
2. **Betaflight-fork прошёл три bench-V&V-теста** (ELRS-kill при активном MSP; MSP-silence→ELRS ≤200 мс измерено; #13416 не воспроизводится) — **до любой тяги.**
3. **Независимый HW-kill смонтирован и проверен** (loss-of-both-links → моторы-офф за измеренное время).
4. **Range-safety:** количественный ground keep-out footprint (баллистика+ветер), exclusion zone, RSO; fail-safe-inert payload если возможно.
5. **Envelope-гейт оттестирован** (цель вне achievable-g/геометрии → ROE-abort).
6. **Cam↔IMU sync <1 мс измерен и soft-mount transfer function охарактеризована** (терминальная точность на этом держится).

**Риск инверсии verifier:** держим Ed25519/HMAC-envelope, schema-validation, recursive scan, JSONL-журнал **как есть** по `REFRAME_NOTES.md`; default-deny остаётся fail-closed дефолтом; arming физически downstream от verifier-PASS **И от независимого HW-kill**; каждый accept/deny журналируется.

---

## 6. План стройки (staged): сим → привязь → свободный полёт

Безопасностный принцип: **free-flight kinetic НИКОГДА не шаг 1.**

| # | Веха | Что делаем | Переносим из кода | Safety-gate выхода | Effort / Risk |
|---|---|---|---|---|---|
| **S0** | Калибровка + схемы + **part-number decision** | Boson intrinsics (f,cx,cy,distortion); **развилка R/не-R core зафиксирована**; turntable: **cam↔IMU time-offset (gating!) + gyro scale/bias**; lock Y16 V4L2 path; `ThermalBlob`/`TargetObservation` + `fpv_thermal_blob_sequence.v1` **с cam_temp/ffc_state** | `detector_output.py` паттерн | схемы зафиксированы, **sync-offset <1 мс измерен**, part-number выбран | M / M |
| **S1** | SIM perception | Синтетик-генератор (холодное небо + горячее пятно area/SNR/motion + звёзды + FFC-freeze + **cam-temp дрейф для не-R**); CV-pipeline top-hat→**относит.порог**→CC→subpix; subpix-точность, false-alarm vs звёзды, **ре-базировка порога после FFC** | `gates/lock.py`, `reacquire.py`, Block-01 perf-tooling | subpix <0.1 px, FA-rate gate, порог стабилен при cam-temp дрейфе | M / L |
| **S2** | SIM ego+track | body-frame seeker-sim: **gyro-only как база** (остаток ≈0 при чистом вращении), KLT-бонус при текстуре, (az,el), α-β→IMM, optical-τ как **слабый** кью; lock.py FSM; инжект FFC/occlusion → coast; **инжект cam↔IMU sync-error и soft-mount-residual → измерить фантомный λ̇** | `gates/lock.py`, IMM-идея Block-01 (body-rewrite) | ego-residual НЕ читается как манёвр; gyro-only терминал держит точность при моделируемом sync/soft-mount | M / **H** |
| **S3** | SIM guidance closed-loop | 6-DOF-lite quad+target sim; **bearing-rate-null + pursuit-blend**; miss vs N∈{3,4}; **Vc_sched из SpeedPolicy vs τ — показать деградацию τ на crossing**; **envelope-гейт: high-crossing/agile-target → abort**; pixel-in-the-loop; **развязанный 250 Гц thread держит rate при дропе кадров + Smith-predictor lead vs >25 мс задержки** | `control/pilot.py`→`LosGuidancePilot`, `speed.py`, `imm_blender.py` | λ̇ нулится в envelope; miss в допуске для head-on/quartering; high-crossing честно abort'ится; lead компенсирует >25 мс | M / **H** |
| **S4** | REAL SERIAL + FORK (V&V) | `msp_codec.py` (MSP v2 + CRC8); `SerialTransport`; high-rate MSP_RAW_IMU reader; **Betaflight fork + ТРИ обязательных V&V-теста**; wire launch-FSM+verifier; **скаффолдинг независимого HW-kill** | `transport.py`,`commands.py`,`rc_control.py`,`mode_state_machine.py`, `fork_*` | **три fork-теста PASS и залогированы**; AUX1 не поднимается без verifier-PASS+throttle-low; sync <1 мс | **H / H** |
| **B1** | BENCH (props OFF) + **латентность эмпирически** | Реальный Boson на Pi5: raw-count пороги, FFC, bad-pixel map, cam-temp дрейф; **импульсный тепло-источник/фотодиод → timestamp команды мотора = ИЗМЕРЕННАЯ end-to-end задержка**; UART loopback CRC~0 за 10 мин; OS-hardening; **p99 CV < frame под thermal-soak с реальным REACQUIRE в трейсе**; **независимый HW-kill: loss-of-both → motors-off измерено** | Block-01 perf-tooling | измеренная задержка ≤ модели; **p99** CV < frame; throttle-flags чисты; HW-kill <bounded; MSP-silence→ELRS <200 мс измерено | M / **H** |
| **B2** | BENCH seeker-only (tether) | Стрим на консоль, acquisition-box, оператор positive-ID/keypress commit **с ID-grade-pixel гейтом**, лок seeds+держит на движущейся тёплой цели; НЕТ propulsion-auth | `gates/lock.py`, консоль-harness, `dual_key.py`/`physical_keypress.py` (реальный GPIO) | лок переносится через симулир. launch; двухступенчатый интерлок; FIRE≠ARM; ID-гейт блокирует commit на 1–3 px без 2-го кью | M / M |
| **B3** | TETHER airframe (props ON, limited) — **ТОЛЬКО после B1 fork+HW-kill PASS** | Полная цепь perception→LOS→guidance→MSP на привязи; loop-rate под вибрацией; **soft-mount/gyro решение валидировано на реальной вибрации**; boresight; bearing-rate-null нулит λ̇; **ELRS-kill И независимый HW-kill мгновенно disarms под нагрузкой**; throttle-ramp; power tether-cut наготове | всё выше + geofence/ROE онборд + HW-kill | реальная end-to-end латентность подтверждает B1; abort-лестница (оба пути) на привязи; soft-mount residual в допуске | M / **H** |
| **F1** | FREE-FLIGHT non-kinetic | Свободный FOLLOW/approach реальной тепло-цели до CONTACT-standoff (без импакта), инертный/сетчатый нос, ANGLE mode, `synthetic=true`, **оба abort-пути live (автономный + операторский) + LINK_LOSS_TIMEOUT протестирован**; RECON→CONTACT; geofence/time-budget; **envelope-гейт live (high-crossing → abort)**; terminal rate-hold | inverted `verifier.py`, весь стек | стабильный терминальный λ̇-null в envelope; graceful abort на HARD_LOST/geofence/link-loss; гейт доказан отказом стрелять | H / **H** |
| **F2** | FREE-FLIGHT KINETIC (демо-цель) | Только после F1 чисто/повторяемо: live KINETIC handoff unlocks impact-фазу; hardware-backed подписи, tight expiry, geofence, **surveyed/cleared/RSO ground keep-out footprint**, **fail-safe-inert payload**, **target в bounded achievable-g envelope (медленная/некрутящаяся/near-head-on цель для первого kinetic)**, abort-lines; `synthetic=false` audited | hardware-backed key backend + range-safety инфра | все 8+ условий enforced verifier.py; **footprint содержит drop без людей/имущества**; envelope-гейт enforced; RSO-controlled | **H / max** |

---

## 7. Честные риски и где реальная инженерия

**Где реальная инженерия (труднодостижимое — именно оно отделяет работающий перехватчик):**

1. **Бортовой ego-motion-стабильный терминал на CPU (Lens 2 — сердце).** Чистый λ̇ на единственной камере при 200–1000 °/с — это разница между перехватчиком и «гоняется за собственным креном». **Но честно: gyro-only — БАЗА (небо бестекстурно), поэтому выигрывают (а) sub-ms cam↔IMU тайм-синком, (б) охарактеризованной soft-mount transfer function (или жёстким монтажом камеры), (в) гиро-гейтингом инноваций IMM, (г) online gyro scale/bias.** Это инженерия калибровки, не «магия».
2. **Эксплуатация ночной физики до предела ДЕТЕКЦИИ (не наведения):** IRST-style sub-pixel point-target detection расширяет дальность **захвата** до 100–300 м на 1–3 px. **Оговорка: ровно на этой дальности нет ID-дискриминации — захват ≠ positive-ID.**
3. **Развязка vision↔guidance + hard real-time overrun-monitor (Lens 6):** bursty CV кормит метрономный 250 Гц command-stream; overrun-monitor форсит 30 Гц вместо тихого джиттера. Стандартная seeker-архитектура, редко реализованная чисто на Python+Pi.
4. **Криптографически-доказуемый HITL-хребет + независимый HW-kill (Lens 5):** гейт доказывается тем, что НЕ стреляет в synthetic-режиме, а моторное отсечение живёт НИЖЕ FC-софта. Юридически защитимая выставочная демонстрация.

**Где легко споткнуться (честные риски — расширены):**

| Риск | Почему опасен | Митигация |
|---|---|---|
| **Наблюдаемость Vc (Ахиллес наведения)** | Монокулярный пассив не видит дальность/closing-rate; PN требует Vc для усиления; τ вырождается на захвате/кроссинге/импакте | Назвать честно: **bearing-rate nuller, не PN**; Vc_sched из SpeedPolicy; pursuit-blend при низком tau_conf; **жёсткий envelope-гейт head-on/quartering, high-crossing → ROE-abort** |
| **Энергетика 0.7–1.0 g vs payload 140–180 г** | 35°→0.7g, 45°→1.0g; против >1g манёвренной цели внутри ~50 мс задержки многие геометрии не закрываются | **Bounded target-envelope для демо** (скорость/g/геометрия); T/W с полным payload верифицировать; CM5/undervolt → выше g; angle→acro terminal; первый kinetic — медленная near-head-on цель |
| **Сенсорная задержка >25 мс + FFC-jitter** | Sign-инверсия в черновике; не чистый bias; bearing-rate-null чувствителен к delay | **>25 мс в бюджете**; Smith-predictor lead, не один offset; **измерить эмпирически B1**; N≤3; узкая полоса; angle→rate; Boson+ (<6 мс, но 6A003 export) как апгрейд |
| **Betaflight fork (#13416/#13374/#8292) — НЕ существует** | Весь failover-spine висит на форке, который воюет с открытыми upstream-багами | **Safety-critical deliverable с тремя обязательными bench-V&V (props-off → tethered) ДО любой тяги**; ничего props-on пока три не залогированы |
| **Нет kill НИЖЕ FC-софта** | Зависший Pi/баг форка/RF-jam оставят моторы крутиться; ELRS-kill идёт через тот же FC-софт и тот же RF | **Независимый HW-kill (отдельный RX/watchdog-MCU, своя loss-of-signal, режет питание моторов); грибок драйвит его; power tether-cut на привязи** |
| **Операторский ABORT по контестируемому RF** | Грибок достаёт борт только по RF; в jam интент не дойдёт | Разделить автономный vs операторский abort; **LINK_LOSS_TIMEOUT → автономный ditch** (короткий для kinetic); честный worst-case: уход в safe-ditch, не к last-known |
| **Ditch armed kinetic = падающий объект** | «Cut-motors-drop» над площадью с людьми — сам по себе hazard | **Количественный ground keep-out footprint (баллистика+ветер), RSO, exclusion zone ДО kinetic**; powered-to-sector только при здоровом control; cut-drop только в cleared zone; fail-safe-inert payload |
| **Positive-ID на 1–3 px невозможен** | Птица/факел/декой/2-й дрон = похожий high-SNR пик; человек тоже не ID'ит точку | **ID-grade-pixel гейт (motion-signature/больше px) ИЛИ 2-й кью/IFF-deconfliction**; kinematics-consistency; для демо — нет других горячих объектов в FOV (precondition) |
| **Не-R Boson: дрейф порога** | counts дрейфуют с cam-temp, нелинейны к T → абсолютный порог «уходит» | **Part-number decision (R если нужен абсолют); иначе явно ОТНОСИТЕЛЬНЫЙ порог + cam-temp/FFC-state вход + ре-базировка после FFC** |
| **Soft-mount vs гиро** | Гиро жёстко смонтирован, камера на гель — гиро не видит реальное движение камеры под вибрацией; а gyro-only это БАЗА | **Охарактеризовать transfer function ИЛИ жёстко смонтировать камеру**; gating-милестон S2/B3 |
| **60 Гц хрупко вне ROI-лока** | p99-маржа съедается KLT/REACQUIRE/GC/throttle именно при потере лока | **Заголовок: 60 Гц только в ROI-локе, детерминированно 30 Гц иначе**; hard overrun-monitor; **доказать p99 (не медиану) на B1 с реальным REACQUIRE и thermal-soak** |
| **Export: 60 Гц = 6A003.b.4.b** | Регулируемая фича = именно частота, на которой держится loop; kinetic end-use чувствителен | **Точная классификация (EAR не ITAR; 60/30→6A003.b.4.b, 9→6A993.a); legal checkpoint ДО закупки и ДО не-US-person/off-continent демо; 9 Гц fallback НЕ бесплатная де-контроль** |
| **Pi5 thermal throttling** | Тихо сносит латентный бюджет | active-cooler обязателен, governor=performance, DVFS off, undervolt/cap; мониторить throttle-flags; верифицировать airflow в полёте |
| **mock Ed25519 в live** | Подделываемые подписи в kinetic | hardware-backed backend обязателен; verifier отвергает mock+uncleared при synthetic=false |
| **Python GC/GIL jitter** | Промах 16.6 мс дедлайна | pre-allocate, `gc.disable()` на миссию, GIL отпущен в numpy/OpenCV/Cython, SCHED_FIFO |
| **Kinetic step 1** | Неуправляемый вооружённый перехватчик | строгая staged-лестница, inverted verifier default-deny, dual-key/keypress, независимый HW-kill, `manual_kill`→AUX1-low всегда выигрывает |

**Брат, суть честно.** Физика ночи делает **детекцию** лёгкой — но не наведение и не ID. Реальная инженерия в **четырёх местах**: (1) gyro-only-baseline ego-motion с sub-ms тайм-синком и решённым soft-mount → честный λ̇ на CPU; (2) развязка vision↔guidance с overrun-monitor; (3) fail-closed HITL-хребет с **независимым аппаратным kill ниже FC**; (4) принятие наблюдаемостного предела — это **bearing-rate nuller с расписанным Vc и жёстким envelope-гейтом**, а не all-aspect PN-перехватчик. Программа **fundable и демонстрируема до tethered и non-kinetic-free-flight (F1)** уверенно; **free-flight kinetic (F2) гейтится за серьёзной range-safety инфраструктурой**, форком с пройденным V&V и независимым HW-kill. Сделай эти четыре чисто на симе и привязи — и kinetic-демо станет последним аудируемым шагом, а не прыжком.

---

## Что строим первым

Три конкретных первых шага к staged-демо (старт S0 → вход в S1/S4-V&V):

1. **Зафиксировать part-number и измерить cam↔IMU тайм-синк на turntable (S0, gating).** Решить развилку **радиометрический Boson-R vs не-R** (от этого зависит вся логика порога в 3.1 и export-классификация в 3.4), заказать core, и на поворотном столе с известной угловой скоростью измерить **offset камера↔FC-гиро до <1 мс** + gyro scale/bias. Параллельно залочить Y16 V4L2-путь и определить dataclass `ThermalBlob`/`fpv_thermal_blob_sequence.v1` **с полями cam_temp/ffc_state/cam_imu_sync_us**. Это gating, потому что терминальная точность gyro-only-базы целиком висит на этом синке.

2. **Поднять SIM perception с относительным порогом и cam-temp дрейфом (S1).** Синтетик-генератор: холодное небо + горячее пятно (управляемые area/SNR/motion) + звёзды + FFC-freeze + **смоделированный дрейф counts с температурой корпуса** (для не-R сценария). Прогнать CV-pipeline `top-hat → относительный перцентильный порог → CC → subpix-центроид`, переиспользуя `gates/lock.py` FSM и `tracking/reacquire.py`. Gate выхода: subpix <0.1 px, FA-rate против звёзд в допуске, **порог стабилен при cam-temp дрейфе и ре-базируется после FFC.**

3. **Начать Betaflight-fork с тремя обязательными V&V-тестами как harness (S4, highest-risk, параллельно S1).** Скаффолдить `msp_codec.py` (MSP v2 + CRC8) и `SerialTransport` за `transport.py`, и сразу строить **bench-V&V-харнесс под три props-OFF теста**: (1) ELRS AUX-kill disarms пока MSP активно оверрайдит; (2) MSP-silence → RXFAIL → ELRS ≤200 мс измерено; (3) #13416 (моторы-стоп-после-arm) не воспроизводится. Поскольку форк — single-highest-risk deliverable и блокирует любую тягу, он стартует параллельно перцепции, а не после неё, и **до тяги одновременно скаффолдится независимый HW-kill** (отдельный RX/watchdog-MCU), чтобы B1 мог измерить loss-of-both-links → motors-off.