> **[HISTORICAL]** — status as of 2026-07-19. Audit as of 2026-06-25.
>
> **`docs/CHECKPOINT.md` is the source of truth.** Where this document disagrees with it, CHECKPOINT wins.

<!-- Block-03 thermal seeker — independent code-grounded scientific audit.
Method: 9 expert dimensions (mathematician / physicist / systems professional),
each adversarially verified by an independent second agent that re-opened every
cited file:line and re-derived every load-bearing number. 18 agents total.
All file:line references are against the working tree as of this date.
Authored 2026-06-25. -->

# 03-fpv «Архангел» — научный аудит ГСН (математик · физик · профессионал)

**Дата:** 2026-06-25
**Метод:** 9 экспертных направлений, каждое прошло независимую состязательную верификацию (re-open кода по каждой ссылке `файл:строка` + ручной вывод каждого числа). 18 агентов, ~1.77 млн токенов. Верификаторы отдельно отмечены там, где поправляли аналитиков.
**Скоуп:** программная часть / управление / оценка / тесты. Сверено с рабочим деревом.

---

## Вердикт (одним абзацем)

Это **алгоритмически богатый, доктринально чистый и необычно честный к себе** программный прототип *середины* головки самонаведения. Спина «оценка + наведение» сделана реально и грамотно. Но **интегральная цепь detect→decide→intercept не замыкается**: приёмочные тесты во многом тавтологичны, ключевые подсистемы (range-observer, APN, look-down-стек, MTI, Ed25519-авторизация) — это *мёртвый код*, подключённый только в документации, а железо отстаёт на целую подсистему. Интегральный **TRL ≈ 3** (валидация компонентов), при том что миссия требует TRL 7–8. Средний «балл строгости» по 9 подсистемам — **5.8/10**. Самый ценный актив проекта — интеллектуальная честность (есть отдельный «честный» контр-гейт, который сам фиксирует провалы).

| Подсистема | Строгость | Краткий вердикт |
|---|:---:|---|
| Оценка/IMM (математик) | 5.5 | Структура IMM верна; `correlated_r` выведен точно; но ковариация перезаписывается, тест меряет не ту R |
| Наблюдаемость/наведение | 6.5 | Честная капитуляция перед ненаблюдаемостью дальности; но «индекс наблюдаемости» — не FIM, APN и range-observer мертвы |
| Ассоциация/корреляция | 5.5 | MOSSE/PSR — образцово; но ассоциация не махаланобисова, «JPDA» — эвристика |
| Радиометрия/детект (физик) | 5.5 | Все числа Johnson/NETD верны; но `thermal_sim` — игрушка, детектор не polarity-agnostic |
| Кинематика/конверт | 5.5 | Стенка 0.84g/0.28g строго верна; но формула конуса бессмысленна, плант разгоняется |
| Стрэпдаун/тайм-синк | 6.5 | Де-ротация бит-точна, физика тайм-синка верна; но рассинхрон render/derotate даёт ложную λ̇ |
| Безопасность/kill-chain (проф.) | 6.0 | Ядро arming/kill хорошее; но Ed25519 мёртв в рантайме, инв. 5/7 не выполнены |
| Честность тестов/V&V | 7.0 | Образцовая самокритика; Mode A тавтологичен, honest-gate реален но на лезвии |
| TRL/железо | 4.5 | Наука есть, система ниже алгоритмов не построена; железо — сток visible-light квадрик |

---

## I. Как математик

### 1. IMM-фильтр (`seeker/imm.py`) — структурно верен, но три дефекта подрывают строгость

**Что действительно строго:**
- Смешивание мод (Blom–Bar-Shalom), моментное согласование смешанной ковариации, лог-обновление вероятностей мод и комбинированная оценка (Bar-Shalom & Li 11.6.6, **со слагаемым разброса средних**) — всё корректно (`imm.py:387-404, 530-542`).
- **Находка-плюс:** блок `correlated_r` = `[[σ², σ²/dt],[σ²/dt, 2σ²/dt²]]` — это **точно** ковариация вектора `[θ_k, (θ_k−θ_{k−1})/dt]`. Выведено независимо, подтверждено Монте-Карло (ρ=0.7071 теор. vs 0.7073 эмпир.). Настоящее исправление double-count конечной разности.

**Дефекты:**
1. **`[az, el, az_rate, el_rate]` — НЕ «modified-polar».** В настоящих MP-координатах (Aidala–Hammel) есть состояние `1/r`, изолирующее ненаблюдаемую дальность. Здесь дальности нет — это **angle-only расцепленная CV-модель**. Инженерно оправдано, но термин в доктрине (инв. 4) и докстринге неверен.
2. **Перезапись ковариаций мод** (`imm.py:544-547`): обе моды получают одну объединённую `P` (рантайм: `P[0]==P[1]` после 80 кадров при `x[0]≠x[1]`). Нестандартный IMM — нет «узкой» CV-моды, способной стянуть `S`.
3. **NEES/NIS-гейт проверяет НЕ ту `R`.** Тест реконструирует `S` из легаси-диагональной `filt._R` (σ_rate=0.005), живой фильтр — `correlated_r` (σ_rate≈0.0424, ×8.5). «Зелёный» гейт сертифицирует неработающую модель. Истинный драйвер консерватизма (NEES≈3.5, NIS≈0.70) — **рыхлая константная Q**, раздувающая априор `P_pred` в ~640× относительно эмпирической дисперсии инноваций, плюс перезапись из п.2.

**Ложные докстринги:** мода 1 — **white-noise-acceleration**, а не «модель Сингера»; `Q` **не дискретизирована по dt** и не χ²-настраиваема.

### 2. Наблюдаемость и закон наведения — честная капитуляция в обёртке мёртвого кода

**Строго и честно:** `a_cmd = N·Vc_sched·λ̇`, `N=3`, `Vc` планируется — инвариант «дальность не масштабирует усиление PN» **держится** (`compute()` не принимает дальность). Ранг-дефицитность пеленга-только уважена: `InverseRangeObserver` отдаёт дальность только при возбуждении собственным перпендикулярным манёвром, иначе `valid=False`. Математически правильная сдача.

**Дефекты:**
- **«Индекс наблюдаемости» — не FIM.** Истинная скалярная FIM `=(a_perp/Vc)²/σ²=6400` за кадр, код даёт `0.107` — расхождение 4–5 порядков; неверная функциональная форма (`range_observer.py:67-76, 269-281`).
- **Весь range-observer — мёртвый код:** `a_perp` не вычисляется *нигде* в продакшене, наблюдатель не инстанцируется. Хуже: predict-шаг `ρ += ρ²·Vc·dt` крутится каждый кадр (в т.ч. без измерения) и **молча фабрикует уменьшающуюся дальность из `Vc_sched`** — то, что доктрина запрещает; замаскировано `valid=False`.
- **APN мёртв by-design, но `apn_active=True` логируется** (`bearing_rate.py:486-521`). `N_effective` — косметическая интерполяция.

**Коллапс на скрещении/квартовании — структурен** (ненаблюдаемость/энергетика), не артефакт настройки.

### 3. Ассоциация и корреляция

**Образцово:** MOSSE — точная замкнутая форма `H=ΣG⊙F̄/(ΣF⊙F̄+λ)` (`num==G·conj(F)`, `den` веществен-неотрицателен), PSR с окном 11×11, лог+Hanning, неизменяемый FEAR-референс LOBL. **AI-firewall держится:** смещение корреляции отбрасывается, в lock-score идёт только PSR (`pipeline.py:372`); LOS — геометрический центроид.

**Дефекты:** кинематическая стоимость — **линейное** `dist/gate_px`, не квадрат Махаланобиса; гейт евклидов, не χ²; «JPDA» — softmax `exp(−cost)` без P_D/плотности клаттера. Два бага: (1) остаток continuity — кумулятивное среднее без окна → подтверждение прямой быстрой цели **задерживается до кадра 5**; (2) **анти-pull-off veto отключается на каждом coast-кадре**.

---

## II. Как физик

### 4. ИК-радиометрия и детектирование — числа верны, исполняемая модель — игрушка

**Всё ключевое арифметически верно (переderived):**
- Johnson DETECT `113–188 м` (N50=1), ID `14–23.5 м` (N50=8) при IFOV 1.33 мрад. ✓
- `f_px=707`, IFOV `1.414 мрад/px`. ✓
- AGC `20000мК/256=78 мК/DN` затмевает 50 мК NETD (×1.56). ✓
- Стефан–Больцман `dM/dT=4εσT³=5.53 Вт/м²/К` ✓; Эйри при 10 мкм ≈ 1 IFOV ✓.

**Физические дыры (которые сам документ называет обязательными):**
- **Детектор НЕ polarity-agnostic** — только белый top-hat (`detect.py:577-613`), пропускает инверсию контраста (холодное-на-тёплом). Ни один тест её не проверяет.
- **`thermal_sim.py` — гауссово пятно фиксированной амплитуды:** нет NETD/ΔT/ε/fill-factor/атмосферы/дальности/AGC. Дефолтный SNR ≈ **145** (тривиально), а не «десятки метров» реальности. Связывающее ограничение не нагружается.
- Весь look-down-стек (region-CFAR / MPCM / directional-median / MTI / graduated-k) — **по умолчанию ВЫКЛ** и **отсутствует в S3-контуре** (`pixel_loop.py` хардкодит `ffc_state="READY"`).

### 5. Кинематика и конверт — стенка верна, но плант уплывает

**Самое строгое:** `a_lat=g·tan(40°)=8.232 м/с²=0.839 g`; граница аборта и клампа актуатора совпадают. Потолок манёвра `0.28g=0.84/3` **строго следует из PN** (для N=3 нужен запас N/(N−2)=3:1).

**Дефекты:**
- **Формула конуса `θ≈√(2·a_max·R/Vc²)` бессмысленна** на боевых дальностях: 82–164° при R=50–200 м. «15–18°» постулированы, не выведены.
- **Плант не держит 15 м/с:** разгоняется до ~24 м/с (середина) и ~41 м/с (t≈10с); steady-state аналитически **56 м/с**. → `Vc` (из собственной скорости) раздут → **усиление PN `N·Vc` в 1.5–2× больше** документного. g-резерв `SpeedPolicy` вычисляется, но в плант **не подаётся**. Канал **рысканья развязан** от трансляции/пеленга.
- **«Стенка десяти τ» (1.0–1.4 с) не реализована** — терминал по фиксированной дальности (15/5 м), τ-путь ВЫКЛ.
- **Boresight по вектору скорости определяет проблему №1 вне существования** — доминирующая порча λ̇ (стрэпдаун ego-rate) в симе отсутствует.

### 6. Стрэпдаун, ego-motion, тайм-синк — формулы точны, интеграция нет

**Строго:** `derotate.world_pixel` — **бит-точный обратный** forward-render (round-trip 2.3e-13 px). **Физика тайм-синка верна:** `5 мс × ω̇ = 50 рад/с² × 0.005 = 0.25 рад/с ≈ 10× сигнала` (через угловое *ускорение*). Жёсткий монтаж обоснован.

**Дефект интеграции:** рендер roll-стабилизирован, а LOS-компьютер де-ротирует по накопленному крену → **ложная λ̇ до ±0.15 рад/с даже при ИДЕАЛЬНОМ гиро**. Весь ORB/LK/RANSAC/phase-corr ego-кросс-чек и MTI MotionGate **мертвы относительно вывода наведения** (подключён только гиро).

---

## III. Как профессионал (системный инженер)

### 7. Безопасность и kill-chain — хорошее ядро, но доктрина сильнее кода

**Реально хорошо:** kill доминантен/«липкий», не-конечные часы и просрочка → KILLED, HW-kill — настоящий default-deny AND-gate. 58 не-крипто тестов проходят, SIL замыкается (link-loss → ABORT → KILLED → питание снято).

**Критические расхождения:**
- 🔴 **Ed25519 dual-operator авторизация мертва в рантайме.** `OnboardRuntime`/`sil_runtime` не зовут `HandoffVerifier`, фабрикуют `verifier_passed=True` (`onboard_runtime.py:75-77`); крипто не импортируется; **нет защиты от replay**.
- 🔴 **`engage_permitted` потребляется ТОЛЬКО в демо `sil_runtime.py:208`, не в продакшен-`OnboardRuntime`.** Инвариант 3 в бою не обеспечен.
- **Инв. 5 — 1 из 3:** только клапан 0.84 g; нет in-FOV и нет стенки десяти-τ. **Инв. 7:** `HARD_LOST` авто-сброс может усыновить другую цель.
- **Цепь тросовая (tether), не автономная** — софт-ABORT и HW-cut зависят от непрерывного наземного RF.
- 🔴 Пакет **`fpv.safety` не импортируется на чистом клоне** (висячий `from cuas.g2u.verifier …`, `__init__.py:5`); `verifier.py` — всё ещё неинвертированный наземный анти-оружейный блок-лист, не подключён к arming.

### 8. Честность тестов — образцовая самокритика, но зелёное ≠ доказано

- **«100% / суб-см» — артефакт Mode A:** впрыск аналитически-**истинной** λ̇ + шум прямо в наведение (`closed_loop.py:576-621`), seeker обойдён.
- **Честный гейт реален:** коррелированный AR-1 сдвиг λ̇ + шумная looming + джиттер; фиксирует коллапс скрещения (hit→abort) при робастном head-on; «попадает-или-фейлится-безопасно». Carry-through `run_monte_carlo` починен, **но порог на лезвии** (1.20 при >1.2).
- Bit-identity — new-vs-new в процессе, **не ловит смену дефолта**. NEES-гейт односторонний (оптимизм hard-fail, консерватизм xfail). Mode B тонок (4–6 seed), сам фиксирует, что 80-м квартование не закрывает (~7.4 м).

### 9. TRL / реальное время / железо

- **Real-time мимо в 9–48×:** baseline p50 **35.7 мс** (а не 17), full look-down p50 **454 мс** vs бюджет 16.7 мс. **ROI не спасает** — MTI идёт полным кадром (`pipeline.py:293`), в `latency_hwil.py` нет флага ROI.
- **Железо — сток visible-light FPV-квадрик**, стоковый FC (`RX_MSP` выкл): нет FT640/Pi5/форка/kill-MCU/beacon. Софт опережает физику на подсистему.
- ~4–19 файлов RGB racing-gate / YOLO-легаси сосуществуют с тепловой работой.

---

## IV. Что чинить — приоритеты (по leverage)

1. **Де-тавтологизировать приёмку:** S3-гейты → `run_monte_carlo` + Mode B; убрать velocity-aligned boresight, чтобы сим нагружал стрэпдаун ego-rate. Дёшево, без зависимостей, восстанавливает правду.
2. **Чинить ковариацию IMM по-настоящему:** не перезаписывать поканальные `P`; согласовать NEES/NIS-гейт с реальной `correlated_r`; ужесточить рыхлую `Q`. Подключить NIS как живой «model-wrong» аборт.
3. **Подключить `engage_permitted` в `OnboardRuntime`** (не только SIL); реальный COMMIT-state (инв. 7); in-FOV + ten-τ клапаны (инв. 5).
4. **Решить судьбу мёртвого кода, который доктрина считает живым:** range-observer (+ убрать фабрикацию дальности из `ρ`-дрейфа), APN, MTI/LK ego-кросс-чек, look-down-стек — подключить и измерить либо явно пометить нереализованным.
5. **Физика детектора:** polarity-agnostic (чёрный top-hat / `|контраст|`) + тест на инверсию; радиометрический `thermal_sim` (NETD/ΔT/AGC/дальность).
6. **Безопасность как система:** реальная Ed25519 в рантайме + анти-replay; починить `fpv.safety.__init__` (висячий `cuas`); инвертировать `verifier.py` в «разрешать по авторизации».
7. **Real-time:** ROI-гейт тяжёлых операторов *включая MTI* + децимация full-frame; ROI-флаг в `latency_hwil`.

---

**Итог:** проект знает, чего не умеет, и кодирует это в честный контр-гейт — редкая инженерная добродетель. Математическая спина (IMM-смешивание, `correlated_r`, MOSSE, де-ротация) и физический конверт (0.84g/0.28g, Johnson, тайм-синк) местами действительно строги. Но дистанция между **доктриной** и **исполняемым кодом** велика: часть «330 зелёных» проверяет допущения сима, решающие подсистемы — мёртвый код, контур безопасности — трос. Честный TRL-3 прототип *середины* ГСН. Следующий по-настоящему сдвигающий шаг — не алгоритм, а **измерение** (FT640+Pi: Pd-vs-дальность, cam↔IMU тайм-синк, полевой NETD), перебазирующее всю модель ошибок.


---

# Приложения (полные структурированные данные аудита)

> Сгенерировано из вывода воркфлоу. Для каждого направления: вердикт аналитика, находки по убыванию серьёзности, переderived числа, и что независимый верификатор подтвердил/опроверг/добавил.


## M1-estimation-imm  ·  строгость 5.5/10
*Mathematician — estimation & filtering theory*

**Вердикт:** The IMM core is structurally sound: the state is genuinely modified-polar [az, el, az_rate, el_rate]; the mode-mixing (mixing probabilities, moment-matched mixed mean/covariance), the log-space mode-likelihood update, and the combined estimate all match the Blom-Bar-Shalom / Bar-Shalom-Li eq 11.6.6 formulation (re-derived and confirmed). The headline 'correlated_r' fix is mathematically correct as a SINGLE-FRAME covariance: I independently derived Cov([theta_k, (theta_k-theta_{k-1})/dt]) = [[s^2, s^2/dt],[s^2/dt, 2 s^2/dt^2]] (Monte-Carlo confirmed, rho=0.707) and the code's R_frame matches it exactly. But three problems undercut the rigor claims. (1) A per-mode covariance OVERWRITE at imm.py:547 sets BOTH modes' P to the combined P — a known IMM anti-pattern, non-standard and over-inflating per-mode priors. (2) The NEES/NIS consistency test does NOT exercise the R the filter actually uses: it reconstructs S from the legacy DIAGONAL filt._R and injects independent rate noise at sigma=0.005, while the live filter uses correlated_r with rate-variance 0.0018 (72x larger) plus off-diagonal terms — so the green gate validates a model the filter no longer runs. (3) The finite-differenced rate is fed as a quasi-independent measurement with time-WHITE noise, but it has lag-1 measurement-noise correlation of -0.5 (colored), which the Kalman update structurally ignores. Several docstrings are false: Mode 1 is NOT a Singer model (no acceleration state, no decay in F), Q is NOT chi2-tunable (fixed at init) and is not dt-discretized. Measured consistency is CONSERVATIVE (NEES~3.5, NIS~0.70 vs ideal 4) — the safe direction — but for the wrong reasons (test/filter R mismatch), so the number does not credibly certify the live filter's covariance.

**Сильные стороны:**
- IMM mode-mixing is correct Blom-Bar-Shalom: predicted mode prob c_j = sum_i p_ij mu_i (code: trans.T @ mode_probs) and mixing weights mu_{i|j} = p_ij mu_i / c_j (code: trans[:,j]*mode_probs/c[j]). Verified numerically: weights sum to 1 per target mode.  
  *(ev: imm.py:387-404; re-derivation matched code outputs exactly)*
- Combined estimate uses the correct moment-matching: x = sum mu_j x_j and P = sum mu_j (P_j + (x_j-x)(x_j-x)^T), i.e. Bar-Shalom-Li 11.6.6 including the spread-of-means term.  
  *(ev: imm.py:530-542)*
- The single-frame correlated-R block is exactly the true covariance of the stacked [bearing, finite-diff-rate] vector. Independent derivation: Var=s^2; Var(rate)=2s^2/dt^2; Cov=s^2/dt; rho=1/sqrt(2)=0.707. Monte-Carlo (2e6 samples) reproduces [[2.5e-7,1.5e-5],[1.5e-5,1.8e-3]] to 3 sig figs.  
  *(ev: imm.py:435-444; MC check rho=0.7073 vs analytic 0.7071)*
- Log-space mode-likelihood update with max-subtraction is numerically robust; degenerate-S guard via slogdet sign and pinv fallback.  
  *(ev: imm.py:497-526)*
- The NEES/NIS test correctly distinguishes the dangerous (OPTIMISTIC, mean above upper chi2) from the safe (CONSERVATIVE, below lower) direction and HARD-FAILS only optimism, xfailing conservatism. chi2 mean bounds for dof=4,N=5400 re-derived as [3.925,4.076], matching the test output.  
  *(ev: test_filter_consistency_nees.py:359-439; chi2.ppf re-derivation matches)*

**Находки:**

| Сев. | Категория | Вердикт | Находка | Свидетельство |
|---|---|---|---|---|
| high | unsound-assumption | unsound | Per-mode covariance overwrite: both modes set to combined P (classic IMM anti-pattern) | `imm.py:544-547; runtime check: np.allclose(filt._P[0], filt._P[1]) == True after 80 frames` |
| high | doc-code-mismatch | flawed | NEES/NIS test validates a DIFFERENT R than the filter actually runs | `test_filter_consistency_nees.py:137 (R = filt._R), :230-235 (noise sigma from diagonal), :266-271 (z fed as independent rate, not finite-diff); imm.py:430-444 (live correlated R)` |
| medium | unsound-assumption | unsound | Finite-differenced rate has time-correlated (colored) measurement noise the Kalman update ignores | `los.py:290-307 (rate is finite diff of world pixel); imm.py:472-490 (treated as time-white measurement); derivation: lag-1 corr = -sigma^2/dt^2 / (2 sigma^2/dt^2) = -0.5` |
| medium | doc-code-mismatch | flawed | Mode 1 is mislabeled 'Singer model' / 'jink'; it is white-noise-acceleration CV with larger Q | `imm.py:16-19 docstring 'Singer model'; imm.py:308-322 _make_Q (diagonal rate noise only); imm.py:324-339 _make_F (mode-independent CV)` |
| medium | unsound-assumption | unsound | Process noise Q is neither dt-discretized nor chi2-tunable, contradicting docstrings | `imm.py:299-322 (_make_Q constant, no dt); imm.py:191-192 q values; no Q-adaptation in update() (imm.py:349-617)` |
| medium | mis-calibration | mixed | Reported consistency is CONSERVATIVE but for the wrong reason; does not certify the live filter | `pytest output NEES 3.50 / NIS 0.70; test_filter_consistency_nees.py:296-305 bounds; chi2 bounds re-derived [3.925,4.076]` |
| low | design-strength | correct | H = I4 is defensible but couples the double-counted rate | `imm.py:288 (H=eye(4)); los.py:290-307 (rate is derived, not sensed)` |
| low | dead-code | correct | imm_blender.py is a disjoint string-keyed posterior normalizer, not part of the seeker IMM | `tracking/prediction/imm_blender.py:1-51 (pure dict normalization); trajectory_predictor.py:8 imports cuas.prediction.imm_blender (path not present under 03-fpv); seeker IMM modes are CV/MANEUVER not these three` |
| note | design-strength | correct | los.py rate/bearing derivation and signs are correct (supporting check) | `los.py:283-307 (rate Jacobian + signs); derotate.py:27-33 (inverse rotation); geometry.py:180-184 (consistent el sign)` |

- **[HIGH] Per-mode covariance overwrite: both modes set to combined P (classic IMM anti-pattern)** — After the combined estimate, the code stores the COMBINED covariance into BOTH per-mode slots: self._P = [P_combined.copy(), P_combined.copy()] while keeping distinct per-mode means self._x = x_upd. In the canonical IMM the per-mode posteriors (x_upd[j], P_upd[j]) are BOTH carried forward and re-mixed next cycle. Overwriting P_j with the combined P discards each mode's own posterior covariance, so on the next cycle every mode-matched Kalman filter starts from an identical, inflated prior. Confirmed at runtime: after settling, P[0]==P[1] exactly (True) while x[0]!=x[1]. This biases the next-step mode likelihoods (S is identical across modes except via Q) and breaks the IMM's ability to let a 'tight' CV mode and a 'loose' maneuver mode maintain different confidences. The inline comment frames it as a feature ('so the next cycle's mixing sees the correct combined uncertainty') but that is the mixing step's job, not a covariance overwrite.
  - *Рекомендация:* Carry forward the per-mode posteriors P_upd[j] (and x_upd[j]); let STEP-1 mixing recombine them next cycle. If a conservative variant is desired, document it as a deliberate deviation from the standard IMM and quantify the bias on mode probabilities, rather than presenting it as the standard algorithm.
- **[HIGH] NEES/NIS test validates a DIFFERENT R than the filter actually runs** — The consistency harness reconstructs the innovation covariance S from filt._R (the legacy DIAGONAL attribute built in __init__ with rate-variance sigma_meas_az_rate^2 = 2.5e-5) and injects measurement noise as independent Gaussians with the same diagonal sigma. But the live filter default is measurement_mode='correlated_r', which builds a per-frame R with rate-variance 2*sigma_meas_az^2/dt^2 = 1.8e-3 (72x larger) PLUS off-diagonal bearing-rate cross terms (1.5e-5). The test's _predicted_S reads filt._R, never the correlated R_frame the update() actually uses. Therefore the 'green' NEES/NIS gate certifies the consistency of the LEGACY diagonal model, not the shipped correlated model. The filter-assumed rate std (0.0424 rad/s) is 8.5x the test-injected rate std (0.005). This is why measured NIS=0.70 (heavily conservative): in the live filter the rate channel is so over-damped that innovations are far inside the predicted ellipsoid. The headline claim 'correlated_r removes the double-count that made NIS~2 and the posterior over-confident' is not demonstrated by this test, because the test does not run correlated_r and does not feed finite-differenced measurements.
  - *Рекомендация:* Make the harness (a) generate measurements by actually finite-differencing a noisy bearing stream so the rate channel carries the correlated/colored noise the filter models, and (b) reconstruct S from the SAME correlated R_frame the filter builds (expose it or recompute identically). Add an explicit A/B asserting diagonal_r is optimistic and correlated_r is consistent under finite-difference measurements.

**Переderived числа (✓ совпало / ✗ расхождение):**

- ✓ **Correlated-R block for stacked [theta_k, (theta_k - theta_{k-1})/dt] given white bearing noise sigma**  
  - заявлено: R block = [[sigma^2, sigma^2/dt],[sigma^2/dt, 2 sigma^2/dt^2]] (imm.py:435-444)
  - вывод: z1=a_k+n_k, z2=(a_k-a_{k-1})/dt+(n_k-n_{k-1})/dt with n iid N(0,sigma^2). Var(z1)=sigma^2; Var(z2)=2sigma^2/dt^2; Cov(z1,z2)=E[n_k(n_k-n_{k-1})]/dt=sigma^2/dt; rho=1/sqrt(2)=0.7071. MC 2e6 samples -> [[2.499e-7,1.500e-5],[1.500e-5,1.800e-3]], rho=0.7073.
  - прим.: The within-frame R is exactly correct. Caveat: this single-frame block does not capture the -0.5 lag-1 time correlation across frames (Finding 3).
- ✓ **chi2 mean bounds for dof=4, N=5400, alpha=0.05 (NEES/NIS acceptance band)**  
  - заявлено: Test prints [3.925, 4.076]
  - вывод: chi2.ppf(0.025, 21600)/5400 = 3.9249; chi2.ppf(0.975, 21600)/5400 = 4.0758.
  - прим.: Bounds computation is correct. The issue is what S/P they are applied to, not the bounds themselves.
- ✗ **Filter-assumed vs test-injected rate measurement std**  
  - заявлено: Filter (correlated_r) effective rate std and test (diagonal) rate std are consistent
  - вывод: Filter correlated_r rate std = sqrt(2)*sigma_meas_az/dt = sqrt(2)*5e-4*60 = 0.0424 rad/s. Test/diagonal rate std = sigma_meas_az_rate = 0.005 rad/s. Ratio = 8.49.
  - прим.: 8.5x mismatch. The live filter's rate channel is far more uncertain than the test models; the test cannot certify the shipped filter.
- ✗ **Per-mode posterior covariance equality after update (overwrite check)**  
  - заявлено: Filter keeps per-mode covariances (implied by IMM structure)
  - вывод: After 80 frames: P[0] diag = P[1] diag = [1.94e-7,1.94e-7,1.385e-3,1.385e-3], np.allclose(P[0],P[1])=True; x[0]!=x[1].
  - прим.: Confirms imm.py:547 overwrite. Standard IMM would retain distinct per-mode P.
- ✗ **Q discretization / frame-rate invariance**  
  - заявлено: Q is process noise on LOS-rate, chi2-tunable (docstring/config)
  - вывод: Code injects constant rate-variance q_rate=0.005 per step (std 0.0707 rad/s) independent of dt; proper WNA at dt=1/60 would give rate-var q*dt=8.3e-5 with pos-var q*dt^3/3 and cross q*dt^2/2. No chi2 adaptation exists in update().
  - прим.: Q is not dt-discretized, gives zero direct bearing process noise, and is not chi2-tunable. Frame-rate-dependent behavior.
- ✗ **Live NEES/NIS vs ideal 4**  
  - заявлено: Correlated_r fix yields credible (in-band) covariance
  - вывод: Measured: CV NEES=3.500, NIS=0.702; CT NEES=3.506, NIS=0.697. NEES mildly below band [3.925,4.076] (conservative); NIS ~5.7x below ideal (strongly conservative).
  - прим.: Conservative = safe direction, but driven by the test/filter R mismatch, so it does not validate the live correlated_r filter. Claim of credible calibration is unsubstantiated by this test.

**Верификация (уверенность):** High. All 9 findings re-opened at the cited file:line and checked against executable code; the live NEES/NIS test was run (CV NEES=3.588/NIS=0.709, CT NEES=3.464/NIS=0.702, all conservative, matching the analyst's qualitative verdict). The Finding-0 overwrite was confirmed at runtime (P[0] exactly == P[1], x differ; P diag matches claimed values). All six quantitative checks re-derived independently with MC: qc[0] correlated-R block exact (rho=0.7071, MC 0.7075); qc[1] chi2 bounds [3.9249,4.0758] exact; qc[2] rate-std ratio 8.485x exact; qc[3] overwrite confirmed; qc[4] Q non-discretization confirmed; lag-1 corr -0.5006 confirmed. Net: 4 confirmed, 4 partially-confirmed, 0 refuted. The analyst's structural findings (per-mode overwrite, Singer mislabel, undiscretized Q, dead imm_blender, colored rate noise, correct los.py) are all real. Two material corrections: (1) the 'chi2-tunable' doc-mismatch is fabricated, and (2) the conservatism mechanism is an inflated prior from loose Q (~640x in the rate channel), not the R double-count the analyst emphasizes — the R is numerically negligible in the reconstructed S. Plus a missed reproducibility defect (PYTHONHASHSEED-dependent seeds)."

*Опровергнуто/преувеличено аналитиком (поймал верификатор):*
- Finding 4 sub-claim 'The docstring/config also implies Q is chi2-tunable as claimed': the string 'chi2-tunable'/'tunable' does NOT appear anywhere in imm.py (grep returns nothing). No docstring or IMMConfig field claims Q is chi2-tunable. This is a rebuttal of a claim the code never makes — the Q-is-not-adapted observation is correct, but the doc-vs-code 'mismatch' framing is fabricated.
- Finding 5 mechanism 'S ~5.7x too large in the rate channel' is wrong by ~2 orders of magnitude. Empirically the reconstructed S rate channel (S[2,2]=0.0315) is ~640x the empirical rate-innovation variance (4.93e-5), not 5.7x. The NIS rate-channel contribution is ~0.0016 (near zero), so NIS=0.70 is carried by the bearing channels, not damped rate innovations.
- Finding 1/5 framing 'the test runs the diagonal-R model, not the shipped correlated model' is imprecise: the live IMMFilter inside the test runs correlated_r by default (imm.py:188), so the filter's posterior P — and therefore the NEES metric — DOES reflect the correlated model. Only the externally reconstructed NIS uses the diagonal _R, and there R is numerically negligible (0.08% of S). NEES is a valid (if conservative) read on the live correlated filter's posterior.
- Finding 1 implication that the diagonal R is the cause of NIS=0.70 conservatism: refuted numerically. The reconstructed S is dominated by the inflated prior P_pred_combined (loose Q), not by R. Even substituting the correct correlated R[2,2]=1.8e-3 would change S[2,2]=0.0315 by <6%, leaving NIS essentially unchanged. The conservatism survives regardless of which R is used.

*Пропущено аналитиком, добавил верификатор:*
- **[high] True driver of conservatism is the loose constant Q inflating the prior P, not R — and it is mode-coupled by the Finding-0 overwrite** — This is the actual root cause of NEES~3.5 and NIS~0.70 (both conservative). It is more fundamental than the R double-count the analyst centers on: even a perfectly white, perfectly correlated R would leave the filter conservative because the prior is ~2-3 orders too loose in the rate channel. Fix is dt-discretized Q with a calibrated accel PSD (Finding 4) AND retaining per-mode P (Finding 0); the R correction alone will not bring NIS into band.  
  *(ev: Empirical: P_pred_combined[2,2]=0.0315 vs empirical rate-innovation Var=4.93e-5 (~640x). The CV mode injects sqrt(0.005)=0.0707 rad/s rate-process std PER FRAME at 60 Hz, equivalent to an angular-accel PSD ~0.3 rad/s^2/sqrt(Hz). Combined with the Finding-0 overwrite, even the CV mode inherits the inflated combined P every cycle, so there is no 'tight' mode to pull S down.)*
- **[medium] MC seeds depend on PYTHONHASHSEED — NEES/NIS numbers are non-reproducible run-to-run** — The consistency gate's exact numbers are not reproducible across CI runs, undermining its use as a regression gate. Two reviewers will legitimately report different NEES/NIS. Should derive the per-scenario offset deterministically (e.g. a fixed int per name) rather than from the salted built-in hash(). This also means any future 'tightening' of the chi2 band could flake.  
  *(ev: test_filter_consistency_nees.py:242 `rng = np.random.default_rng(seed + (hash(name) & 0xFFFF))`. Python salts str hashing per-process unless PYTHONHASHSEED is pinned: hash('CV')&0xFFFF = 17256 (seed0) vs 22380 (seed1). My run produced CV NEES=3.588/NIS=0.709; the analyst reported 3.500/0.702 — both valid samples of different RNG streams.)*
- **[low] NEES uses P=filt._P[0] which, post-overwrite (Finding 0), equals the combined P with the spread-of-means term added — double-inflated for the consistency metric** — The NEES denominator is the combined P INCLUDING the spread-of-means inflation, which is the correct combined-posterior covariance to test the combined mean against — so this is defensible. But it compounds with the loose-Q inflation to push NEES low. Worth noting that NEES tests the combined estimate, while a per-mode NEES (impossible here because per-mode P was overwritten) would expose the Finding-0 defect directly. The test structurally cannot detect the per-mode covariance loss.  
  *(ev: test:285 `P = filt._P[0]`; imm.py:539-547 stores P_combined = sum_j mu_j*(P_upd[j] + outer(x_upd[j]-x_combined)) into both slots. test:283-284 reconstructs the combined mean xc=sum mu_j*x[j].)*
- **[low] Innovation used for ego gate / NIS diagnostics in live filter is the COMBINED-prediction innovation, not per-mode — diagnostic nis/nis_true are R-only or S-combined, never validated against truth** — The live diagnostic 'nis' (imm.py:569) normalizes by the diagonal sigma_meas_*_rate=0.005 regardless of measurement_mode, so under the default correlated_r it does NOT correspond to the filter's actual measurement model — it is an R-only proxy that the code comment (imm.py:562-566) admits is deliberately conservative. This is internally documented, but it means the live lock_quality/model_ok gate is calibrated to the wrong rate-sigma; combined with the ~640x prior inflation, nis_true will essentially never trip, so the model_wrong_alarm has very low sensitivity in the rate channel.  
  *(ev: imm.py:417 innov_gate uses x_pred_combined_gate; imm.py:569 nis = (innov_gate[2]/sa)^2+... with sa=sigma_meas_az_rate=0.005 (the DIAGONAL legacy sigma, even when measurement_mode=correlated_r); imm.py:579-582 nis_true uses S_combined[2:4,2:4].)*

*Вердикты «опровергнуто/частично»:*
- [partially-confirmed] [1] NEES/NIS test validates a DIFFERENT R than the filter runs — The headline 'the test does not run correlated_r' is too strong: the filter inside the test runs correlated_r (NEES sees it). What is mis-reconstructed is the NIS metric's S. AND critically, in that reconstruction the diagonal R[2,2]=2.5e-5 is only 0.08% of S[2,2]=0.0315 (S is dominated by the inflated prior P_pred), so the R-vs-R mismatch is numerically negligible for NIS — the real distortion is the prior, not R. The analyst over-attributes the problem to R.
- [partially-confirmed] [4] Process noise Q is neither dt-discretized nor chi2-tunable — The Q-structure claims are all CORRECT and well-derived. BUT the sub-claim 'The docstring/config also implies Q is chi2-tunable as claimed' is a MISATTRIBUTION: grep shows the string 'chi2-tunable'/'tunable' does NOT appear anywhere in imm.py. No docstring or IMMConfig field claims Q is chi2-tunable. The analyst is rebutting a claim the code never makes. Flagged in hallucinations_caught.
- [partially-confirmed] [5] Reported consistency is conservative but for the wrong reason; does not certify the live filter — Conclusion (test does not certify live covariance credibility; conservative direction) is CORRECT. The quantitative mechanism is materially wrong: the conservatism is driven by a grossly inflated PRIOR covariance from the loose constant Q (Finding 4), NOT by an R mismatch (Finding 1). The rate channel of NIS contributes essentially zero (~0.0016, vs ideal 1.0 each); the residual NIS=0.70 is carried by the bearing channels (each ~2.9x over-covered). The '5.7x rate channel' figure is unsupported.


---

## M2-observability-guidance  ·  строгость 6.5/10
*Mathematician — observability & optimal guidance*

**Вердикт:** The guidance core is genuinely honest about the one theorem it cannot beat: it implements a_cmd = N*Vc_sched*lambda_dot with Vc SCHEDULED from own airspeed, and the doctrinal invariant 'range never scales the PN gain' holds in code — BearingRateGuidance.compute() takes no range argument, and the inverse-range observer is never instantiated in any production path. The bearings-only rank-deficiency is correctly respected: the InverseRangeObserver reports range only when an own perpendicular-acceleration parallax term is excited, and reports valid=False on a clean collision triangle. That is the mathematically correct surrender. But several load-bearing claims are overstated versus what the code computes: (1) the 'observability index' is NOT a Fisher-information quantity — it is a linear excitation accumulator with the wrong functional form and wrong scaling variable relative to the true scalar CRLB term; (2) the APN term is fully dead-by-design yet apn_active=True is still logged; (3) the entire range-observer + a_perp parallax channel is dead code — a_perp is never computed anywhere in the repo. The crossing collapse is a genuine observability/energy consequence, not a tuning artifact. The pure-pursuit/PN blend is a heuristic, not collision-triangle PN, and N_effective is a cosmetic interpolation.

**Сильные стороны:**
- The doctrinal invariant 'range never scales the PN gain' is enforced structurally, not by convention. compute() has no range parameter; the PN magnitude is Vc (scheduled), set at bearing_rate.py:387 and used at :483-484 (brn = N*acquire_gain*Vc*lambda_dot). The range observer's output is never read by the gain path.  
  *(ev: fpv/guidance/bearing_rate.py:344-351,387,483-484; test_doctrine_invariants.py:test_inv1 asserts compute() signature excludes {range,estimated_range_m,range_m,r_hat})*
- The inverse-range EKF correctly filters rho=1/r (bounded as r->inf), and its measurement update is gated to ONLY fire when own perpendicular maneuver a_perp exceeds a floor — i.e. it refuses to manufacture range on a clean collision triangle (a_perp~0), reporting valid=False, range_m=None, range_sigma=inf.  
  *(ev: fpv/seeker/range_observer.py:264 (rho_dot=rho^2*Vc closing drift, dimensionally correct d(1/r)/dt=Vc/r^2), :292-302 (measurement update gated on a_perp>=min_a_perp), :307-314 (gate), test_range_observer.py:33-60 (unobservable-without-maneuver test))*
- The crossing-geometry abort is grounded in a correct g-budget inequality, not an arbitrary threshold. required_g = lambda_dot_mag*Vc*N/9.81 (bearing_rate.py:436) is the standard PN lateral demand divided by g; for a 0.15 rad/s crosser at Vc=20,N=3 this is 0.92 g against an 0.84 g body — genuinely out of envelope.  
  *(ev: fpv/guidance/bearing_rate.py:436-453; re-derived: 0.15*20*3/9.81=0.917 g > tan(40deg)=0.839 g)*
- The IMM is a correct, standard Bar-Shalom 2-mode (CV/Singer) filter in modified-polar [az,el,az_rate,el_rate] with proper mode-mixing, spread-of-means combined covariance, and log-space likelihoods; the correlated-R model correctly removes the finite-difference rate double-count (the NIS~2 bug).  
  *(ev: fpv/seeker/imm.py:383-404 (mixing), :430-461 (correlated R block [[s^2,s^2/dt],[s^2/dt,2s^2/dt^2]]), :528-547 (combined covariance with outer-product spread term))*

**Находки:**

| Сев. | Категория | Вердикт | Находка | Свидетельство |
|---|---|---|---|---|
| high | mis-calibration | flawed | The 'observability index' is NOT a Fisher-information / FIM quantity — wrong functional form and wrong scaling variable | `fpv/seeker/range_observer.py:67-76 (docstring 'instantaneous FIM-toward-range'), :269-281 (info_inc = a_perp*dt/sigma*rho), :113-118; my derivation: true FIM=(a_perp/Vc)^2/sigma^2=6400 vs code=0.107` |
| medium | dead-code | mixed | APN term is fully dead — apn_active=True is logged with zero acceleration contribution (doc-vs-code mismatch the prompt flagged) | `fpv/guidance/bearing_rate.py:44-49 (docstring claims APN live), :234,251-252 (config knobs), :486-518 (apn_az=apn_el=0.0; apn_active=True), :521-522 (apn_az/el added but are 0)` |
| medium | dead-code | unverifiable | Entire inverse-range observer + parallax channel is dead code: a_perp is never computed anywhere in the repo, observer never instantiated in production | `grep: InverseRangeObserver( only in range_observer.py:195 (docstring) and tests; a_perp produced nowhere in production; closed_loop.py:500 (range_m=ground truth), :743 (fed to pilot); bearing_rate.py:560-564 (t_go from looming only)` |
| medium | unsound-assumption | unsound | Parallax measurement update discards the SIGN of the induced LOS-rate (uses /lambda_dot/), introducing a sign-blind range bias the tests cannot expose | `fpv/seeker/range_observer.py:50-59 (signed model), :294-296 (z=abs(lambda_dot), H>=0), test_range_observer.py:96-102 (synthesizes z from the model itself)` |
| low | mis-calibration | mixed | N_effective is a cosmetic blend interpolation, not a navigation ratio; 'pure pursuit' is a bearing-proportional heuristic, not collision-triangle pursuit | `fpv/guidance/bearing_rate.py:468-476 (pursuit=Vc*az), :520-522 (blend), :554-557 (n_effective interpolation)` |
| low | unverifiable-claim | mixed | t_go is sound-by-omission but the 'ten-tau wall' commit logic is not in this code path; t_go is range-free only because it is usually inf | `fpv/guidance/bearing_rate.py:560-564 (t_go gate); fpv/guidance/command_map.py:301-337 (terminal switches: legacy range-keyed, use_tau default False); looming.py:18-24 (tau_confidence collapses in exactly the regimes guidance runs)` |
| low | unverifiable-claim | mixed | Inv-1 closed-loop test feeds SIM GROUND-TRUTH range to the pilot — the invariant holds for the gain but range still enters terminal timing via an oracle | `fpv/guidance/closed_loop.py:498-500,743; fpv/guidance/command_map.py:301-337 (legacy range-keyed terminal switches); use_tau_terminal default False (command_map.py:106)` |
| note | design-strength | correct | Crossing collapse to ~26 m is a genuine observability+energy consequence — NOT a tuning artifact (confirming the design claim) | `fpv/guidance/tests/test_s3_honest_acceptance.py:91-129; bearing_rate.py:430-453 (crossing required_g vs achievable); looming.py:21-24 (tau->inf on crossing)` |

- **[HIGH] The 'observability index' is NOT a Fisher-information / FIM quantity — wrong functional form and wrong scaling variable** — The module docstring (range_observer.py:67-76, 113-118) and dataclass field repeatedly call the index 'the instantaneous FIM-toward-range' and 'published FIM-toward-range index'. The code computes info_inc = (a_perp*dt/sigma_lambda_dot)*rho (line 273), summed over a window. The true scalar Fisher information for estimating rho from the parallax measurement h(rho)=a_perp*rho/Vc with noise R=sigma^2 is I = (dh/drho)^2 / R = (a_perp/Vc)^2 / sigma^2. The code's quantity is (a) LINEAR in a_perp, not quadratic; (b) LINEAR in 1/sigma, not quadratic; (c) scaled by rho (1/m), whereas the true FIM scales by 1/Vc^2 and is independent of rho. Numerically the true per-frame FIM at a_perp=8,Vc=20,sigma=0.005 is 6400; the code's info_inc is 0.107. They are not the same object up to a constant — the dependence on a_perp, sigma, Vc, and rho all differ. It is a heuristic excitation/SNR accumulator (|a_perp|*time above the LOS-noise floor), which happens to be monotone in maneuver strength (so the monotonicity test passes) but is not the CRLB-grounded quantity the doctrine claims and cannot be used to read off a range variance or a CRLB.
  - *Рекомендация:* Either (a) rename the field to an honest 'parallax-excitation index' / 'maneuver SNR' and drop the FIM/CRLB language, or (b) actually accumulate the FIM: I_window = sum_k (a_perp_k/Vc_k)^2 / sigma_lambda_dot^2 * dt, and gate on a real information threshold (e.g. range_sigma derived from 1/sqrt(I)). The current index conflates 'we maneuvered enough' with 'range is information-theoretically observable', which are not the same and will mis-gate at low Vc (true FIM blows up as 1/Vc^2, the heuristic ignores Vc entirely).

**Переderived числа (✓ совпало / ✗ расхождение):**

- ✓ **Max achievable lateral g at theta_max=40 deg**  
  - заявлено: ~0.84 g (docstring/comments: '40 deg -> ~0.84 g'; abort uses achievable_g=tan(theta_max))
  - вывод: a_max = g*tan(40deg) = 9.81*0.8391 = 8.23 m/s^2; achievable_g = tan(40deg) = 0.8391
  - прим.: Correct. The 35/45 deg figures in bearing_rate.py:54-55 (0.70 g, 1.00 g) also check out (tan35=0.700, tan45=1.000).
- ✓ **Crossing required_g at threshold lambda_dot=0.15 rad/s, Vc=20, N=3**  
  - заявлено: Abort fires because required_g > achievable_g (~0.84 g) on a 0.15 rad/s crosser
  - вывод: required_g = lambda_dot*Vc*N/9.81 = 0.15*20*3/9.81 = 0.917 g > 0.839 g
  - прим.: Correct: a threshold crosser is already ~9% over the g-budget; the abort inequality is physically grounded. The lambda_dot that exactly saturates a_max is 0.137 rad/s (7.9 deg/s), slightly below the 0.15 threshold, so the classifier+abort are mutually consistent.
- ✓ **Inv-3 default-deny test: required_g at az_rate=2.0 rad/s**  
  - заявлено: Test asserts required_g > achievable_g for an 'extreme crossing'
  - вывод: 2.0*20*3/9.81 = 12.2 g >> 0.84 g
  - прим.: Trivially true (12 g vs 0.84 g). The test is sound but undemanding — it proves abort fires somewhere in 40 ticks, not that the boundary is calibrated.
- ✗ **'Observability index' vs true scalar Fisher information for rho**  
  - заявлено: Index is 'the instantaneous FIM-toward-range' (range_observer.py:67-76)
  - вывод: True FIM = (dh/drho)^2/R = (a_perp/Vc)^2/sigma^2 = (8/20)^2/0.005^2 = 6400 per frame. Code info_inc = a_perp*dt/sigma*rho = 8*0.02/0.005*(1/300) = 0.107.
  - прим.: NOT the FIM. Wrong order in a_perp (linear vs quadratic), wrong order in 1/sigma (linear vs quadratic), scaled by rho instead of 1/Vc^2, and carries dt (an accumulator, not an instantaneous information). It is a heuristic excitation metric; monotone in a_perp so tests pass, but the FIM/CRLB language is unjustified.
- ✓ **rho closing-drift term rho_dot = rho^2 * Vc**  
  - заявлено: d(1/r)/dt = Vc/r^2 = rho^2*Vc (range_observer.py:264)
  - вывод: rho = 1/r => d(rho)/dt = -(1/r^2)*dr/dt; closing means dr/dt = -Vc, so d(rho)/dt = +Vc/r^2 = rho^2*Vc
  - прим.: Dimensionally and sign-wise correct for the propagation. This part of the EKF is right.
- ✓ **range_sigma via delta method on r=1/rho**  
  - заявлено: sigma_range = rho_sigma/rho^2 (range_observer.py:311)
  - вывод: r=1/rho => dr/drho = -1/rho^2 => sigma_r = |dr/drho|*sigma_rho = sigma_rho/rho^2
  - прим.: Correct first-order (delta-method) propagation.
- ✓ **Looming consistency: closing_normalized = 1/(2*tau)**  
  - заявлено: rho_dot/rho = A_dot/(2A) = 1/(2*tau) (range_observer.py:39, :286)
  - вывод: A proportional to rho^2 => A_dot/A = 2*rho_dot/rho => rho_dot/rho = A_dot/(2A); tau=A/A_dot => A_dot/A=1/tau => rho_dot/rho = 1/(2*tau)
  - прим.: The area-growth relation is correctly derived and implemented. Note it yields the OBSERVABLE fractional rate Vc*rho only; it does not pin absolute rho without a size prior, which the docstring correctly states.

**Верификация (уверенность):** high — all 8 findings opened at their exact file:line and confirmed; all 7 quantitative checks re-derived numerically and match (FIM 6400 vs code 0.107; tan40=0.839; req_g 0.917/12.23; rho^2*Vc=2.22e-4; 1/(2tau)=0.125). No hallucinations: every load-bearing claim is supported by the executable code. Finding [3] was strengthened with a direct EKF experiment showing sign-flip invariance and 88% error collapse under a 0.005 rad/s crossing-rate contamination, proving the convergence test is tautological. Added 4 missed issues, the most important being the unconditional Vc_sched-driven rho drift in the predict step (medium) that contradicts the module's own range-unobservable doctrine.

*Пропущено аналитиком, добавил верификатор:*
- **[medium] EKF rho 'predict' step double-counts the closing drift, biasing rho upward between valid measurements** — The propagation term is dimensionally correct (verified QC4) but is integrated unconditionally with no observability gate, so the filter mean is driven by Vc_sched during the unobservable regime that dominates the engagement. This is a real (if currently inert) bias source that contradicts the module's own doctrine.  
  *(ev: range_observer.py:264-266: rho_dot_closing = rho^2*Vc; self._rho += rho_dot_closing*dt. This deterministic drift is applied EVERY frame including all the (overwhelmingly common) frames where a_perp < min_a_perp_mps2 and NO measurement update fires (the measurement at :292-302 is gated on the same a_perp floor). With the default rho_init=1/500 and the closing drift always positive, the unobserved state marches rho upward (range downward) open-loop, driven by the SCHEDULED Vc — a quantity the module docstring (:13-18) insists is never an observed truth. So on a passive collision triangle the observer silently fabricates a shrinking range from Vc_sched alone, exactly the 'manufacture range from a straight bearing' the doctrine claims to forbid. It is masked only because valid=False suppresses range_m, but the drifting rho is still the prior the next maneuver-update corrects from.)*
- **[low] EKF process noise q_rho_rate is ~25x too small to cover the deterministic closing drift it is meant to model** — Even setting aside that the observer is unwired, its reported range_sigma would be optimistic because the process-noise budget does not account for the Vc_sched modelling error that the deterministic drift injects. Minor since diagnostics-only, but it undpercuts the 'always honour the wide sigma' contract.  
  *(ev: config q_rho_rate=(1/2000)^2=2.5e-7 m^-2 (:176), added as P += q_rho_rate*dt (:267). But the actual per-frame deterministic rho change at r=300, Vc=20 is rho^2*Vc*dt = 2.22e-4*0.02 = 4.4e-6 m^-1, and the modelling uncertainty on it (Vc_sched is admittedly unknown to ~tens of %) is order 1e-6 m^-1, whose variance ~1e-12 is dwarfed... conversely the prior sigma rho_init_sigma=1/200=5e-3 gives P0=2.5e-5, so q adds only ~1% of P0 per second. The covariance therefore tightens (via the measurement update) far faster than the un-modelled Vc_sched error justifies, so range_sigma (delta-method, :311, verified QC5) is reported tighter than the true uncertainty — an overconfident sigma on a quantity the doctrine says must always read wide.)*
- **[low] abort_g_margin default changed to 1.0 and effective_max_a_cmd clamps at exactly a_max, so the abort boundary and the actuator clamp coincide — abort can never fire on HEAD_ON/QUARTERING via the envelope path before the clamp engages** — Not a bug, but the envelope-abort branch is effectively unreachable in normal operation (clamp catches everything at the same threshold) and its boundary is untested — the analyst's QC2 note that the abort test is 'undemanding' understates this: the entire HEAD_ON/QUARTERING envelope-abort path is dead in practice.  
  *(ev: bearing_rate.py:246 abort_g_margin=1.0 (comment: 'command clamp is the real guard'); :529 envelope_ok = a_total <= a_max*1.0; clamp :550-552 uses effective_max_a_cmd()=a_max_mps2() (:288-289). The envelope abort (:535) fires only when a_total STRICTLY exceeds a_max, and the clamp caps at exactly a_max. So for HEAD_ON/QUARTERING the abort path is a razor-thin equality boundary — any command at or below a_max passes and is then clamped, meaning the 'envelope abort' is essentially decorative for non-crossing geometry; the only operative abort is the HIGH_CROSSING classifier at :435. The Inv-3 default-deny test (QC2, 12.2 g >> 0.84 g) only exercises the HIGH_CROSSING branch, never the envelope branch, so the envelope abort's calibration is untested.)*
- **[low] Looming closing_normalized cross-check is computed and published but never actually cross-checked against rho_dot/rho anywhere** — The doctrine sells the looming channel as a consistency cross-check on the parallax/Vc geometry. In code it is a computed-and-forgotten field. Combined with the observer being unwired, the entire looming-fusion story in this module is aspirational.  
  *(ev: range_observer.py:283-286 computes closing_normalized=1/(2*tau) and stores it in the RangeEstimate (:323), and the docstring (:65-76, :119-121) repeatedly calls it a 'consistency cross-check'. But nothing in update() ever compares closing_normalized to the filter's own implied fractional rate rho_dot/rho = rho*Vc — it is a passive output field. test_looming_fractional_rate_matches_area_growth_relation (:161-175) only checks the arithmetic 1/(2*tau), not any consistency gate. So the advertised 'cross-check' that would catch a Vc_sched / looming disagreement is not implemented; it is a label on an unused scalar.)*


---

## M3-association-correlation  ·  строгость 5.5/10
*Mathematician — data association & correlation tracking*

**Вердикт:** The MOSSE/FEAR correlation channel is genuinely rigorous and correctly implemented: the FFT closed-form H = ΣG⊙conj(F)/(ΣF⊙conj(F)+λ) is exact (verified: num==G·conj(F), den==F·conj(F), den is real-nonneg), the online learning-rate update is the standard convex blend, PSR is computed correctly with an 11×11 exclusion and a div-by-zero floor, log+normalize+Hanning preprocessing is textbook, and the FEAR immutable LOBL reference is truly immutable (lr=0 makes update() a no-op; measure() adapts only the dynamic filter). The AI-firewall invariant holds: in pipeline.py:372 the correlation offset (_dx,_dy) is discarded and only PSR flows to set_correlation_confidence → lock-score; LOS uses the geometric centroid. HOWEVER the association/gating layer is NOT statistically grounded in the estimator covariance: the kinematic cost is a LINEAR normalized distance dist/gate_px (not a squared-Mahalanobis), the gate is a fixed Euclidean disc (not a χ² gate on the innovation covariance S), the "JPDA" is a heuristic exp(−cost) softmax with no detection probability, clutter density, or Gaussian likelihood normalization (not true marginal association probabilities), and the combined cost folds appearance/intensity into what is then re-used as a position-mixing weight. Two real defects: the multi-track continuity residual is a lifetime cumulative mean with no windowing, so the velocity-init transient on the spawn frame permanently inflates it and DELAYS confirmation of perfectly straight fast targets (a 25 px/frame CV target cannot confirm until frame 5); and the anti-pull-off veto is fully disabled on every coast frame (ref=None when missed_frames>0), removing the appearance firewall exactly at the post-dropout horizon-crossing geometry it was built to defend.

**Сильные стороны:**
- MOSSE FFT closed-form is exact and matches Bolme 2010: per-element num = G⊙conj(F), den = F⊙conj(F), H = num/(den+eps); peak offset recovery is exact (a (+4,+3) shift returns dx=4.000,dy=3.000) and self-correlation PSR is huge (≈709) vs noise PSR≈3.2.  
  *(ev: correlation.py:98-122; verified numerically)*
- FEAR dual-template immutability is genuine: the reference filter is constructed with lr=0.0, so its update() blend (1-lr)*num + lr*(...) is the identity; CorrelationChannel.measure(adapt=True) only ever calls _dyn.update, never _ref.update.  
  *(ev: correlation.py:147,164-165; verified _ref._num unchanged after feeding a different chip)*
- PSR firewall invariant is correctly wired: pipeline discards the correlation peak offset (_dx,_dy underscore-binding) and feeds only normalized PSR to set_correlation_confidence, which modulates the lock-score lifecycle; the live LOS uses los_centroid = snap.centroid_px (the geometric centroid).  
  *(ev: pipeline.py:372-375,390-397; track.py:456-463,714-719)*
- PSR computation and numerical guards are correct: exclude=5 yields exactly an 11×11 suppression window as documented, the sidelobe std has a 1e-6 floor, and a flat response returns PSR≈0 rather than NaN.  
  *(ev: correlation.py:125-134; verified flat-response PSR=0.000)*

**Находки:**

| Сев. | Категория | Вердикт | Находка | Свидетельство |
|---|---|---|---|---|
| high | unsound-assumption | flawed | Kinematic association cost is linear normalized distance, not squared-Mahalanobis; the gate is a Euclidean disc, not a χ² gate | `track.py:788-789 (Euclidean gate), 853 (kin=dist/gate_px), 404-413 (scalar covariance floor); pipeline.py:407-409` |
| high | mis-calibration | flawed | JPDA soft-update is a heuristic softmax, not marginal association probabilities | `track.py:802-823, 856-858; test_r10_jpda.py:34-40; verified betas=exp(-cost) with no P_D/clutter/likelihood norm` |
| high | correctness-error | flawed | Multi-track continuity residual is a non-windowed lifetime mean; spawn-frame velocity-init artifact permanently inflates it and delays confirmation of straight fast targets | `track_manager.py:96-97, 99-112, 244-247; verified 25 px/fr CV target confirms only at frame 5` |
| medium | unsound-assumption | flawed | Anti-pull-off veto and appearance/intensity cost are fully disabled on every coast frame | `track.py:763-766, 840-841, 848-851, 742-743` |
| low | unsound-assumption | flawed | Intensity veto is one-sided: only hotter candidates are rejected, never anomalously cold ones | `track.py:850-851; verified 0.002× peak passes` |
| low | unsound-assumption | flawed | MultiTrackManager uses greedy GNN with no global (Hungarian/auction) optimum and no covariance-weighted cost | `track_manager.py:147-148 (docstring 'multi-hypothesis'), 188-203 (greedy sort-by-distance)` |
| note | doc-code-mismatch | correct | MOSSE den accumulates without λ; regularizer λ shares the same _eps symbol as the preprocess std-floor | `correlation.py:80,96,101,110,115` |
| note | dead-code | correct | Tracklet _window default maxlen=5 vs config confirm_window requires runtime re-normalization | `track_manager.py:84, 221, 240-241` |

- **[HIGH] Kinematic association cost is linear normalized distance, not squared-Mahalanobis; the gate is a Euclidean disc, not a χ² gate** — The persona's core question answered directly: the kinematic term is kin = dist/gate_px (track.py:853), a LINEAR ratio in [0,1), NOT a (squared-)Mahalanobis distance dᵀS⁻¹d using the innovation covariance S. The gate test is dist >= gate_px (track.py:789), a fixed-radius Euclidean disc, NOT a χ² gate at a chosen confidence level on S. There is an A4 'covariance-sized' floor (set_search_radius, track.py:404-413) but it only sets a scalar isotropic radius = min(3σ·f_px, 3·base) — it projects the IMM bearing-innovation std to one pixel radius and takes a max with the fixed gate; it never forms S⁻¹ and never produces an elliptical/anisotropic gate. Consequently the gate cannot account for correlated az/el uncertainty or a stretched along-track covariance, and the association cost is not a likelihood. This is a principled-but-ad-hoc heuristic, defensible for a single dominant target but not the textbook GNN/Mahalanobis construction the surrounding doctrine language implies.
  - *Рекомендация:* If statistical gating is wanted, gate on dᵀS⁻¹d <= χ²_{2,α} with S = HPHᵀ+R from the IMM, and use 0.5·dᵀS⁻¹d + 0.5·ln|2πS| as the kinematic log-likelihood cost. At minimum, rename/redocument the current scheme as a normalized-Euclidean heuristic, not a Mahalanobis gate.
- **[HIGH] JPDA soft-update is a heuristic softmax, not marginal association probabilities** — _jpda_centroid (track.py:802-823) computes betas = exp(-(cost - c_min)/scale) over in-gate candidates, normalizes, and adds a pseudo-weight jpda_prediction_weight·max(beta) at the predicted state. These are NOT JPDA marginal probabilities: (1) cost is the COMBINED kinematic+appearance+intensity cost (track.py:856-858), so appearance/size enters a position-mixing weight — a category error in a kinematic estimator; (2) there is no detection probability P_D, no spatial clutter density λ, and no Gaussian likelihood normalization 1/√|2πS|, so the weights are not proportional to true association likelihoods; (3) the 'no-target / all-missed' hypothesis is modeled crudely as a single prediction pseudo-weight rather than the β₀ clutter/miss term. The r10 tests only assert the blended x lands strictly between target and intruder (test_r10_jpda.py:39-40), which any monotone softmax satisfies — they do not test marginal-probability correctness, so they are non-discriminating w.r.t. the JPDA claim. It is a reasonable position-regularizer that prevents full pull-off, but calling it JPDA overstates its rigor.
  - *Рекомендация:* Either (a) compute proper single-target PDA betas from the kinematic likelihood N(z;ẑ,S) with explicit P_D and clutter density and use the PDA-combined innovation, or (b) keep the heuristic but document it as a 'softmax position regularizer,' not JPDA, and drive the softmax by a PURELY kinematic cost (dist only) so appearance never warps reported position.
- **[HIGH] Multi-track continuity residual is a non-windowed lifetime mean; spawn-frame velocity-init artifact permanently inflates it and delays confirmation of straight fast targets** — Tracklet.mean_residual = _residual_sum/_residual_n accumulates over the ENTIRE lifetime with no sliding window or forgetting (track_manager.py:96-97, 99-112). On the spawn frame velocity=(0,0), so the first on_hit computes a residual against a stationary CV prediction equal to roughly the full per-frame displacement of the target. For a genuinely straight constant-velocity target this transient is baked into the lifetime average forever. Verified: a perfectly linear 25 px/frame target — the most trajectory-continuous signal possible — is BLOCKED from confirmation until frame 5 purely because its cumulative mean residual (25→12.5→8.33→6.25→5.0) only dilutes below max_continuity_residual_px=6.0 at frame 5, even though every post-velocity-learning residual is ~0. The statistic therefore conflates the velocity-initialization transient with maneuver, penalizing exactly the fast genuine movers the backstop is meant to confirm, while the 6px absolute cap is also velocity-coupled (a fast straight target and a slow jittery one are not separable by a single distance threshold). A windowed RMS residual or excluding the first 1-2 frames would be statistically sound; the lifetime cumulative mean is not.
  - *Рекомендация:* Use a sliding-window (deque) residual over the last K frames, or skip the first 1-2 residual samples (velocity not yet observable), and ideally normalize the residual by the learned speed (residual/|v|) or test it as a χ² against process+measurement noise rather than a fixed 6px cap.

**Переderived числа (✓ совпало / ✗ расхождение):**

- ✓ **MOSSE closed-form H = num/(den+λ) with num=G⊙conj(F), den=F⊙conj(F)**  
  - заявлено: H* = ΣG⊙F* / (ΣF⊙F* + λ) (docstring/correlation.py:6,86-87)
  - вывод: Computed P=preprocess(chip), F=fft2(P); checked num==G·conj(F) exactly (allclose True) and den==F·conj(F) exactly with imag(den) max = 0.0; λ added only at division as eps=1e-3
  - прим.: Closed form is exact and matches Bolme 2010 element-wise MOSSE. den correctly accumulated without λ; λ only in the H division.
- ✓ **MOSSE peak-offset (dx,dy) recovery for a known translation**  
  - заявлено: correlate returns peak offset from chip centre (correlation.py:112-122)
  - вывод: Trained on a centred Gaussian blob; shifted target by (+4,+3) px; correlate returned dx=4.000, dy=3.000
  - прим.: Sub-pixel-exact at integer shifts; offset convention (px - n//2) is correct given the centred desired Gaussian (no fftshift needed).
- ✓ **PSR = (peak - sidelobe_mean)/sidelobe_std with 11×11 exclusion**  
  - заявлено: exclude=5 -> 11x11 window (correlation.py:125-134)
  - вывод: Window indices [py-5, py+5] = 11 elements per axis = 11×11; self-correlation PSR≈709, noise PSR≈3.2, flat-response PSR=0.000 (guarded)
  - прим.: Exclusion size, ordering, and 1e-6 std floor all correct; PSR cleanly separates trained-on-self from noise.
- ✓ **Combined association cost = w_k·(dist/gate) + w_a·|ln(area_ratio)|/ln(veto) + w_i·min(|Δsnr|/snr,1)**  
  - заявлено: cost formula (track.py:853-858)
  - вывод: Hand-computed for dist=10,gate=48,area 120/100,snr 11 vs 10: 1.0·0.2083 + 2.0·app + 0.5·0.1 = 0.65629; code returned 0.65629 (match)
  - прим.: Cost matches, BUT kin term is LINEAR dist/gate, not squared-Mahalanobis; not a χ² statistic.
- ✗ **JPDA soft centroid blend weights**  
  - заявлено: likelihood-weighted marginal association (track.py:802-823, docstring)
  - вывод: For costs (0.2,0.6), scale 1: betas=exp(-(c-cmin))=(1.0,0.6703), bpred=0.5·max(beta)=0.5; blended x = (1·100+0.6703·120+0.5·105)/(1+0.6703+0.5) = 107.329; code returned 107.329
  - прим.: Arithmetic of the heuristic is self-consistent, but betas are bare exp(-cost) — NOT JPDA marginals (no P_D, no clutter density, no Gaussian likelihood normalization). Disagree on the 'JPDA' label, not the arithmetic.
- ✗ **Continuity-confirmation latency for a straight 25 px/frame target (residual cap 6 px)**  
  - заявлено: trajectory-continuous targets confirm via N-of-M + low CV residual (track_manager.py:237-247)
  - вывод: Lifetime mean residual evolves 25→12.5→8.33→6.25→5.0 (spawn-frame velocity=0 bakes in a ~25px first residual); crosses below 6.0 only at frame 5, so confirmation is delayed to frame 5 despite perfect linearity
  - прим.: The non-windowed cumulative mean + velocity-init transient penalizes genuine fast straight movers — a real statistical-soundness defect, not just a tuning issue.

**Верификация (уверенность):** high — Every one of the analyst's 8 findings was independently re-opened at the cited file:line and CONFIRMED against the executable code; 6 of them were additionally reproduced with live experiments (linear-distance cost 0.65629, JPDA blend 107.329, continuity confirm at frame 5, coast-frame veto bypass associating a 10x intruder, one-sided cold-candidate pass, REACQUIRE gate=144). All 5 quantitative checks re-derived correctly (QC0-QC4 exact; QC5 sequence reproduced exactly). The only discrepancy is cosmetic PSR magnitudes in QC2 (seed-dependent, conclusion intact). No hallucinations of substance. I add 3 missed issues, the most important being that the JPDA prediction pseudo-weight degenerates to a constant — further undermining the 'JPDA' label. The analyst's analysis is rigorous and code-grounded.

*Опровергнуто/преувеличено аналитиком (поймал верификатор):*
- QC[2] PSR numbers: analyst reported self-correlation PSR≈709 and noise PSR≈3.2; my independent run gave PSR self≈698.6 and noise≈4.34. The numbers are seed/sigma-dependent and the QUALITATIVE conclusion (11x11 exclusion window = 121 cells, clean separation trained-on-self vs noise, 1e-6 std floor) is fully correct, so this is a minor numerical discrepancy, NOT a substantive hallucination. No load-bearing claim was found to be unsupported by the code — every cited file:line matched.

*Пропущено аналитиком, добавил верификатор:*
- **[medium] JPDA prediction pseudo-weight b_pred is a CONSTANT (= jpda_prediction_weight), independent of candidate quality** — A principled JPDA β₀ (no-target/clutter) weight should GROW when all in-gate candidates fit poorly (pull harder toward the prediction) and SHRINK when one candidate is an excellent match. Here the prediction always receives a fixed fraction (0.5) of the best candidate's weight regardless of how good or bad the fit is. The prediction-bias term therefore cannot adapt to candidate quality — it is a constant regularizer, reinforcing finding [1] that this is not JPDA. The analyst noted the missing β₀ term but did not catch that the implemented pseudo-weight degenerates to a constant.  
  *(ev: track.py:818 `b_pred = self._cfg.jpda_prediction_weight * max(betas)`. Because c_min is subtracted at track.py:814 before exp(), max(betas) is ALWAYS exactly 1.0 (the best candidate maps to exp(0)=1). Verified across cost sets [0,0], [0.2,0.6], [5.0,5.1]: max(beta)=1.0 in every case, so b_pred=0.5 always.)*
- **[low] On the hit path, predicted_centroid_px is overwritten with the JPDA-softened MEASURED centroid, contradicting its own docstring** — Downstream consumers reading predicted_centroid_px get the JPDA-blended measurement on associated frames but the true CV/IMM prediction on coast frames — an inconsistent, self-contradicting output field. A display or analytics layer comparing measurement-vs-prediction would see zero residual on every hit frame because both fields are identical. Doc-vs-code mismatch the analyst did not flag.  
  *(ev: track.py:580 and 584 both set `centroid_px=report_centroid` AND `predicted_centroid_px=report_centroid`, where report_centroid = `_jpda_centroid(blob)` (the softened observation). The field docstring (track.py:250-251) says predicted_centroid_px is 'CV-predictor centroid regardless of state'. On the MISS path (track.py:657) it is correctly the prediction.)*
- **[low] Area veto/appearance term operate on top-hat-SUPPRESSED area_px, not the looming-robust area_extended_px** — On LOCKED non-coast frames (where the veto IS active per finding [3]), a genuinely looming endgame target whose area_px is being suppressed could see an erratic area_ratio and even trip the low-side veto (area_ratio < 1/2.5), penalizing the real target precisely at closing. The field engineered to track true growth (area_extended_px) is excluded from the association firewall. A consistency gap between the appearance veto's metric and the project's own looming/size metric.  
  *(ev: track.py:846,848,854 read `blob.area_px`. Per blob.py:118-121, area_px is suppressed by the top-hat for large/extended targets, whereas area_extended_px 'GROWS with the true target size'. _association_cost never references area_extended_px (confirmed by source scan); area_extended_px is used only by the regime classifier (track.py:572) and looming.)*


---

## P1-radiometry-detection  ·  строгость 5.5/10
*Physicist — IR radiometry & detection*

**Вердикт:** The Johnson DETECT/ID geometric envelope in the doc is arithmetically correct and self-consistent with the code's intrinsics (FT640 f_px=707, IFOV~1.41 mrad/px, within ~6% of the doc's quoted 1.33 mrad), and the AGC quantization argument (~78 mK/DN vs 50 mK NETD) is numerically sound. The local-contrast primitives (MPCM directional-min, Deshpande max-median, region-graduated CFAR k-ordering) are individually well-constructed and behave as advertised on synthetic point-vs-edge/line tests. However, the detection chain is physically incomplete in two load-bearing ways the doc explicitly calls mandatory: (1) the detector is bright-blob-only (white top-hat, no black top-hat / no |contrast|) and empirically MISSES contrast-inverted (cold-on-warm) targets, directly violating the doc's stated "detector must be polarity-agnostic" requirement; (2) thermal_sim.py is a fixed-amplitude Gaussian-blob generator with no NETD, no dT/emissivity, no fill-factor, no atmospheric transmission, no range coupling, and no 8-bit AGC channel, so it cannot exercise the SNR ~ dT_apparent*fill/NETD_eff regime the doc centers its detection physics on. Default scene SNR is ~145 (trivially easy), not the contrast-limited tens-of-meters reality. The region-CFAR / MPCM / directional-median / MTI look-down stages, the doc's doctrinal answer to heavy-tailed clutter, are all default-OFF opt-in flags, and the S3 closed-loop (pixel_loop.py) does not expose them at all and hardcodes ffc_state="READY". The radiometric reasoning in the doc is genuinely rigorous; the executable detection model is a benign-sky toy that does not test the binding constraints the same doc identifies.

**Сильные стороны:**
- Johnson DETECT/ID envelope is arithmetically correct and brackets the stated ~115-190 m detect / ~18-30 m ID from R=d/(2*N50*IFOV) at IFOV=1.33 mrad, N50=1/8, d=0.3-0.5 m.  
  *(ev: docs/SEEKER_SCIENCE_DEEP_DIVE.md:182-197; re-derivation: detect 112.8 m (d=0.30) / 188.0 m (d=0.50); ID 14.1 m / 23.5 m)*
- The code's camera intrinsics are self-consistent with the doc IFOV. ft640_intrinsics computes f_px = (640/2)/tan(48.7deg/2) = 707.08 px, i.e. IFOV = 1/f_px = 1.414 mrad/px, within ~6% of the doc's 1.33 mrad class.  
  *(ev: fpv/seeker/geometry.py:122-152 (ft640_intrinsics, f_px~707, comment states 1.41 mrad/px); verified f_px=707.08)*
- The AGC quantization argument is numerically correct: an 8-bit AGC auto-spanning a ~20 K scene yields 20K/256 = 78.1 mK/DN, ~1.56x coarser than a 50 mK bolometer NETD, so AGC (not NETD) is the sensitivity floor.  
  *(ev: docs/SEEKER_SCIENCE_DEEP_DIVE.md:128,204; re-derivation 78.1 mK/DN matches)*
- The relative/percentile+MAD thresholding with iterative sigma-clip and FFC re-base is the correct response to the missing radiometry (no fixed DN threshold is physically meaningful behind per-frame AGC).  
  *(ev: fpv/seeker/detect.py:616-674 (_compute_threshold, 1.4826 MAD scaling, sigma-clip), 153-161 + 358-361 (FFC needs_rebase), 348-350 (FREEZE guard returns empty))*
- MPCM (multiscale directional-min patch contrast) and the Deshpande directional max-median are mathematically correct local-contrast / line-rejection operators on the residual.  
  *(ev: fpv/seeker/detect.py:766-797 (_mpcm), 800-828 (_directional_max_median); tests: point-target kept (residual 100.0), horizontal line suppressed to 0.0, edge interior/boundary MPCM ~0)*
- Region-graduated CFAR k-multipliers correctly enforce the k_horizon<k_sky<k_ground doctrine and OR with the global threshold as a fail-safe so region-CFAR can never be LESS sensitive than global.  
  *(ev: fpv/seeker/detect.py:89-91 (0.7/1.0/1.6), 399-408 (thr_map OR global), verified floors 1.75/2.5/4.0)*

**Находки:**

| Сев. | Категория | Вердикт | Находка | Свидетельство |
|---|---|---|---|---|
| high | doc-code-mismatch | flawed | Detector is NOT polarity-agnostic; empirically misses contrast-inverted (cold-on-warm) targets the doc says it must catch | `fpv/seeker/detect.py:577-613 (_white_tophat, np.clip(result,0,None)), 411 (tophat>threshold); docs/SEEKER_SCIENCE_DEEP_DIVE.md:160,205; empirical: bright target found, inverted target MISSED` |
| high | unsound-assumption | unsound | thermal_sim.py has no radiometric physics: no NETD, no dT/emissivity, no fill-factor, no atmosphere, no range coupling, no AGC channel | `fpv/seeker/thermal_sim.py:108-110 (fixed target_peak_above_bg=1800), 408-446 (_render_frame: base+noise+gaussian, no range/NETD/AGC), 468-471 (_float64_to_u16 clips to 14-bit, no AGC); measured default SNR=144.5; AGC search in seeker tree finds AGC only in mti/aimpoint/correlation, never in the scene generator` |
| medium | unsound-assumption | flawed | Drone signature is a single circular Gaussian: no mixed-emissivity structure, no motor/ESC/battery multi-spot, no plume-absence test, no solar-loading sign flip | `fpv/seeker/thermal_sim.py:432-444 (single _gaussian2d target + Gaussian stars), 392-396 (_target_area single-sigma); docs/SEEKER_SCIENCE_DEEP_DIVE.md:142-150 (component-by-component signature)` |
| medium | correctness-error | flawed | MPCM gate can suppress the peak pixel of a true 1-px point target (most range-limited target) | `fpv/seeker/detect.py:418-420 (binary_mask & (mpcm > _MPCM_RATIO*tophat)), 103 (_MPCM_RATIO=0.3); empirical 1-px: mpcm 11.11 < 30` |
| medium | dead-code | mixed | Look-down clutter doctrine (region-CFAR / MPCM / directional-median / MTI / graduated-k) is default-OFF and absent from the S3 closed loop | `fpv/guidance/pipeline.py:80-98 (all flags default 0/False), fpv/guidance/pixel_loop.py:529-536 (detect_frame with no advanced flags, ffc_state hardcoded READY)` |
| low | unsound-assumption | flawed | No against-cloud / near-zero-dT failure mode is representable; sky background is always cold and friendly | `fpv/seeker/thermal_sim.py:373-382 (single cold-sky gradient), 105-106 (fixed sky_base_counts)` |
| low | mis-calibration | mixed | Doc IFOV (1.33 mrad) is ~6% finer than the code's modeled lens (1.41 mrad); range numbers are quoted at the optimistic value | `docs/SEEKER_SCIENCE_DEEP_DIVE.md:169-170 (1.33 mrad via FOV/N), fpv/seeker/geometry.py:135 (1.41 mrad via 1/f_px); re-derivation detect 106.1/176.8 m at 1.41 mrad` |

- **[HIGH] Detector is NOT polarity-agnostic; empirically misses contrast-inverted (cold-on-warm) targets the doc says it must catch** — The doc states (twice) that the detector MUST be polarity-agnostic to survive contrast inversion (drone cooler than sun-heated ground in daylight look-down, appearing as a NEGATIVE blob). The code uses a WHITE top-hat only (f - opening(f)), clips negatives to zero, and thresholds tophat>thr. There is no black top-hat, no |residual|, no dark-on-light path anywhere in detect.py. Empirical test: a synthetic cold Gaussian dip (-1800 counts) on a warm 8000-count background yields ZERO blobs, while the equivalent bright target yields 1 blob at the correct centroid. The seeker would drop track at the exact horizon-crossing / against-hot-ground geometries the doc flags as the SNR-collapse regime.
  - *Рекомендация:* Add a black-top-hat / dual-polarity branch (detect on max(white_tophat, black_tophat) or |bandpass residual|) and tag blob polarity, OR explicitly scope the seeker to look-up/sky-background-only engagements in the doc and remove the polarity-agnostic claims. Do not leave the doctrine asserting a capability the code does not have.
- **[HIGH] thermal_sim.py has no radiometric physics: no NETD, no dT/emissivity, no fill-factor, no atmosphere, no range coupling, no AGC channel** — The doc grounds detection on SNR ~ dT_apparent*fill/NETD_eff and on the 8-bit AGC being the binding floor. The simulator implements none of this. The target is a fixed 1800-count Gaussian (target_peak_above_bg, constant for the whole run) summed onto a 4096-count sky with 12-count read noise; there is no range argument, so the target does not dim with distance, no fill-factor dilution as the blob shrinks toward 1 px, no NETD/dT mapping, no atmospheric transmission, and crucially the frame is emitted as a 14-bit linear uint16 with NO 8-bit AGC compression/contrast-stretch/pumping anywhere. Default scene SNR measured ~145 - a trivially easy target, the opposite of the contrast-limited reality. Consequently every green detection test exercises a benign-sky easy-target regime and says nothing about the doc's actual physics walls.
  - *Рекомендация:* Add (a) a range-driven fill-factor / sigma & amplitude model so apparent contrast falls toward NETD at long range, (b) an explicit NETD-referenced noise and a few-K dT-class signature, and (c) an 8-bit AGC stage (per-frame min/max span -> 256 levels + pumping) BEFORE detection. Without this, detection P_d numbers from the sim are not transferable to the field and the doc's contrast-limited envelope is untested.

**Переderived числа (✓ совпало / ✗ расхождение):**

- ✓ **FT640 focal length f_px from HFOV=48.7deg, W=640**  
  - заявлено: ~707 px (geometry.py); IFOV ~1.41 mrad/px
  - вывод: (640/2)/tan(radians(48.7)/2) = 707.08 px; 1/707.08 = 1.414 mrad/px
  - прим.: Code intrinsic is exactly reproduced; matches the geometry.py docstring.
- ✓ **Johnson DETECT range at IFOV=1.33 mrad, N50=1, d=0.30-0.50 m**  
  - заявлено: ~113-188 m (doc), stated envelope ~115-190 m
  - вывод: 0.30/(2*1*1.33e-3)=112.8 m; 0.50/(...)=188.0 m
  - прим.: Exact. At the code's actual 1.41 mrad it is 106-177 m, ~6% shorter.
- ✓ **Johnson ID range at IFOV=1.33 mrad, N50=8, d=0.30-0.50 m**  
  - заявлено: ~14-23.5 m (doc), stated envelope ~18-30 m
  - вывод: 0.30/(2*8*1.33e-3)=14.1 m; 0.50/(...)=23.5 m
  - прим.: Doc's own derivation (14-23.5) is slightly tighter than its quoted 18-30 envelope; both are order-consistent. The 8x detect->ID penalty is correct.
- ✓ **AGC quantization step (8-bit over ~20 K scene span) vs NETD**  
  - заявлено: ~78 mK/DN, swamps 50 mK bolometer (doc 1.2, 1.6)
  - вывод: 20000 mK/256 = 78.1 mK/DN; ratio to 50 mK NETD = 1.56
  - прим.: Numerically exact; the AGC-is-the-floor thesis is sound.
- ✓ **Stefan-Boltzmann contrast slope dM/dT at 290 K, eps=1**  
  - заявлено: ~5.5 W/m2/K (doc 1.1)
  - вывод: 4*5.67e-8*290^3 = 5.53 W/m2/K
  - прим.: Correct.
- ✓ **Diffraction Airy first null at lambda=10um, f/1 FT640 (EFL ~8.5 mm)**  
  - заявлено: ~1.36 mrad ~ 1 IFOV (doc 2.5, 9mm aperture)
  - вывод: 1.22*10e-6/8.48e-3 = 1.438 mrad (EFL=f_px*12um pitch=8.48mm); at 9mm =1.356 mrad
  - прим.: LWIR is genuinely diffraction-soft at ~1 IFOV; consistent. Note the implied 12um pitch gives EFL 8.48mm, not the doc's 9-10mm, but Airy ~= 1 IFOV holds either way.
- ✗ **Default sim scene SNR (target_peak=1800, read_noise=12)**  
  - заявлено: models a drone at 100-200 m (thermal_sim docstring target_sigma comment)
  - вывод: detector-reported SNR = 144.5; peak/read_noise = 150
  - прим.: An SNR~145 target is a trivially easy detection, NOT the contrast-limited tens-of-meters reality the doc describes; the sim does not model NETD/fill/atmosphere/AGC, so the '100-200 m' framing is not physically backed.
- ✗ **MPCM response at the peak of a 1-px point target vs the 0.3*tophat gate**  
  - заявлено: MPCM gate passes compact targets (detect.py:97-103)
  - вывод: scale-1 MPCM@peak = 100/9 = 11.11; gate threshold = 0.3*100 = 30 -> peak pixel FAILS
  - прим.: The gate rejects the peak pixel of a true single-pixel target; only survives because the PSF spreads to neighbors. Marginal sub-pixel long-range targets are eroded.

**Верификация (уверенность):** high — every finding and all 8 quantitative checks were re-opened at the cited file:line and independently reproduced (f_px=707.08->1.414 mrad; DETECT 112.8-188.0 @1.33 vs 106.1-176.8 @1.414; ID 14.1-23.5 vs 13.3-22.1; AGC 78.1 mK/DN, ratio 1.56; dM/dT 5.53 W/m2/K; Airy 1.439 mrad@8.48mm EFL; default sim SNR 149.5~=150). Decisive findings ([0] polarity, [3] MPCM 1-px erosion, [6] default SNR) were confirmed by running the actual code, not just reading it. No hallucinations found; the analyst's quant flags on [6] (agree=false) and [7] (agree=false) are correct. Added 4 missed issues (untested polarity, config-dependent SNR, non-physical noise model, trivially-separable static stars).

*Пропущено аналитиком, добавил верификатор:*
- **[medium] No test anywhere in the seeker suite exercises contrast inversion / polarity-agnostic detection** — Finding [0] is not merely an implementation gap but an untested requirement: the polarity-agnostic mandate has no covering test, so the white-tophat-only behavior would never be caught by the green suite. This makes the doc-vs-code mismatch durable -- a future 'fix' would have nothing to regress against. Strengthens finding [0].  
  *(ev: grep for polarity|inverted|cold.*target|black.*tophat across fpv/seeker/tests/ returns ZERO matches. The test dir has 30+ files (test_detect.py, test_mpcm.py, test_region_cfar.py, test_directional_median.py, etc.) but none constructs a cold-on-warm (negative-contrast) target. The doc mandates polarity-agnostic detection twice (SEEKER_SCIENCE_DEEP_DIVE.md:160,205).)*
- **[low] Background-stats leakage in SNR: bg_mean/bg_std exclude only threshold-passing pixels, so SNR is computed against an MPCM/region-modified mask, coupling SNR to the gate config** — The reported per-blob SNR is not a fixed physical quantity: enabling use_mpcm/region_bands changes which pixels count as background, shifting bg_std and hence every blob's SNR and the salience sort order. Plain np.std (not MAD) also means a few surviving bright clutter pixels inflate bg_std and depress SNR. Minor for the benign sim but means SNR is not comparable across pipeline configurations.  
  *(ev: detect.py:427-435 sets bg_mask = ~binary_mask AFTER the MPCM gate (420) and region-CFAR (407) have already pruned binary_mask. bg_mean/bg_std are np.mean/np.std (NOT robust) over tophat[~binary_mask]. SNR (466) = (peak_tophat - bg_mean)/bg_std then divides by this config-dependent std.)*
- **[low] Read-noise model is signal-independent Gaussian only; no shot/photon noise, no FPN/NUC residual, no 1/f -- so even the noise floor is non-physical for a bolometer** — Adds to finding [1]: not only is the AGC/NETD chain absent, but the modeled sensor noise is a single homoscedastic Gaussian. The FFC re-base machinery and threshold sigma-clipping are therefore tested against a noise model that contains none of the structured artefacts (FPN, NUC residual, AGC pumping) they were built to survive.  
  *(ev: thermal_sim.py:425 noise = rng.normal(0, read_noise_sigma=12) added once, constant across the whole frame regardless of scene level. No Poisson/shot term, no fixed-pattern (column/row) noise, no post-FFC NUC residual structure (the very thing the FFC re-base logic at detect.py:17-23/352-361 exists to handle).)*
- **[low] Stars are STATIC across the run while only the target moves -- the 'hard negative' is trivially separable by motion, overstating discrimination** — The 'hard negatives' differ from the target in brightness, width, AND motion -- any one of which trivially separates them. The doc's discrimination challenge (AUC 0.6-0.75 single-frame, doc:16) assumes clutter that is structurally target-like; this generator's stars are not, so any green discrimination/MTI/track test on this sim overstates real separability. Reinforces findings [2] and [5].  
  *(ev: thermal_sim.py:384-390 _place_stars fixes positions once; in _render_frame (439-444) stars only receive rigid ego-drift (dx_ego,dy_ego), identical for all of them, while the target follows its own trajectory_fn. star_peak_fraction=0.55 and star_sigma=0.8*target make them dimmer AND narrower.)*


---

## P2-kinematics-envelope  ·  строгость 5.5/10
*Physicist — flight dynamics & intercept kinematics*

**Вердикт:** The core body-envelope wall is correct and faithfully enforced: a_lat = g*tan(theta) gives exactly 0.839 g at theta_max=40deg, command_map clamps via atan2(a,g)/theta_max, and the guidance hard-cap equals a_max=g*tan(theta_max) with abort_g_margin=1.0, so the abort boundary and actuator clamp agree. This is the most rigorous part of the subsystem. The 0.28 g maneuver ceiling (achievable_g/3) is arithmetically exact and correctly logged as the high-crossing abort rationale; the crossing threshold (0.15 rad/s -> ~0.92 g at design Vc) sits just above the wall, internally consistent. But two load-bearing claims are flawed in CODE. (1) The plant does NOT hold the 15 m/s design point: fixed forward-lean pitch (0.4*theta_max) against linear drag drives forward speed to ~25 m/s by mid-engagement and ~41 m/s at steady state, while the vertical channel sinks several meters; because Vc is scheduled from this inflated own-speed, the PN gain N*Vc is 1.5-2x larger than the documented 20 m/s, and the SpeedPolicy g-reserve output is computed but NEVER fed to the plant (dead path). (2) The capture-cone formula theta_capture~=sqrt(2*a_max*R/Vc^2) is numerically nonsensical at engagement ranges (82-164deg at R=50-200 m), so the doc's 15-18deg cone is asserted, not derived by its own formula. The ten-tau wall is documented but NOT wired into the default loop (terminal/LOS-hold default to fixed 15 m / 5 m range thresholds; tau path is default-OFF). The strapdown ego-rate problem the science doc calls "the whole ballgame" is structurally absent because the plant uses a velocity-aligned boresight, so the dominant real-world LOS-rate corruption is defined away in sim.

**Сильные стороны:**
- The 0.84 g lateral wall is correctly derived and consistently enforced: a_lat = g*tan(theta), tan(40deg)=0.8391 -> 8.232 m/s^2, and the guidance hard-cap is set to exactly a_max=g*tan(theta_max) with abort_g_margin=1.0 so the clamp and abort boundary coincide (no silent saturation margin).  
  *(ev: quad_sim.py:353 (a_lateral_x = _G*math.tan(clamp(roll))); bearing_rate.py:269-289 (a_max_mps2/effective_max_a_cmd), :246 (abort_g_margin=1.0), :529-546 (envelope check + abort))*
- The command-map lateral limiter is the correct inverse of the plant tilt law: theta_cmd = atan2(a_cmd, g), normalized = theta/theta_max, clamped to [-1,1]. Feeding this into the plant's a = g*tan(roll) recovers the commanded lateral accel up to the clamp, so guidance and plant are dimensionally and numerically consistent.  
  *(ev: command_map.py:290-298 (_accel_to_normalized_angle); quad_sim.py:329,353 (roll_target = roll_cmd*theta_max; a = g*tan(roll)))*
- The 0.28 g target-maneuver ceiling is exactly achievable_g/3 and is computed/logged from the envelope, not hard-coded: tan(40deg)/3 = 0.2797 g, matching the doc's 0.84/3.  
  *(ev: bearing_rate.py:566 (target_ceiling_g = achievable_g/3.0), :447-448 (abort reason logs ceiling); a_max/3 derivation reproduced numerically (0.2797 g))*
- The continuous closest-approach (segment minimum) miss metric is mathematically correct: it analytically minimizes |d0 + t*dd|^2 over t in [0,1], eliminating the discrete-step quantization artifact.  
  *(ev: closed_loop.py:145-186 (_segment_closest_approach, t* = -dot(d0,dd)/|dd|^2 clamped to [0,1]))*

**Находки:**

| Сев. | Категория | Вердикт | Находка | Свидетельство |
|---|---|---|---|---|
| high | unsound-assumption | unsound | Plant does not hold the 15 m/s design point; forward speed runs away and inflates the PN gain | `quad_sim.py:372 (a_y = g*tan(pitch) - drag*vy, no speed reference); command_map.py:249 (pitch_cmd = forward_pitch_fraction, constant); closed_loop.py:724-729 (Vc from own_speed=/q_state.vel/); empirical: vy=15.7@0.5s,18.7@2s,23.9@5s,31@10s,41@ss` |
| high | dead-code | flawed | SpeedPolicy g-budget reserve is computed but never actuated (dead control path) | `command_map.py:257-263,274 (resolve_speed -> AICommand.resolved_speed_mps only); speed.py:99-126 (_g_budget_scale); closed_loop.py: no read of resolved_speed (grep empty); plant forward speed set by pitch lean only (quad_sim.py:372)` |
| medium | unverifiable-claim | unverifiable | Capture-cone formula is numerically invalid at engagement ranges; the 15-18deg cone is asserted, not derived | `docs/SEEKER_SCIENCE_DEEP_DIVE.md:14,843-849; doc:15 '15-18deg'; recomputation: 82/116/164deg at R=50/100/200, Vc=20, a_max=8.23; no theta_capture symbol in bearing_rate.py/command_map.py` |
| medium | doc-code-mismatch | flawed | Ten-tau commit wall is documented as active but the default closed loop uses fixed range thresholds, not tau | `command_map.py:99-107 (range thresholds; use_tau_terminal=False default), :301-337 (_is_terminal_phase/_is_los_hold_phase legacy range path), :107 (los_rate_hold_tau_s=0.15); closed_loop.py:386 (LosGuidancePilot(config=cfg.pilot) with default PilotConfig); pipeline.py:180-182 (only place use_tau_terminal flows in)` |
| medium | unsound-assumption | unsound | Velocity-aligned boresight defines away the dominant strapdown ego-rate error | `quad_sim.py:499-505,574-579 (boresight=velocity); pixel_loop.py:50-59 (zero pitch/yaw ego for velocity-aligned boresight); docs/SEEKER_SCIENCE_DEEP_DIVE.md:920 (unity-gain body-rate coupling is 'the whole ballgame'); closed_loop.py:236,609 (los_rate_bias_sigma default 0)` |
| low | correctness-error | mixed | Vertical (elevation) channel drifts: documented altitude-hold is not achieved in maneuvering flight | `command_map.py:213-221 (cos(roll)*cos(pitch)); quad_sim.py:362-373 (a_z_thrust*cos(theta_total)-g, theta_total=sqrt(roll^2+pitch^2)); empirical vz=-1.84@5s,-3.74@10s, z=-18.4@10s` |
| low | doc-code-mismatch | flawed | abort_g_margin docstring (0.90) contradicts the code default (1.0) | `bearing_rate.py:212-214 (docstring 'Default 0.90'), :246 (code default 1.0 with corrective comment), :529 (envelope_ok uses abort_g_margin)` |
| low | design-strength | correct | Smith-predictor lead is applied to bearing but the rate fed forward is the stale delayed rate | `closed_loop.py:655-666 (az_guided = az_d + az_rate_d*total_delay_s; az_rate_guided = az_rate_d), :637-654 (rationale comment)` |

- **[HIGH] Plant does not hold the 15 m/s design point; forward speed runs away and inflates the PN gain** — The pilot applies a CONSTANT forward-lean pitch (forward_pitch_fraction=0.4 -> 16deg) and the plant's only longitudinal opposition is linear drag (drag_coeff=0.05/s). Force balance gives v_ss = g*tan(16deg)/0.05 = 56 m/s; empirically the integrator reaches ~41 m/s steady state and, over a realistic 200 m head-on engagement, climbs from 15 m/s to ~24 m/s by t=5 s and ~31 m/s by t=10 s. Vc is then scheduled from this actual own-speed (schedule_Vc_mps(|v|+5)), so the PN gain N*Vc grows from the documented 3*20=60 to 3*46=138 at steady state. Every doc/comment that reasons about 'interceptor at 15 m/s', 'Vc~=20 m/s', and the delay-miss scaling miss~N*Vc*Td^2*a_T/2 is using a Vc the plant does not actually fly. The law direction is fine, but the magnitude scaling and the whole delay/miss budget are computed at an operating point the closed loop never holds.
  - *Рекомендация:* Close the longitudinal loop: either drive pitch_cmd from a forward-speed error toward a commanded airspeed (the SpeedPolicy resolved_speed), or cap/regulate vy. At minimum, document that Vc and the 0.84 g/delay budgets are evaluated at a non-constant, self-inflating speed and re-derive the delay-miss numbers at the true mid-engagement Vc (~25-30 m/s).
- **[HIGH] SpeedPolicy g-budget reserve is computed but never actuated (dead control path)** — The A3 'speed loop coupled to the g-budget' is the documented mechanism for buying maneuver headroom by slowing closure (the science doc: 'slowing down buys maneuver headroom', theta_capture rises as Vc falls). The pilot calls SpeedPolicy.resolve_speed_mps with required_g/achievable_g and the _g_budget_scale multiplier correctly returns g_cap/required_g (<1) to hold a 20% reserve. But the resulting resolved_speed_mps is only stored in the AICommand telemetry field; the closed-loop plant integrates pitch/throttle/roll directly and NEVER reads resolved_speed. Grep confirms resolved_speed is consumed nowhere in closed_loop.py or quad_sim.py. So the headroom-by-slowing doctrine is implemented in arithmetic but has zero effect on the simulated trajectory or Vc.
  - *Рекомендация:* Wire resolved_speed back into the forward-speed regulator (commanded airspeed) and into Vc scheduling, then re-run the Monte-Carlo to see whether the g-reserve actually changes hit/abort statistics. Until then, label the g-budget coupling as telemetry-only, not an active control law.

**Переderived числа (✓ совпало / ✗ расхождение):**

- ✓ **a_lateral at theta_max=40deg (the 0.84 g wall)**  
  - заявлено: a_lateral_max ~= 8.22 m/s^2 (0.84 g), via a_lat = g*tan(theta), tan(40deg)=0.839
  - вывод: 9.81*tan(40deg) = 9.81*0.83910 = 8.232 m/s^2 = 0.8391 g
  - прим.: Exact. quad_sim.py docstring says 8.22 (rounds tan to 0.838); code uses math.tan so it is 8.232. The 0.84 g figure is correct.
- ✓ **Maneuver ceiling a_T = achievable_g/3 (3:1 overmatch)**  
  - заявлено: a_T <~ 0.28 g, = 0.84/3
  - вывод: tan(40deg)/3 = 0.8391/3 = 0.2797 g; 0.839/3 = 0.2797
  - прим.: Exact and computed in code (bearing_rate.py:566). Genuinely derived from theta_max, not asserted.
- ✗ **Capture cone half-angle theta_capture = sqrt(2*a_max*R/Vc^2)**  
  - заявлено: 15-18deg forward half-angle (a_max=0.84 g)
  - вывод: At Vc=20, a_max=8.23: R=50->82.2deg, R=100->116.2deg, R=200->164.4deg. To get 15-18deg requires R~0.9-3.7 m.
  - прим.: Formula yields non-physical >pi/2 angles at engagement ranges. The 15-18deg cone is FOV-limited, not produced by this kinematic formula at any realistic R. Doc claim is not reproducible from its own equation.
- ✓ **max nullable LOS rate vs crossing threshold**  
  - заявлено: crossing_rate_threshold=0.15 rad/s classifies HIGH_CROSSING; just above the g-wall
  - вывод: Max nullable lambda_dot = a_max/(N*Vc) = 8.23/(3*20) = 0.1372 rad/s = 7.9 deg/s. Threshold 0.15 rad/s -> required_g = 0.15*20*3/9.81 = 0.917 g = 1.09x achievable.
  - прим.: Consistent at the DESIGN Vc=20. But with the inflated in-flight Vc~46, the same 0.15 rad/s implies 2.11 g, so the abort fires far earlier than the doc's reasoning assumes -- the threshold's g-meaning drifts with the runaway speed (see speed finding).
- ✗ **Steady-state / mid-engagement forward speed vs 15 m/s design**  
  - заявлено: interceptor at ~15 m/s, Vc~=20 m/s (docs, GuidanceConfig.Vc_sched_mps=20)
  - вывод: Force balance v_ss = g*tan(0.4*40deg)/drag = 2.81/0.05 = 56 m/s (analytic); numerical integrator: vy=15.7@0.5s, 18.7@2s, 23.9@5s, 31@10s, ~41 steady. Vc=|v|+5 tracks this.
  - прим.: Plant does not hold 15 m/s. By mid-engagement Vc is ~28-36, making N*Vc 1.4-1.8x the documented value. The 15 m/s/Vc=20 operating point used in all envelope/delay reasoning is not flown.
- ✗ **Vertical channel altitude hold (a_z at level)**  
  - заявлено: throttle = hover/(cos roll cos pitch) holds altitude
  - вывод: throttle = 0.5/cos(16deg) = 0.5201; a_z = 2*0.5201*9.81*cos(16deg) - 9.81 = 0.000 m/s^2 (level). But integrated flight sinks: vz=-1.84@5s, z=-18.4@10s.
  - прим.: Algebra is exact at level, but cos-model mismatch (cos r*cos p vs cos(sqrt(r^2+p^2))), attitude lag, and lack of altitude integral produce a real uncorrected sink in maneuvering flight.
- ✗ **Ten-tau wall time scale vs implemented terminal switches**  
  - заявлено: ~1.0-1.4 s commit cutoff (10-15 * tau_loop, tau_loop~0.1 s)
  - вывод: Default terminal switch is range-based: acro at 15 m, LOS-hold at 5 m. At Vc~25 m/s that is t_go~0.6 s / 0.2 s. The tau thresholds (0.4 s / 0.15 s) are also < 1.0 s. None match 1.0-1.4 s, and the tau path is default-OFF.
  - прим.: The physically-motivated 1.0-1.4 s wall is neither the default trigger nor matched by the tau thresholds; the validated loop commits on a fixed range timer ~3-7x shorter than the documented wall.

**Верификация (уверенность):** high — all 8 findings re-checked against source at the cited lines and 6 verified by re-running the actual plant/closed loop; all 7 quantitative checks re-derived independently and confirmed. Key correction: finding [5]'s headline sink numbers are a bare-plant artifact (refuted in the real closed loop), and finding [4]'s 'off by default' framing understates the honest-test coverage. Two structural issues the analyst missed (decoupled yaw channel; independent roll/pitch tilt clamps over-stating the lateral g-budget) are physics-grade and material to the ROE/intercept-kinematics claims.

*Опровергнуто/преувеличено аналитиком (поймал верификатор):*
- Finding [5]: the empirical vertical-sink figures 'vz=-1.8 m/s at t=5s, -3.7 m/s at t=10s, z=-18 m' are NOT produced by the closed loop. They are bare-plant numbers with a flat throttle=0.5 (no gravity feed-forward). The real closed loop holds z within ~0.1m and vz~0 even under a 30m-lateral-offset maneuvering engagement (verified by running ClosedLoop). The cos-model mismatch the analyst blames produces only a -0.017 m/s^2 residual at 20deg roll — physically incapable of an 18m sink.
- Finding [0] / QC4: the claimed '~41 m/s steady state' for the plant is wrong. The analytic force-balance steady state is 56.26 m/s (g*tan(16deg)/0.05), and the open-loop integrator actually reaches 56.2 m/s. The '41 m/s' is just the t~=10s value, mislabeled as steady state. (The core finding stands; only this number is off.)
- Finding [4]: the claim that the AR-1 los_rate_bias knob is 'the only proxy left, and it is off by default' overstates the gap — test_s3_honest_acceptance.py wires los_rate_bias_sigma_radps=1.0e-3 rad/s ON in the honest grading path. It is off only in the baseline/default config.
- Finding [2] / QC2: minor — the analyst's 'R<0.9-3.7 m' / '<4 m' window for recovering 15-18deg is loose; the exact band is R=1.67-2.40 m. Does not change the conclusion.

*Пропущено аналитиком, добавил верификатор:*
- **[high] Yaw channel is completely decoupled from translation AND from the bearing — pure dead actuation** — The pilot computes yaw_rate_cmd = yaw_gain*az_rad (command_map.py:252) as a 'point boresight toward target' command, and the docstring (command_map.py:251) claims it points the boresight. But in the sim the yaw attitude angle has zero effect on either the plant trajectory or the seeker bearing — the boresight is hard-wired to velocity. The yaw control loop is entirely cosmetic in every Monte-Carlo run. This is a structural modeling gap the Physicist analyst did not flag: a real strapdown seeker's boresight is the airframe nose (attitude), not the velocity vector, so the entire yaw-pointing channel is untested by this sim.  
  *(ev: quad_sim.py:331,343 integrate yaw_rate into attitude_rad[2], but the acceleration block (:370-373 a_x,a_y,a_z) never reads yaw. compute_bearing_from_states (:499-505) and compute_los_rates (:574-579) use the VELOCITY direction as boresight, not attitude/yaw. I verified: after 1s of full yaw_rate_cmd=1.0 the yaw attitude reaches 1.571 rad while vx stays EXACTLY 0.0 and the trajectory is unchanged.)*
- **[medium] Lateral command saturates the SAME g-budget as forward closure: roll produces a_x but pitch lean already consumes ~16deg of the 40deg tilt budget** — The honest-physics claim a_max=g*tan(40deg)=0.84g assumes the FULL tilt budget is available for lateral acceleration. But the constant 16deg forward lean already consumes part of the attitude envelope; a real quad has a SINGLE thrust vector whose total tilt is bounded, so lateral and forward tilt trade against each other. Here they are independent (separate clamps), so the plant can produce 0.84g lateral while ALSO leaning 16deg forward — a combined tilt of ~25.6deg whose true lateral component is over-stated. The 0.84g lateral envelope used in every ROE/abort calc is therefore optimistic relative to a single-thrust-vector airframe.  
  *(ev: quad_sim.py:353-354 clamp roll_actual and pitch_actual INDEPENDENTLY to +/-theta_max (40deg) each. The lateral accel a_x=g*tan(roll) and forward a_y=g*tan(pitch) are computed from separately-clamped angles, so the model permits 40deg roll SIMULTANEOUS with 16deg pitch — a combined tilt of sqrt(20^2+16^2)... actually the total tilt vector can exceed 40deg.)*
- **[low] _DelayBuffer.peek_delayed uses raw self._delay_s, ignoring jitter — latent inconsistency (currently unused)** — Dead-but-inconsistent code: if peek_delayed is ever wired in for A5 latency-jitter sweeps it will not apply the jitter, silently diverging from pop_delayed. Low severity because it is currently unused, but it is a trap for future maintainers.  
  *(ev: closed_loop.py:322-330 peek_delayed compares against self._delay_s, while pop_delayed (:313-320) uses _effective_delay() (jittered). peek_delayed is defined but never called in closed_loop.py.)*
- **[low] Continuous-CPA termination can prematurely cut the run for a target offset larger than 3x capture_radius that never re-closes** — Not a bug per se, but the early-termination logic only arms inside 2.25m. A grazing pass at, say, 3m closest approach will not trigger early termination and the miss is captured by the segment-minimum (correct), but the engagement_time_s reported equals max_sim_time (30s) rather than time-of-CPA — a reporting artifact that could mislead timing analyses. Worth noting since the Physicist persona reasons about engagement timelines.  
  *(ev: closed_loop.py:505 sets past_closest_approach only when range < capture_radius*3.0 (=2.25m); :508-517 then terminates after 5 increasing steps. For a genuine wild-miss (range never drops below 2.25m) this branch never arms, so the loop instead runs to max_sim_time_s.)*

*Вердикты «опровергнуто/частично»:*
- [partially-confirmed] [4] Velocity-aligned boresight defines away the dominant strapdown ego-rate error — The PHYSICS claim is confirmed: the velocity-aligned boresight removes the unity-gain body-rate coupling, so Mode A/B do not test the dominant real-world LOS-rate corruption. BUT the analyst's claim that the AR-1 los_rate_bias 'is the only proxy left, and it is off by default' is only half-true: the HONEST acceptance test (test_s3_honest_acceptance.py:46,144) DOES wire los_rate_bias_sigma_radps=1.0e-3 rad/s as exactly this strapdown proxy. So it is off in the BASELINE config but ON in the honest grading path. Downgraded to partially-confirmed because the 'only proxy, off by default' framing understates the honest test's coverage.
- [refuted] [5] Vertical channel drifts; documented altitude-hold not achieved in maneuvering flight — The MECHANISM claims are individually true (cos-model mismatch exists; no el-integral exists — grep for integral/accumulate in command_map is empty), BUT the headline empirical sink (vz=-1.84@5s, z=-18.4@10s) is a HALLUCINATION: those numbers come from the BARE plant with a flat throttle=0.5 (no gravity feed-forward), not the closed loop. In the actual closed loop the pilot applies throttle=hover/(cos*cos) (command_map.py:221) and altitude holds to ~0.1m even under hard maneuvering. The engagement IS flown essentially level. The cos-mismatch residual is 2 orders of magnitude too small to produce the claimed 18m sink.


---

## P3-strapdown-egomotion-timesync  ·  строгость 6.5/10
*Physicist — strapdown sensing, ego-motion & time-sync*

**Вердикт:** The core strapdown de-rotation kinematics are rigorously correct and internally self-consistent: the geometry sign conventions (az/el, el-rate negation), the gyro-derotation translation terms (dx=-f*omega_y*dt, dy=-f*omega_x*dt), and the cumulative roll inversion in derotate.world_pixel are bit-exact inverses of the seeker_sim forward render model (round-trip error 2e-13 px even at large roll). FT640 intrinsics are exactly as documented (f_px=707.08, 1.414 mrad/px, HFOV 48.70 deg, VFOV 39.81 deg) and ARE the pixel_loop default. The doc's internal time-sync derivation (residual lambda_dot ~ omega_dot*dt, with omega_dot=50 rad/s^2 angular ACCELERATION -> 0.25 rad/s ~10x signal) is dimensionally and numerically correct -- but the prompt's restatement as a 50 rad/s body RATE is physically wrong, since a constant rate produces a constant angle residual with zero time-derivative and thus no false rate. The hard-mount vs soft-mount argument is physically sound. The serious defects are integration-level, not formula-level: (1) the live closed-loop measurement chain (pixel_loop.py) uses a velocity-aligned, implicitly roll-stabilized boresight in which body roll is never baked into the rendered target pixel, yet the LOSComputer un-rotates by accumulated roll -- injecting false lambda_dot up to +/-0.15 rad/s under hard roll even with a PERFECT gyro; (2) the entire ORB/LK/RANSAC/phase-correlation ego cross-check and the MTI MotionGate are dead with respect to guidance output (gyro-only is the only wired ego path; MTI defaults off and is not imported by closed_loop/pixel_loop).

**Сильные стороны:**
- De-rotation inversion (derotate.world_pixel) is a bit-exact inverse of the simulator forward rotate-then-translate render model, including full non-small-angle roll, not just first order.  
  *(ev: fpv/seeker/derotate.py:27-33 (inverse R(+theta)) vs fpv/seeker/seeker_sim.py:432-433 (forward M=[[c,s],[-s,c]]=R(-theta)); verified round-trip max error 2.3e-13 px over 10000 random (dx_w,dy_w,theta,ego) incl |theta|<2 rad)*
- Sign/axis conventions are globally consistent across geometry, egomotion, los, and the sim forward model.  
  *(ev: fpv/seeker/geometry.py:182-184 (az=atan2(px-cx,f), el=atan2(-(py-cy),f)); fpv/seeker/egomotion.py:162-164 (dx=-f*oy*dt, dy=-f*ox*dt); fpv/seeker/los.py:306-307 (el_rate=-v_true_y*f/(f^2+dy^2)); verified pure-yaw omega_y>0 -> scene-left, downward pixel motion -> el_rate<0)*
- FT640 intrinsics match the documented numbers exactly and are the actual default for the pixel-in-the-loop measurement chain.  
  *(ev: fpv/seeker/geometry.py:122-152 + fpv/guidance/pixel_loop.py:108-123,244-246; computed f_px=707.076 (doc ~707), IFOV=1.414 mrad/px (doc ~1.41), HFOV=48.70 deg, VFOV=39.81 deg (doc ~39.8); Boson legacy model f_px=2128.5, 0.47 mrad/px also correct)*
- MTI homography rescale formula H_full = inv(S) @ H_small @ S is mathematically correct, and the parallax/false-mover argument in the docs is physically sound.  
  *(ev: fpv/seeker/mti.py:128-132; verified a 5px small-image translation maps to 8.33px full-res at s=0.6 (=5/0.6) as required; near-identity corner-displacement guard at mti.py:140-144 correctly rejects homographies that registered the moving target)*

**Находки:**

| Сев. | Категория | Вердикт | Находка | Свидетельство |
|---|---|---|---|---|
| high | unsound-assumption | flawed | Roll-stabilized rendering vs roll de-rotation injects false lambda_dot with a PERFECT gyro in the live closed-loop chain | `fpv/guidance/quad_sim.py:524-552 (roll-free frame), fpv/guidance/pixel_loop.py:445-503 (omega_z fed to ego_for_los), fpv/seeker/los.py:256-277 (un-rotate by cum_roll); measured az_rate std vs roll_rate sweep` |
| medium | dead-code | correct | LK / RANSAC / phase-correlation ego cross-check is dead code relative to all guidance output | `fpv/seeker/egomotion.py:184-235 (LK entry), fpv/guidance/pixel_loop.py:458-498 (only gyro_derotation called); grep shows sparse_lk_residual called only in fpv/seeker/__init__.py and tests` |
| medium | correctness-error | flawed | Phase-correlation fallback returns shift with INVERTED sign relative to the LK convention it claims to substitute | `fpv/seeker/egomotion.py:290 (LK: good_cur - good_prev) vs egomotion.py:336-347,370-371 (phase-corr cross_power=F_prev*conj(F_cur), returns dx_raw,dy_raw); numerical sign check` |
| medium | doc-code-mismatch | correct | MTI MotionGate (the documented look-down clutter discriminator) is off by default and not in the closed-loop path | `fpv/seeker/mti.py:38-80; fpv/guidance/pipeline.py:81,100,286-293 (motion_gate default False); no pipeline import in closed_loop.py/pixel_loop.py` |
| note | mis-calibration | correct | Time-sync sensitivity is correct in the docs but the prompt's rate-based framing is physically wrong | `docs/SEEKER_SCIENCE_DEEP_DIVE.md:931,975; fpv/seeker/seeker_sim.py:445-477 (fractional-frame gyro resample); pixel_loop.py:489-498 (scale-factor only, no time skew)` |
| note | design-strength | correct | Hard-mount mandate argument is physically correct | `docs/SEEKER_SCIENCE_DEEP_DIVE.md:935-948,974; fpv/seeker/seeker_sim.py:249-255,372-385,475-477` |

- **[HIGH] Roll-stabilized rendering vs roll de-rotation injects false lambda_dot with a PERFECT gyro in the live closed-loop chain** — pixel_loop renders the target pixel via compute_bearing_from_states, which builds the body frame purely from the velocity vector (boresight=vel/|vel|, body_right=boresight x world_up, body_up=body_right x boresight). Because body_right is always a cross product with world_up it is always horizontal, so the frame is IMPLICITLY ROLL-STABILIZED: the body roll attitude_rad[0] is never an input and never baked into the rendered target pixel. Yet pixel_loop feeds omega_z = d(attitude_rad[0])/dt into ego_for_los, and LOSComputer.update un-rotates the target centroid by the accumulated cum_roll. The de-rotation therefore removes a roll that was never present in the image, sweeping the world-pixel through a circle that did not exist -> a false LOS-rate. Numerically, with a world-stationary off-boresight target, a body rolling at 0/0.5/1/3 rad/s and gyro_scale_error=0 (PERFECT gyro), the az_rate std grows 0.0016 -> 0.0061 -> 0.0171 -> 0.110 rad/s and peaks at 0.158 rad/s -- far above the 0.01-0.1 rad/s terminal signal. This is the doc's own roll x off-boresight coupling term (SEEKER_SCIENCE_DEEP_DIVE.md:921) but here it is a SIM/de-rotation INCONSISTENCY, not a modeled physical error: the forward and inverse roll models disagree.
  - *Рекомендация:* Make the forward render and the inverse de-rotation consistent. Either (a) bake the body roll into the rendered target pixel in compute_bearing_from_states / pixel_loop (give the velocity-aligned frame a real roll DOF driven by attitude_rad[0]) so the LOSComputer roll un-rotation actually cancels something, or (b) if the doctrine is a roll-stabilized boresight, do NOT pass omega_z into ego_for_los at all. As written, the omega_z path only ever adds error in the closed-loop sim; the wiring test (test_s3_honest_acceptance.py:272) candidly notes the sim under-rolls, which is exactly why this defect is hidden.

**Переderived числа (✓ совпало / ✗ расхождение):**

- ✓ **FT640 focal length f_px and IFOV**  
  - заявлено: f_px ~ 707 px, ~1.41 mrad/px (and Boson legacy f_px~2130, 0.47 mrad)
  - вывод: f_px = (640/2)/tan(radians(48.7)/2) = 707.076; 1/f_px = 1.4143 mrad/px. Boson: (640/2)/tan(radians(17.1)/2) = 2128.46; 1/f = 0.4698 mrad/px
  - прим.: Exact match. VFOV = 2*atan((512/2)/707.08) = 39.81 deg, HFOV = 48.70 deg, both match docs. Confirmed via geometry.ft640_intrinsics() that this is the pixel_loop default.
- ✓ **Time-sync false LOS-rate: 5 ms skew**  
  - заявлено: 5 ms skew -> 0.25 rad/s false lambda_dot, ~10x the signal
  - вывод: Correct mechanism: residual = omega_dot * dt = 50 rad/s^2 * 0.005 s = 0.25 rad/s. Signal ~0.025 rad/s -> ratio 10x. PROMPT's omega=50 rad/s framing: angle residual = 50*0.005 = 0.25 rad, but d/dt of a constant residual = 0 -> no false rate for constant rate.
  - прим.: Doc's omega_dot=50 rad/s^2 (acceleration) derivation is correct. Prompt's 50 rad/s (rate) framing is physically wrong; a constant rate gives a constant angle bias, not a false rate. The skew is modeled correctly in seeker_sim (fractional-frame gyro resample) but NOT in pixel_loop.
- ✓ **De-rotation round-trip self-consistency (forward render vs derotate.world_pixel inverse)**  
  - заявлено: derotate.world_pixel is the exact inverse of the sim forward rotate-then-translate model (bit-identical)
  - вывод: Forward M=[[cos,sin],[-sin,cos]]=R(-theta) then +ego; inverse removes ego then applies R(+theta)=[[cos,-sin],[sin,cos]]. Verified max round-trip error 2.34e-13 px over 10000 random (dx_w,dy_w in +/-300/200, theta in +/-2 rad, ego in +/-50)
  - прим.: Exact inverse even at large roll angles (uses full rotation, not small-angle). The translation-before-rotation ordering is handled correctly.
- ✓ **MTI homography rescale H_full = inv(S) @ H_small @ S, s=0.6**  
  - заявлено: small-image homography rescales to full-res via inv(S) H_small S with S=diag([s,s,1])
  - вывод: x_small = S x_full; x'_small = H_small x_small; x'_full = inv(S) x'_small = inv(S) H_small S x_full -> H_full = inv(S) H_small S. Verified a 5px translation in small image maps to 5/0.6 = 8.33px full-res.
  - прим.: Correct. RANSAC reproj tolerance is also correctly scaled by s (mti.py:125) and the corner-displacement guard is evaluated at full res on the rescaled homography.
- ✗ **False lambda_dot from roll de-rotation with PERFECT gyro (scale=0), stationary off-axis target**  
  - заявлено: implied near-zero (ideal de-rotation should null body roll)
  - вывод: Ran pixel_loop with stationary off-boresight target, gyro_scale_error=0, sweeping body roll 0/0.5/1/3 rad/s -> az_rate std 0.0016/0.0061/0.0171/0.110 rad/s, peak |az_rate| 0.158 rad/s
  - прим.: Disagrees with the ideal. Because the rendered target pixel is roll-stabilized (roll never baked in) but LOSComputer un-rotates by accumulated roll, body roll injects false lambda_dot proportional to roll rate -- up to 6-10x the terminal signal at 3 rad/s, with a PERFECT gyro. This is a forward/inverse model inconsistency, not modeled physics.
- ✓ **gyro_scale_error wiring reaches de-rotation**  
  - заявлено: 10% gyro scale error must change the LOS-rate under roll (test_s3_honest_acceptance)
  - вывод: Ran pixel_loop with body roll 2-3 rad/s, off-axis target; |az_rate(scale=0) - az_rate(scale=0.1)| reached 0.080 rad/s; deterministic wiring test passes (d>1e-6)
  - прим.: Wiring is genuine and reaches ego_for_los via omega_z_los = omega_z_full*(1+gyro_scale_error) (pixel_loop.py:493). But its closed-loop effect is negligible because the velocity-aligned boresight under-rolls in the sim's own frame; the test honestly states this. The effect that DOES appear is partly the roll-stabilization artifact above, not a clean scale-factor sensitivity.

**Верификация (уверенность):** high — all six findings re-derived against the executable code and confirmed; quant checks [0] (f_px=707.08, 1.414 mrad/px; Boson 2128.46), [2] (round-trip 2.27e-13 px), [3] (5px->8.33px, H_full=inv(S)H_small S) reproduced exactly; [1] (time-sync 0.25 rad/s = 10x signal) and [5]/[4] wiring confirmed by direct simulation (perfect-gyro roll injection reproduced to within scenario tolerance; scale-error sensitivity 0.088 rad/s at 3 rad/s roll). Two added missed issues (dead cum_roll_rad accumulator; inert pitch/yaw ego translation) strengthen Finding [0]/[1]. Only caveat: the analyst's exact mid-roll std numbers in quant[4] are scenario-dependent and ~2x lower in my reproduction, though the endpoints and qualitative conclusion match.

*Опровергнуто/преувеличено аналитиком (поймал верификатор):*
- Finding [0] cites quad_sim.py:524-552 for the 'roll-free frame'; the frame construction is actually quad_sim.py:524-534 (lines 535-552 are the az/el projection and atan2 conversion, not the frame basis). Minor line-range imprecision, not a substantive error.
- Finding [2]'s worked example states 'cur=roll(prev,+5,+7) yields LK-convention +(5,7) but phase-corr returns (-5,-7)'. The numbers are axis-transposed: np.roll axis-0(+5)=row=dy, axis-1(+7)=col=dx, so LK gives (dx,dy)=(+7,+5) and phase-corr gives (-7,-5). The sign-inversion conclusion is correct; only the (5,7)<->(7,5) labeling is off.
- Finding [0]/quant[4] reported az_rate std 0.0016/0.0061/0.0171 for roll 0/0.5/1 rad/s; my reproduction gave 0.0008/0.0029/0.0121 for the same rates. The high-roll endpoint matches (0.108 vs 0.110 at 3 rad/s; peak 0.151 vs 0.158) but the low/mid-roll absolute values are scenario-dependent and roughly 2x lower in my setup -- the analyst's exact mid-range numbers are not reproducible without their precise geometry. The qualitative claim (monotonic growth, perfect gyro, far above terminal signal at high roll) stands.

*Пропущено аналитиком, добавил верификатор:*
- **[medium] ps.cum_roll_rad is accumulated but never passed to the renderer -- a dangling roll accumulator that strengthens Finding [0]** — The dedicated roll accumulator intended to rotate the rendered scene is wired to nothing. This is not just an 'implicit' roll-stabilization (the analyst's framing) -- there is an explicit, named accumulator that was presumably meant to rotate the image and is silently dead. It makes Finding [0] more clearly a wiring bug than an architectural subtlety: the forward render path drops roll on the floor while the inverse (LOSComputer._cum_roll_rad from ego_for_los) faithfully removes it.  
  *(ev: pixel_loop.py:503 accumulates ps.cum_roll_rad += ego_for_stars.roll_rad (the FULL true roll), and PixelLoopState declares cum_roll_rad (pixel_loop.py:265) documented as 'Cumulative roll angle for star rendering'. But the _render_one_frame call (pixel_loop.py:513-523) passes only cum_ego_dx/dy and omits cum_roll_rad entirely; _render_one_frame has no roll parameter (pixel_loop.py:130-148) and stars are placed by translation only (pixel_loop.py:186-187).)*
- **[low] LOSComputer's translational ego (_cum_ego) stays exactly zero in the live path, so the pitch/yaw translation that IS rendered into the stars is never de-rotated -- only the velocity-frame target self-consistently lacks it** — The design note (pixel_loop.py:468-488) argues this is correct because the velocity-aligned boresight already moves the TARGET pixel for pitch/yaw. That is self-consistent for the target, but it means the LOSComputer's world-pixel de-rotation is only ever applied to a frame whose target carries pitch/yaw but whose ego-translation channel is identically zero. The pipeline's pitch/yaw ego-compensation is therefore never actually exercised in the live closed loop (it is a no-op), paralleling the dead-code concern in Finding [1]. Worth flagging as another 'documented-but-inert' compensation path.  
  *(ev: ego_for_los is built with omega_x=0, omega_y=0 (pixel_loop.py:495), so gyro_derotation returns shift_px=(0,0) (egomotion.py:162-163 with ox=oy=0). LOSComputer accumulates _cum_ego_x += 0 (los.py:256-257). Meanwhile _render_one_frame translates stars by ps.cum_ego_dx/dy from ego_for_stars (full pitch/yaw, pixel_loop.py:501-502).)*
- **[note] el_rate and az_rate use a per-axis small-angle denominator (f^2+dx^2) vs (f^2+dy^2) independently, which is only exact on-axis** — For a target offset in BOTH axes the pinhole bearing-rate Jacobian couples the axes; treating az purely as atan2(dx,f) and el purely as atan2(-dy,f) ignores the f^2+dx^2+dy^2 coupling. For the small terminal offsets here the error is second-order and negligible, but the docstring (los.py:294-301) presents these as exact derivatives. Not load-bearing for the campaign numbers, hence 'note', but it is a doc-vs-derivation imprecision adjacent to the verified findings.  
  *(ev: los.py:306-307: az_rate = v_true_x*f/(f^2+dx_world^2), el_rate = -v_true_y*f/(f^2+dy_world^2), where dx_world,dy_world are the SEPARATE axis offsets (los.py:303-304). The true Jacobian of az=atan2(dx,f) w.r.t. an off-axis pixel that also has a dy component is not separable this way for the full 3D bearing.)*


---

## S1-safety-killchain  ·  строгость 6/10
*Systems professional — safety architecture & kill chain*

**Вердикт:** The arming core, failsafe, and HW-kill modules are genuinely well-engineered for the part of the problem they cover: kill is dominant/sticky, non-finite clocks and expired authorizations fail safe to KILLED, and the HW-kill is a true default-deny AND-gate modeling an independent MCU. 58 non-crypto safety tests pass and the SIL loop closes (link-loss drives ABORT->KILLED->effective_motor_power=False). HOWEVER, three load-bearing doctrine claims are materially weaker in code than the docstrings/master-plan assert. (1) The kill chain is a TETHER, not an onboard fire-and-forget abort authority: both the software ABORT and the HW-kill cut depend on continuous ground RF (telemetry + permit beacon); link-loss=>safe is correct doctrine but means the system cannot complete an autonomous engagement through jamming. (2) The Ed25519 dual-operator console exists and is cryptographically reasonable, but is NOT wired into OnboardRuntime or sil_runtime (which fabricate verifier_passed=True directly), the crypto module cannot even import here, and it has no replay protection. (3) Inv5's in-FOV and ten-tau wall and Inv7's post-commit no-new-track are doc-claimed but absent from the command/firing path: only the 0.84 g clamp is enforced.

**Сильные стороны:**
- Kill is dominant, sticky, and evaluated first every tick; a non-finite clock fails safe to a recoverable-only-via-reset KILLED rather than a silent hold.  
  *(ev: arming.py:182-190 (non-finite clock -> kill() before any other branch), :159-167 (kill latches _killed, abort() delegates to kill()), :188-190 (kill checked before state dispatch))*
- Authorization arming is genuine default-deny: verifier_passed + unexpired + finite window + keypress-in-window all required, and the FIRE keypress is embedded in the auth window rather than a free-floating latch (the stale-keypress auto-arm bug is designed out).  
  *(ev: arming.py:78-103 (authorized() and committed() conjunctive guards), :99-102 (issued<=keypress<=expires), :83-84 (non-finite now/expires => not authorized))*
- The independent HW-kill is a correct default-deny dominant AND-gate: power requires a live permit beacon AND no latch, and effective_motor_power = fc_commands_motors AND hw_kill_enabled.  
  *(ev: hwkill.py:73-76 (latched=>False, else beacon.healthy), :86-89 (effective_motor_power AND-gate), failsafe.py:46-51 (Watchdog.healthy rejects backwards-clock and unfed))*
- The true-NIS model_wrong_alarm behind engage_permitted is statistically sound: it uses the rate-channel innovation covariance S (not R-only), so a real maneuver inflates S and does NOT trip it; only a sustained (5-frame) exceedance does.  
  *(ev: imm.py:461 (S_combined = H P_pred H^T + R, H=I4), :579-591 (Srr=S_combined[2:4,2:4], nis_true=ir@inv(Srr)@ir, sustain counter), :216-217 (nis_gate_chi2=9.21 2-DOF 99%, nis_sustain_for_alarm=5))*
- The msp_codec sanitises non-finite guidance to safe RC: symmetric axes degrade to neutral and throttle degrades to idle, never high throttle, and every channel is hard-clamped to [1000,2000] us.  
  *(ev: msp_codec.py:176-194 (symmetric_to_us/throttle_to_us NaN->0.0), :172-173 (clamp_us), arming.py test test_ai_active_nan_command_degrades_to_neutral_idle passes)*

**Находки:**

| Сев. | Категория | Вердикт | Находка | Свидетельство |
|---|---|---|---|---|
| critical | dead-code | flawed | Ed25519 dual-operator authorization is dead code relative to the runtime: OnboardRuntime/sil_runtime never invoke HandoffVerifier and fabricate verifier_passed=True directly | `onboard_runtime.py:75-77 + 86; sil_runtime.py:155-167, :213-215; console/console.py:79-84 (HandoffVerifier.verify, only caller is LaunchConsole.press_fire); grep: only console.py imports fpv_ai.console outside tests; pytest collection error 'No module named cryptography' on console tests` |
| high | correctness-error | flawed | No replay protection on the engagement handoff — a captured SignedHandoff re-authorizes arming until expiry | `console/console.py:50-84 (verify has no replay/nonce check), :145 (handoff_id=hk-{counter}); handoff.py:76-94 (canonical body has no nonce field beyond handoff_id which is never enforced unique)` |
| high | doc-code-mismatch | mixed | Inv5 enforces ONLY the 0.84 g clamp — the in-FOV and ten-tau-wall conjuncts are absent from the command path | `bearing_rate.py:549-552, :529-546; command_map.py:290-298 (no FOV clamp), :301-337 (tau switches timing only, default off); pixel_loop.py:134-176 (target_in_fov is render scene flag); test_doctrine_invariants.py:14 (claim) vs :129-138 (only g-budget asserted); docs/PROJECT_COMPLETION_PLAN.md:110, FIRE_AND_FORGET_AUTONOMY_BRIEFING.md:92 (FOV clamp listed as TODO)` |
| high | doc-code-mismatch | mixed | Inv7 (post-commit no NEW track) is enforced only as a single-frame out-of-family veto inside the gate — HARD_LOST auto-reset can adopt a fresh, different target | `arming.py:61-76 (no track identity in auth); onboard_runtime.py:86 (no identity check on guidance_command); track.py:501-515 (HARD_LOST auto-reset to NO_TARGET); handoff.py:48-49 (track_id present in order but dropped); test_doctrine_invariants.py:152-163 (only single-frame in-gate veto tested); docs/FIRE_AND_FORGET_AUTONOMY_BRIEFING.md:335` |
| medium | mis-calibration | correct | The kill chain is a TETHER (link-loss => abort, beacon-loss => power cut), not a self-contained onboard fire-and-forget abort authority | `failsafe.py:99-101 (link loss dominant ABORT), hwkill.py:36 + 73-76 (power requires live beacon), sil_runtime.py:193-201 (link_loss drops beacon), SIL run: link_loss_at=20 -> aborted=True final_state=KILLED eff_power=False` |
| low | unsound-assumption | correct | abort_g_margin default is 1.0 but the field still allows >1.0 which would silently saturate; clamp and abort agree only at the default | `bearing_rate.py:246 (abort_g_margin=1.0, no validation), :277-289 (effective_max_a_cmd caps at a_max regardless of margin), :529 (envelope_ok uses a_max*margin)` |
| note | design-strength | correct | OnboardRuntime aborts only WHILE armed; a stale link before arming is a no-op, relying entirely on the auth gate | `onboard_runtime.py:81-83 (abort only if is_armed), arming.py:213-226 (_tick_safe/_tick_prearm gate on _authorized/_committed)` |

- **[CRITICAL] Ed25519 dual-operator authorization is dead code relative to the runtime: OnboardRuntime/sil_runtime never invoke HandoffVerifier and fabricate verifier_passed=True directly** — console/handoff.py and console/console.py implement a real dual-signed Ed25519 engagement order (two distinct trusted keys, canonical JSON body, expiry, keypress-in-window, KINETIC roe_pass + synthetic-block). BUT no runtime consumes it. OnboardRuntime.step takes an ArmingAuthorization parameter and passes it straight to arming.authorize (onboard_runtime.py:75-77); sil_runtime._bench_authorization constructs ArmingAuthorization(verifier_passed=True,...) by hand (sil_runtime.py:159-167). A grep shows the only non-test importer of fpv_ai.console is console.py itself. So the cryptographic gate is never on the path between pixels and arming — the ArmingAuthorization.verifier_passed boolean is trusted blindly by the arming core, and nothing onboard checks signatures. Additionally `cryptography` is not installed in this environment, so handoff.py cannot even import (its tests ERROR on collection), confirming the crypto path is unexercised by the runnable system.
  - *Рекомендация:* Wire HandoffVerifier into the onboard authority path: OnboardRuntime should accept a SignedHandoff (not a pre-trusted ArmingAuthorization) and run HandoffVerifier.verify onboard before arming.authorize, so signature/dual-key/expiry are checked by the consumer. Make `cryptography` a hard production dependency (verifier.py's HMAC fallback must NOT be reachable for the engagement order). Until wired, the 'dual-signed authorization gates arming' claim is unsubstantiated in the executable system.
- **[HIGH] No replay protection on the engagement handoff — a captured SignedHandoff re-authorizes arming until expiry** — HandoffVerifier.verify checks signatures, dual-key distinctness, expiry, and keypress-window, but never records or rejects a previously-consumed handoff_id (or nonce). handoff_id is a monotonic 'hk-{counter}' (console.py:145) with no onboard seen-set. Within the TTL window (default 90 s console / 100 s SIL), an attacker who captures the signed order off the wire can replay it to re-arm. canonical_order_bytes is deterministic, so the captured signature stays valid. There is no nonce, no journal-of-consumed-IDs, and replay_events in verifier.py is for a different (G2U) journal and does no dedup.
  - *Рекомендация:* Add an onboard monotonic counter or consumed-handoff_id set (persisted across reset within a sortie) and reject any handoff_id <= last-accepted or already-seen. Shorten TTL to the minimum operational window. This is standard two-man-rule replay hardening.
- **[HIGH] Inv5 enforces ONLY the 0.84 g clamp — the in-FOV and ten-tau-wall conjuncts are absent from the command path** — Doctrine Inv5 (master plan, test_doctrine_invariants docstring line 14) states 'Every command <= 0.84 g lateral, in-FOV, corrections before the ~1.0-1.4 s ten-tau wall.' In code only the first conjunct exists: bearing_rate.compute clamps |a_cmd| to effective_max_a_cmd()=a_max (bearing_rate.py:549-552) and aborts above a_max*abort_g_margin (:529-546). There is NO FOV/look-angle clamp on commanded tilt in command_map.py — roll is just atan2(a,g)/theta_max clamped to [-1,1] (command_map.py:290-298); pixel_loop.py's target_in_fov is a frame-renderer scene flag (pixel_loop.py:134-176, :405-410), not a command gate. There is NO ten-tau commit cutoff: use_tau_terminal only switches ACRO/LOS-hold timing (command_map.py:301-337) and defaults OFF; the docs themselves admit the ten-tau wall is unimplemented ('realize/relabel the ten-tau wall', PROJECT_COMPLETION_PLAN.md:110). The Inv5 CI test (test_doctrine_invariants.py:129-138) asserts only a_tot <= a_max — it does not test FOV or ten-tau, so the green test gives false assurance on two of the three claimed properties.
  - *Рекомендация:* Either (a) implement the FOV-constrained commanded-tilt clamp and the t_go<~10*tau_system predicted-lead cutoff and extend the Inv5 test to assert both, or (b) re-scope the Inv5 docstring/master-plan to claim only the g-budget that is actually enforced. The current state is a doc-vs-code mismatch that overstates the safety envelope. For a strapdown body-fixed seeker the missing FOV clamp is the named failure mode (commit maneuver swings target out of frame).
- **[HIGH] Inv7 (post-commit no NEW track) is enforced only as a single-frame out-of-family veto inside the gate — HARD_LOST auto-reset can adopt a fresh, different target** — Inv7 doctrine: 'Post-commit, acquiring a NEW track is forbidden; re-acquire only the SAME committed track.' In code there is no COMMIT state binding the firing authority to a target identity. The EngagementOrder carries target.track_id (handoff.py:48-49) but ArmingAuthorization strips it entirely (arming.py:61-76 has no track field), and OnboardRuntime.step accepts whatever guidance_command the pipeline emits with zero identity check (onboard_runtime.py:86). What enforces Inv7 is purely the tracker's in-gate out-of-family rejection (test_doctrine_invariants.py:152-163), and crucially track.py:508-515 AUTO-RESETS HARD_LOST -> NO_TARGET, re-seeding the acquisition basket so a re-appearing or DIFFERENT target can climb CANDIDATE->LOCKED again. Combined with the seeker re-seeding the centered basket on reacquire, a post-loss lock can be a new object. The doctrine's 'anti-lock-theft / LOBL-not-LOAL geometric invariant' is acknowledged as TODO in the briefings (FIRE_AND_FORGET_AUTONOMY_BRIEFING.md:335 'forbid acquiring any new track post-COMMIT').
  - *Рекомендация:* Introduce a COMMIT state that binds the authorized target.track_id to the engagement; after commit, forbid the tracker from seeding a new lock (HARD_LOST should ABORT/safe-ditch, not auto-reseed) and require re-acquisition to match the committed track's kinematic family within a geometric basket. Today the 'same committed track only' property holds only across a single in-gate frame, not across a loss/reacquire cycle.

**Переderived числа (✓ совпало / ✗ расхождение):**

- ✓ **a_max lateral at theta_max=40 deg (the '0.84 g' body limit)**  
  - заявлено: a_lateral_max ~= 8.22 m/s^2 ~= 0.84 g (quad_sim.py:9, bearing_rate.py:245)
  - вывод: a_max = g*tan(40deg) = 9.81*0.83910 = 8.2316 m/s^2; /9.81 = 0.83910 g
  - прим.: Matches. achievable_g()=tan(theta_max) (bearing_rate.py:273-275) and a_max_mps2()=9.81*tan (:269-271) are dimensionally and numerically correct.
- ✗ **Inv5 conjuncts actually enforced in the command path**  
  - заявлено: 3 conjuncts: <=0.84 g AND in-FOV AND before ten-tau wall (test_doctrine_invariants.py:14)
  - вывод: Traced command_map.py + bearing_rate.py: only the g-clamp (effective_max_a_cmd) and ROE abort are present. No FOV/look-angle clamp on commanded tilt; ten-tau cutoff unimplemented (use_tau_terminal switches timing only, default OFF). So 1 of 3 enforced.
  - прим.: Doc overstates by 2 of 3 conjuncts. The Inv5 CI test asserts only the g-budget, so it passes green while two claimed properties are absent.
- ✓ **model_wrong_alarm firing threshold (sustained true-NIS)**  
  - заявлено: SUSTAINED true-NIS exceedance; nis_gate_chi2=9.21 (2-DOF 99%), nis_sustain_for_alarm=5 (imm.py:216-217)
  - вывод: chi-square 2-DOF 99% quantile = 9.2103; alarm = _nis_bad_count >= 5 consecutive frames with nis_true>9.21 (imm.py:587-591). Srr is the 2x2 rate-channel block of S_combined=P_pred+R (H=I4), so nis_true=ir@inv(Srr)@ir is the correct 2-DOF normalized innovation squared.
  - прим.: Statistically sound. Using S (not R) means a genuine maneuver inflates Srr and does not trip the alarm; only unexplained sustained residuals do. The engage_permitted default-deny signal is well-grounded.
- ✗ **engage_permitted consumption in the firing path**  
  - заявлено: default-deny suppresses the command when model-wrong (sil_runtime.py:20-24)
  - вывод: engage_permitted is consumed ONLY in sil_runtime.py:208 (flown_cmd = out.command if out.engage_permitted else None). OnboardRuntime (the production orchestrator) never reads engage_permitted — grep of onboard_runtime.py shows it takes guidance_command pre-filtered. So the gate is wired in the SIL demo wrapper, not in the reusable runtime.
  - прим.: The audit-flagged wire is closed only in sil_runtime, which is itself a bench harness (synthetic auth, MockFcChannel). The reusable OnboardRuntime.step still flies whatever command it is handed. Any other consumer of OnboardRuntime must replicate the suppression.
- ✓ **HW-kill beacon timeout vs software link timeout ordering**  
  - заявлено: beacon_timeout_s (0.5) >= software link failsafe (0.2) so controlled ditch runs first (hwkill.py:35-36)
  - вывод: link_timeout_s=0.2 (failsafe.py:68) < beacon_timeout_s=0.5 (hwkill.py:36). So software ABORT fires at 0.2 s of silence; HW power cut at 0.5 s. Ordering is correct — controlled safe-ditch precedes the guaranteed backstop cut.
  - прим.: Correct and self-consistent. Both are watchdogs that also reject backwards clocks (failsafe.py:46-51).

**Верификация (уверенность):** High. All 7 findings and all 5 quantitative checks were independently re-opened at the cited code and re-derived. chi2(2-DOF,99%)=9.2103 matches nis_gate_chi2=9.21; a_max=9.81*tan(40deg)=8.2316 m/s^2=0.8391 g matches the 0.84 g claim; link_timeout(0.2)<beacon_timeout(0.5) ordering confirmed; S_combined=H·P_pred·H^T+R with H=eye(4) (imm.py:288,461) confirms the rate-block true-NIS derivation; engage_permitted consumed only at sil_runtime.py:208, never in onboard_runtime (confirmed by grep). The SIL link-loss run was executed and reproduced aborted=True/KILLED/eff_power=False. The analyst's findings are accurate with no hallucinations; the two quant-check 'agree=false' verdicts (Inv5 conjuncts 1-of-3, engage_permitted wired only in the bench harness) are correct. I added four missed issues, the most important being the operator_abort doc-vs-code mismatch on the HW-kill (medium)."

*Опровергнуто/преувеличено аналитиком (поймал верификатор):*
- None. Every load-bearing claim in findings 0-6 was re-opened at the cited file:line and matched the executable code. Minor citation drift only: finding 5 cites 'bearing_rate.py:269-289' and ':277-289' for effective_max_a_cmd, where 269-271 is actually a_max_mps2() and the effective_max_a_cmd method body is 277-289 — substantively correct. Finding 0 cites 'sil_runtime.py:213-215' for the synthetic auth, where the _bench_authorization definition is actually 155-167 and line 213 is its call site — both correct, no fabrication.
- Finding 4's paraphrase of the hwkill comment ('still fires when all of those are dead or compromised') as 'true for the CUT direction only' is a reasonable gloss, not a hallucination: the source comment (hwkill.py:11-13) is literally about the decision's independence from FC/Pi/MSP/ELRS, and the analyst correctly maps that to the autonomous CUT while noting ENABLE needs the live beacon.

*Пропущено аналитиком, добавил верификатор:*
- **[medium] OnboardRuntime.operator_abort does NOT drive the HW-kill, contradicting its own docstring** — Doc-vs-code mismatch on the kill chain. The OnboardRuntime's operator_abort is single-pathed (software disarm only); the 'independent HW-kill is also driven by the same ABORT' guarantee is realized only inside LaunchConsole.abort (console.py:123-127), which the SIL never exercises (SIL drives the beacon directly and drops it on link loss). For an OnboardRuntime-only integrator this is a latent gap: the latched, sticky HW-kill is never engaged by an onboard operator abort.  
  *(ev: onboard_runtime.py:57-61 operator_abort calls ONLY self.arming.abort(reason); its docstring (:59-60) claims 'The SAME physical ABORT independently drives the HW-kill below the FC -- so power is cut even if this software path is dead.' But OnboardRuntime never holds nor calls hwkill.operator_kill. grep for non-test operator_kill callers returns ONLY console.py:127 (the ground console). So in the onboard runtime path an operator abort does NOT latch the independent HW-kill — power is cut only indirectly via the beacon stopping (a 0.5s timeout), not via the latched mushroom path the docstring promises.)*
- **[low] SIL link-loss path never exercises the latched HW-kill (operator_kill); it only relies on beacon-timeout** — The most safety-relevant HW-kill behavior — the sticky, latched mushroom that survives a transient and stays cut until physical reset — is exercised only in the console unit tests (which currently ERROR on collection because cryptography is missing). So the latched-kill invariant has no green end-to-end coverage in the runnable system.  
  *(ev: sil_runtime.py:193-201 sets fc.link_up=False and STOPS calling hwkill.permit_beacon on link loss; it never calls runtime.hwkill.operator_kill. grep confirms no non-test operator_kill caller except console.py. The SIL therefore validates the beacon-timeout CUT (Invariant 2 of hwkill) but not the latched operator-kill CUT (Invariant 3), and not the OnboardRuntime->HW-kill wire (which does not exist).)*
- **[low] abort() aliases to kill() making every failsafe ABORT sticky/unrecoverable without reset(), with no reset path in either runtime** — This is arguably the correct conservative posture (a link blip during a live kinetic engagement should not silently re-arm), and the analyst's finding 4 touches the abort behavior, but the STICKY/unrecoverable nature of a failsafe-driven abort — versus a transient HOLD_LAST — is not called out. Worth an explicit design note: HOLD_LAST coasts, but any ABORT is terminal for the engagement until a human resets, which is a strong (and probably intended) property.  
  *(ev: arming.py:165-167 abort() calls self.kill(reason); kill() sets self._killed=True (sticky). Recovery requires reset() (arming.py:169-175) plus a fresh committed authorization. grep shows NO reset() call in onboard_runtime.py or sil_runtime.py. So a single transient link blip (>0.2s) that trips failsafe ABORT latches KILLED permanently for the life of the process.)*
- **[note] Inv5 docstring numeric range '~1.0-1.4 s ten-tau wall' is asserted nowhere and undefined in code** — Adds to finding 2: not only is the ten-tau conjunct unenforced, the specific 1.0-1.4 s figure is un-rederivable from the code (it would depend on closing geometry and a defined 'commit' epoch, neither of which exist as state). Treat any '10-tau wall' claim as aspirational doctrine, not implemented behavior.  
  *(ev: test_doctrine_invariants.py:14 states 'corrections before the ~1.0-1.4 s ten-tau wall'; no constant, threshold, or test encodes 1.0-1.4 s. The only tau thresholds in command_map are terminal/LOS-hold phase switches (use_tau_terminal default False). The number is a doc artifact with no executable counterpart.)*


---

## S2-test-honesty-vv  ·  строгость 7/10
*Systems professional — V&V & test-honesty auditor*

**Вердикт:** The team has done unusually honest self-V&V: the suite is explicitly split into near-tautological Mode-A ideal-measurement gates (test_s3_acceptance.py) and a de-tautologized honest gate (test_s3_honest_acceptance.py), and the headers say so. The central truth: the 100% hit / sub-cm miss headline is a Mode-A artifact: in Mode A the loop injects the analytically-TRUE LOS-rate from compute_los_rates(q_state,tgt_state) plus white noise directly into guidance (closed_loop.py:578-617), bypassing the detect->ego->los->IMM-from-pixels chain, so those gates grade PN math under a perfect sensor, not the system. The honest gate is real: it injects a correlated AR-1 lambda-dot bias + noisy looming area + latency jitter and PINS that crossing/quartering geometry collapses (hit->abort) while head-on stays robust, and that the system hits-or-fails-safe. The run_monte_carlo carry-through fix is now correct (empirically honest-ON HEAD_ON miss 0.0562 m vs OFF 0.0467 m, ratio 1.20), though its guard threshold (>1.2x) is razor-thin. Two weaknesses: the bit-identity test is new-vs-new in-process (test_monte_carlo.py:30) so it cannot catch a changed DEFAULT, and two real default-ON changes exist (IMM measurement_mode -> correlated_r; camera f_px 2130 -> 707) that no frozen golden guards; and the NEES gate is now one-sided (optimistic hard-fails, conservative only xfails, so green no longer proves full calibration). Mode B IS a real chain but coverage is thin (4-6 seeds) and honestly pins that it does NOT close an 80 m quartering intercept (~7.4 m).

**Сильные стороны:**
- The suite is honestly self-labelled: test_s3_acceptance.py's header explicitly states it runs Mode A with the analytically-TRUE LOS-rate, the seeker bypassed, and the honest knobs OFF, and that its green hit-rate must NOT be read as fielded capability.  
  *(ev: test_s3_acceptance.py:3-13 (SCOPE warning); closed_loop.py:578-583 and 614-617)*
- The honest gate genuinely de-tautologizes: it injects a CORRELATED AR-1 lambda-dot bias (not white, so it does not average out in the IMM), noisy/quantized looming area, and latency jitter, and PINS the geometry-dependent collapse with hit->abort doctrine (abort=PASS, wrong-hit=HARD-FAIL).  
  *(ev: test_s3_honest_acceptance.py:51-78, 153-192; closed_loop.py:606-617)*
- The 7 doctrine invariants are enforced by introspection-based structural guards, not comments: compute takes no range arg, IMM/Tracker.update reject quality kwargs, the command schema has no gimbal fields.  
  *(ev: test_doctrine_invariants.py:66-80 (Inv1), 85-98 (Inv2), 143-147 (Inv6); confirmed 10 passed in 1.03s)*
- Mode-B end-to-end and Gate-O are honestly graded by ABSOLUTE miss with xfail/pin escape hatches rather than forced green; they explicitly pin that the pixel pipeline does NOT close an 80 m quartering intercept (~7.4 m) and xfail head-on if the chain stops closing.  
  *(ev: test_modeb_endtoend_acceptance.py:283-296; test_s3_modeb.py:453-466)*

**Находки:**

| Сев. | Категория | Вердикт | Находка | Свидетельство |
|---|---|---|---|---|
| high | unsound-assumption | flawed | Mode-A acceptance is near-tautological: true LOS-rate injected directly into guidance, seeker bypassed | `closed_loop.py:576-621 (Mode A branch); quad_sim.py:555-614 (compute_los_rates from true states); test_s3_acceptance.py:215 (mode=analytic) via _make_cfg` |
| high | unverifiable-claim | unverifiable | Bit-identity determinism test is new-vs-new in-process and cannot catch a changed DEFAULT | `test_monte_carlo.py:30 (a==b); test_a5_montecarlo.py:33 (scalar default); imm.py:176-188; closed_loop.py:138, pixel_loop.py:108-123, pipeline.py:123-127` |
| medium | mis-calibration | mixed | NEES consistency gate made one-sided: conservative miscalibration now xfails instead of asserting in-bound | `test_filter_consistency_nees.py diff (optimistic -> assert False; mean_nees<nees_lo -> pytest.xfail); imm.py diff:426-449; derived correlated_r rate 1-sigma ~0.042 vs legacy 0.005 (8.5x)` |
| medium | mis-calibration | correct | Honest-MC bias-injection guard passes by a razor-thin margin (ratio 1.20 vs threshold >1.2) | `closed_loop.py diff:968-976; test_s3_honest_acceptance.py:195-211; reproduced 12 seeds off=0.04666 on=0.05619 ratio 1.20` |
| medium | unsound-assumption | mixed | Mode-B coverage is thin and head-on-centric; dominant strapdown error proven only at wiring level | `test_s3_honest_acceptance.py:246-269, 272-301; test_modeb_endtoend_acceptance.py:77; test_s3_modeb.py:77` |
| medium | doc-code-mismatch | mixed | Camera-model default flip (Boson f_px 2130 -> FT640 707) is load-bearing and pinned only indirectly | `closed_loop.py:130-138,587-593; pixel_loop.py:108-123; pipeline.py:123-127; test_s3_honest_acceptance.py:112-123; test_s3_modeb.py:715-719` |
| low | dead-code | flawed | peek_delayed uses nominal (un-jittered) delay, inconsistent with pop_delayed | `closed_loop.py:313-320 (pop_delayed uses _effective_delay) vs 322-330 (peek_delayed uses nominal self._delay_s)` |
| low | dead-code | correct | APN term is permanently zeroed but maneuver path still flagged active (honest but dead) | `bearing_rate.py:486-518` |

- **[HIGH] Mode-A acceptance is near-tautological: true LOS-rate injected directly into guidance, seeker bypassed** — In Mode A the vision tick computes az/el and az_rate/el_rate analytically from the true relative kinematics via compute_bearing_from_states and compute_los_rates, adds white per-frame noise (sigma=3e-4 rad bearing, 3x for rate), and pushes THAT to the delay buffer driving guidance. The detect->ego->los->IMM-from-pixels chain is skipped; the outer IMM (closed_loop.py:717) merely re-filters truth+white-noise. The entire test_s3_acceptance.py file (Gates I,J,K,L,M) thus grades PN math under a PERFECT bearing-rate sensor. The 100% hit / 0.003-0.04 m miss / real-spread results are properties of the 3e-4 rad clean measurement, not seeker robustness. Explicitly disclosed, but dominant by test count.
  - *Рекомендация:* Keep Mode-A gates labelled as unit-level guidance-math sanity. Do NOT report any Mode-A hit-rate/miss as system acceptance. Consider renaming the file to remove the residual acceptance implication.
- **[HIGH] Bit-identity determinism test is new-vs-new in-process and cannot catch a changed DEFAULT** — The only behavioral bit-identical assertion compares two run_monte_carlo(randomize=False) calls in the SAME process (a==b): determinism, not invariance vs a baseline. The pervasive default-0 bit-identical comments are not enforced by any frozen golden. The working tree has TWO genuine default-ON changes with no golden guard: (1) IMM measurement_mode default flipped diagonal_r -> correlated_r, changing posterior covariance and NIS/NEES; (2) camera intrinsics default flipped Boson f_px=2130 -> FT640 707 in closed_loop._FT640_F_PX, pixel_loop._wide_fpv_intrinsics, pipeline:127. A regression flipping either default back leaves test_monte_carlo green (a and b shift together).
  - *Рекомендация:* Add a true frozen-golden test (store a baseline miss_distances array, assert np.allclose). Separately golden-pin IMM measurement_mode and intrinsics.f_px so a default flip fails loudly.

**Переderived числа (✓ совпало / ✗ расхождение):**

- ✓ **Achievable lateral g at theta_max=40 deg**  
  - заявлено: 0.84 g (8.23 m/s^2) per test_s3_acceptance.py:504, bearing_rate.py:245
  - вывод: tan(40 deg)=0.8391 g; *9.81=8.2316 m/s^2
  - прим.: Matches to stated precision; a_max derivation dimensionally and numerically correct.
- ✓ **Net lateral miss for a 1.5 g sustained step-jink at t=4 s, 80 m**  
  - заявлено: ~51 m (test_s3_acceptance.py:492-493)
  - вывод: 0.5*(1.5*9.81 - 8.2316)*16 = 0.5*6.483*16 = 51.9 m
  - прим.: Energy-bound argument sound; 1.5 g step-jink correctly uninterceptable (1.5 g > 0.84 g).
- ✓ **AR-1 lambda-dot bias: stationary std preservation and physical magnitude**  
  - заявлено: ~1 mrad/s from omega_body 0.5 rad/s x 2 ms cam-IMU skew; sigma preserved by k=sqrt(1-rho^2)*sigma
  - вывод: rho=exp(-(1/60)/0.30)=0.946; empirical stationary std over 20000 steps=0.001028 vs target 1e-3; 0.5*2e-3=1.0 mrad/s
  - прим.: AR-1 correctly preserves the specified stationary variance and the physical magnitude justification checks out exactly.
- ✓ **correlated_r rate-channel 1-sigma vs legacy diagonal rate sigma**  
  - заявлено: diagonal_r treated rate as independent precise measurement (0.005 rad/s), causing optimistic NIS~2
  - вывод: correlated_r rate 1-sigma = sqrt(2)*5e-4/(1/60) = 0.0424 rad/s, i.e. 8.5x the legacy 0.005
  - прим.: Confirms legacy diagonal-R was ~8.5x over-precise on the rate channel; the correlated-R covariance is the textbook finite-difference model, dimensionally correct.
- ✓ **run_monte_carlo honest-knob carry-through effect on HEAD_ON median miss**  
  - заявлено: honest ON miss must be > OFF miss * 1.2 (test_s3_honest_acceptance.py:209)
  - вывод: Reproduced 12-seed: OFF=0.04666 m, ON=0.05619 m, ratio=1.20 (0.05619 > 0.05599, margin 0.4%)
  - прим.: Carry-through is real and the guard passes, but only barely; assertion margin ~0.4%, a fragile sentinel.
- ✓ **Fast structural-honesty gate pass count**  
  - заявлено: doctrine invariants + A5 montecarlo all green
  - вывод: Ran test_doctrine_invariants.py + test_a5_montecarlo.py: 10 passed in 1.03s
  - прим.: The 7 doctrine invariants and A5 jitter/bit-identical-default checks pass cleanly; the most meaningful structural guards are genuinely green.

**Верификация (уверенность):** high — all 8 findings and all 6 quantitative checks were re-derived/re-run against the actual code. QC0 (tan40=0.839g/8.2316 m/s2), QC1 (51.87m), QC2 (rho=0.9460, empirical std=0.0010280 over 20000 steps), QC3 (correlated rate 1-sigma=0.0424 rad/s, 8.49x), QC4 (honest-MC OFF=0.0467/ON=0.0562, ratio 1.203), and QC5 (10 structural gates pass in 0.42s) all reproduce exactly. Findings [0],[2],[3],[4],[6],[7] confirmed; [1] and [5] partially-confirmed with a real hallucination caught (camera flip is committed at HEAD, not an uncommitted working-tree default change, and measurement_mode is a new field rather than a flipped prior default). Two substantive missed issues added: (a) the correlated_r R over-states the Mode-A rate-channel noise by ~1-2 orders of magnitude vs the actually-injected white rate noise, mechanistically explaining the conservative NEES that finding [2] waves through; (b) no MC test pins an absolute value, sharpening finding [1].

*Опровергнуто/преувеличено аналитиком (поймал верификатор):*
- Finding [1] claims the camera intrinsics flip (Boson f_px 2130 -> FT640 707) is one of 'TWO genuine default-ON changes' in the WORKING TREE with no golden guard. This is inaccurate: the FT640 flip is already COMMITTED at HEAD (git show HEAD:closed_loop.py:138 and HEAD:pixel_loop.py:123 both already use ft640_intrinsics). Only the measurement_mode change is uncommitted. The working-tree pixel_loop.py diff adds gyro_scale_error/last_detected_area_px plumbing, not an intrinsics default flip. The structural conclusion (no frozen golden, revert escapes test_monte_carlo) still holds for both defaults.
- Finding [1] says measurement_mode default was 'flipped diagonal_r -> correlated_r'. The field is BRAND-NEW in the working tree (no measurement_mode field exists at HEAD), defaulting to correlated_r. There was no prior diagonal_r default to flip; diagonal_r exists only as the opt-in legacy branch. Substance (new default changes P/NIS/NEES, unguarded) is correct.
- Finding [2] / finding [5] (and [1]) repeatedly frame the camera flip as part of the uncommitted Wave-3 diff; it is committed. Finding [2]'s CT_jink claim implies the conservative-NEES xfail branch fires, but in the current live run CT_jink xfails on the NIS-conservative branch first, not the NEES branch (the NEES conservative xfail code exists but is not reached today).

*Пропущено аналитиком, добавил верификатор:*
- **[medium] correlated_r R matrix is built from sigma_meas_az/el but the analytic measurements are generated with bearing_noise_sigma_rad and rate noise = 3x bearing -- a possible Q/R model/data mismatch** — The conservative NEES that finding [2] waves through is not an unexplained Q/R artifact: in Mode A the rate channel is generated 3x the bearing white-noise (~9e-4 rad/s for default sigma) while R models it at ~0.042 rad/s (the finite-difference assumption). The finite-difference covariance is the right model for a TRUE pixel finite-difference, but Mode A does NOT finite-difference -- it injects independent white rate noise. So correlated_r over-states rate noise by ~1-2 orders of magnitude on the Mode-A path, which mechanically produces a conservative (too-large-P) posterior. This is a model/data mismatch specific to Mode A, separate from the genuine pixel path.  
  *(ev: Mode-A measurements: noise_az ~ N(0, bearing_noise_sigma_rad), noise_az_rate ~ N(0, bearing_noise_sigma_rad*3.0) (closed_loop.py:601-604). The IMM correlated_r R uses sb_az=sigma_meas_az**2=(5e-4)**2 and rate variance 2*sb_az/dt2 = 2*(5e-4)^2/(1/60)^2 -> rate 1-sigma ~0.0424 rad/s (QC3). But the actual injected rate noise 1-sigma is 3*bearing_noise_sigma_rad; for the default bearing_noise_sigma_rad=3e-4 that is 9e-4 rad/s -- ~47x SMALLER than what R models. The injected white-noise rate is FAR more precise than R assumes, which by itself would make the posterior conservative -- a plausible mechanistic cause of the CV NEES=3.557 conservative xfail in finding [2], and evidence the correlated_r model is mis-matched to the Mode-A data-generating process, not just 'lands conservative.')*
- **[low] Mode-A outer IMM is fed the SMITH-PREDICTED bearing, not the raw measurement -- the IMM-vs-measurement consistency is on a derived input** — Strengthens finding [0]: the Mode-A IMM input is not just truth+white-noise, it is the Smith-advanced truth+white-noise, making the Mode-A consistency story even less representative of a real pixel-derived measurement chain.  
  *(ev: closed_loop.py:707-718 builds LOSObservation(az_rad=az_guided, az_rate_radps=az_rate_guided, ...) from the Smith-predictor-advanced bearings (az_guided computed after pop_delayed at :629), then calls imm.update. So in Mode A the IMM does not even see the analytic measurement directly; it sees a lead-extrapolated version. Any NEES/NIS run on the Mode-A IMM is measuring consistency against a doubly-processed (delay+Smith) truth-derived signal, further weakening the seeker-robustness interpretation of Mode-A gates.)*
- **[low] test_randomize_off_is_unchanged_default asserts equality but does NOT pin the value -- complements finding [1] gap** — Reinforces and sharpens finding [1]: the absence of even a single hard-coded expected miss/hit value in the MC determinism suite is the concrete reason a default revert is undetectable.  
  *(ev: test_monte_carlo.py:28-30 only asserts a==b (two fresh deterministic runs). There is no recorded scalar (e.g. assert miss_median == <frozen number>) anywhere in test_monte_carlo.py or test_a5_montecarlo.py. Combined with finding [1], NO test in the MC suite pins an absolute outcome value, so any default change that shifts a and b together is invisible.)*
- **[low] gyro_scale_error injects residual only on the LOS de-rotation (omega_z_los), not on the star-field world rotation -- so the unit test proves wiring but the magnitude is a single-sided model** — Adds nuance to finding [4]: not only is the intercept-level sensitivity unexercised, the injected residual itself is a single-axis (roll scale-factor) model, so the dominant strapdown error is only partially represented even at the wiring level.  
  *(ev: pixel_loop.py diff: omega_z_los = omega_z_full*(1+gyro_scale_error) feeds gyro_derotation, while the comment states 'the world (stars) rotated by the TRUE rate.' This correctly models a scale-factor residual, but the residual is applied ONLY to the in-plane roll de-rotation (z axis). A real cam<->IMU misalignment also couples pitch/yaw gyro errors into the bearing channels; the model exercises only the roll-scale term, so even the wiring unit test (test_gyro_scale_error_wiring_reaches_ego_derotation) under-represents the full strapdown error manifold.)*

*Вердикты «опровергнуто/частично»:*
- [partially-confirmed] [1] Bit-identity determinism test is new-vs-new in-process, cannot catch a changed DEFAULT — REFUTED sub-claim: the camera intrinsics flip (Boson 2130 -> FT640 707) is NOT a working-tree default change -- it is ALREADY COMMITTED at HEAD (git show HEAD:closed_loop.py:138 _FT640_F_PX=ft640_intrinsics().f_px ~707; HEAD pixel_loop.py:123 _wide_fpv_intrinsics returns ft640_intrinsics()). The working-tree pixel_loop diff only adds gyro_scale_error and last_detected_area_px plumbing, not an intrinsics flip. So the analyst's 'TWO genuine default-ON changes in the working tree' overcounts: only ONE (measurement_mode) is uncommitted. The structural point -- no frozen golden pins either default, a revert escapes test_monte_carlo -- holds for both.
- [partially-confirmed] [5] Camera-model default flip (Boson 2130 -> FT640 707) load-bearing, pinned only indirectly; 50-deg mislabel — PARTIAL because the flip is COMMITTED at HEAD, not a working-tree (Wave-3 uncommitted) change -- the analyst frames it as a current diff. The substance (indirect outcome pin, no direct golden on intrinsics.f_px, 50-deg stale label) is all correct.


---

## S3-systems-trl-hwgap  ·  строгость 4.5/10
*Systems professional — TRL, architecture & hardware-software gap*

**Вердикт:** This is an algorithmically rich, doctrinally clean, and unusually self-honest software seeker study at an integrated TRL of about three. The guidance and estimation spine is real and defensible, but the integrated detect to decide to intercept loop does not close. The decide segment is the worst gap because the kinetic authorization gate described in the README does not exist in code; the safety verifier is still the un-inverted ground anti-weapon blocklist and is not even imported by the arming path. The real-time budget fails by roughly nine to forty-eight times and the region-of-interest gating cannot save it because the motion-target-indication stage runs on the full frame. The hardware that physically exists is a stock manual visible-light FPV quad with a stock flight controller, not the assumed thermal seeker plus companion computer plus forked firmware plus independent kill controller plus permit beacon. The science is sound; the system is unbuilt below the algorithm layer.</summary>
<_sacrificial>["this unknown array parameter exists only to absorb the positional parser drop of the first array after the scalars"]

**Сильные стороны:**
- The IMM is genuinely modified-polar with the four-state azimuth, elevation, azimuth-rate and elevation-rate vector.  
  *(ev: fpv/seeker/imm.py lines 5, 269 and 329)*
- The Mode-B closed loop is non-tautological and the honesty knobs for looming-from-area, correlated bias and latency jitter are plumbed into the Monte-Carlo entry point.  
  *(ev: fpv/guidance/closed_loop.py lines 530 to 575, 609 to 610 and 138)*
- The documentation is adversarially self-honest; the S3 acceptance header labels itself ideal-measurement gates rather than system acceptance.  
  *(ev: fpv/guidance/tests/test_s3_acceptance.py lines 1 to 13)*
- The firmware verification doctrine is coherent and grounded in real Betaflight issues numbered 8292, 13374 and 13416.  
  *(ev: firmware/V_AND_V.md and firmware/betaflight-fork/PATCH.md)*

**Находки:**

| Сев. | Категория | Вердикт | Находка | Свидетельство |
|---|---|---|---|---|
| critical | doc-code-mismatch | flawed | Kinetic authorization gate in README does not exist; verifier is the un-inverted ground anti-weapon blocklist and is not wired into arming | `verifier.py lines 36 to 46 and 178 to 181; REFRAME_NOTES.md; arming.py lines 45 and 70` |
| critical | correctness-error | flawed | Real-time budget fails by nine to forty-eight times and ROI gating cannot fix it because the MTI stage runs full-frame | `measured latency; fpv/guidance/pipeline.py lines 293 and 296 to 297; latency_hwil.py lines 53 to 61` |
| critical | doc-code-mismatch | flawed | Hardware is a stock manual visible-light FPV quad with RX_MSP disabled; the assumed thermal, Pi, fork, kill-MCU and beacon stack is unbuilt | `hardware bill-of-materials xlsx; flashed FC config txt showing 4.4.3 and feature minus RX_MSP; PI_BRINGUP.md; geometry.py lines 127 to 145` |
| high | unverifiable-claim | unverifiable | Phase-C onboard abort authority, the stated prerequisite for autonomy beyond bench, is entirely unbuilt; safety is a tether | `PROJECT_COMPLETION_PLAN.md; BLOCK03_MASTER_PLAN.md section C; no fpv/safety/engage_fsm.py` |
| high | unverifiable-claim | unverifiable | TASK1 claims a 17 ms Pi baseline passing the 30 ms assumption, contradicted by a measured 36 ms p50 on faster Mac silicon | `TASK1_CAMPAIGN_COMPLETE.md; measured baseline latency` |
| medium | dead-code | mixed | About 35 files of RGB racing-gate and YOLO legacy remain co-mingled with the thermal work | `grep showing 35 files; fpv/fpv_ai/perception/yolo_offline.py; README.md` |
| medium | design-strength | correct | Architecture invariants are coherent in the spine but unhonorable as integrated; the honest gate pins a near-head-on-only envelope | `BLOCK03_MASTER_PLAN.md section 0; range_observer.py; imm.py line 269; test_s3_honest_acceptance.py lines 1 to 40` |

- **[CRITICAL] Kinetic authorization gate in README does not exist; verifier is the un-inverted ground anti-weapon blocklist and is not wired into arming** — README says the kinetic gate, requiring two Ed25519 signatures plus keypress plus ROE plus civcas, is cored on the safety verifier. In reality the verifier rejects any payload containing engage, intercept, kinetic, attack, or fire, which is the inverse of an arm gate; the reframe notes admit the inversion is an unfinished TODO; the arming module never imports the verifier; and verifier_passed is a bare trusted boolean with no signing or ROE behind it. The decide segment is documentation only.
  - *Рекомендация:* Invert the verifier to allow-on-authorization, implement real two-signature plus ROE plus civcas validation, design the missing engagement_handoff contract, and call it from the arming commit path fail-closed.
- **[CRITICAL] Real-time budget fails by nine to forty-eight times and ROI gating cannot fix it because the MTI stage runs full-frame** — Measured on a Mac faster than the target Pi5, baseline pipeline step p99 was 143.8 ms and p50 35.7 ms, with 95 percent of frames over the 16.7 ms budget; the full look-down stack p99 was 798.5 ms with all frames over. The latency harness never enables roi gating, and even when enabled the ROI crops only the detection call while the heavy motion mask is computed on the full frame, explicitly noted as full-frame MTI. So the ROI strategy cannot bring the stack under budget.
  - *Рекомендация:* Plumb the ROI into the MTI and directional-median stage, add a roi-gating flag to the latency harness, and re-profile on the actual Pi5; treat the latency claim as unmet until p99 under 16.6 ms is shown with ROI on MTI.
- **[CRITICAL] Hardware is a stock manual visible-light FPV quad with RX_MSP disabled; the assumed thermal, Pi, fork, kill-MCU and beacon stack is unbuilt** — Software assumes an FT640 thermal core, a Pi5, a forked Betaflight, an independent kill controller, and a permit beacon. The actual bill of materials lists a Caddx Ratel PRO 1500TVL visible-light analog camera, a SpeedyBee F405 stack, and an analog video transmitter, with no Pi, thermal core, kill controller or beacon. The flashed flight controller is stock Betaflight 4.4.3 with the MSP feature explicitly disabled, the opposite of the required fork. The bring-up guide introduces a third inconsistent camera identity, an analog CVBS thermal camera. The seeker has no sensor on the actual aircraft.
  - *Рекомендация:* Publish an as-built versus as-designed hardware delta, procure the assumed stack or rebaseline the software to existing hardware, and reconcile the three camera identities to one fielded sensor before any latency, Johnson-range, or NETD number can mean anything.
- **[HIGH] Phase-C onboard abort authority, the stated prerequisite for autonomy beyond bench, is entirely unbuilt; safety is a tether** — Both plans state that Phase C, comprising the acquire-confirm-commit-terminal-abort state machine, the commit gate, the self-safe state, the geo and altitude box, and the signed decision journal, is a hard prerequisite and confirm it is not built; failsafe and hwkill are tether-only. There is no engage state-machine module. Fire-and-forget autonomy has no realized decision or abort state machine, only a link-loss to disarm tether the program itself calls the wrong topology.
  - *Рекомендация:* Keep it gated; do not present fire-and-forget autonomy as achievable until C1 through C3 exist with full state-machine branch coverage and a logged refuse-to-fire.
- **[HIGH] TASK1 claims a 17 ms Pi baseline passing the 30 ms assumption, contradicted by a measured 36 ms p50 on faster Mac silicon** — The campaign record asserts a roughly 17 ms Pi baseline that passes the 30 ms assumption. The measured baseline on this Mac is p50 35.7 ms, mean 42.3 ms, p99 143.8 ms, over both the frame budget and the 30 ms assumption on hardware faster than a Pi5. The 17 ms figure is unsourced and not reproduced by the in-repo harness, and it is load-bearing for the latency gate and the sensor-delay assumption that back-propagates into every miss number.
  - *Рекомендация:* Re-run the harness on the actual Pi5 and publish the distribution; if it is not 17 ms, retract the claim and treat the 30 ms assumption as violated per the program own auto-invalidate rule.

**Переderived числа (✓ совпало / ✗ расхождение):**

- ✗ **Baseline per-frame latency versus the 16.7 ms budget**  
  - заявлено: About 17 ms, passing the 30 ms assumption
  - вывод: Measured on Mac: mean 42.3, p50 35.7, p99 143.8 ms, 95 percent over budget.
  - прим.: p50 of 36 ms exceeds both budgets on faster hardware; the 17 ms claim is unsourced.
- ✓ **Full look-down latency and the 388 ms claim**  
  - заявлено: About 388 ms, not real-time without ROI
  - вывод: Measured full stack on Mac: mean 463, p50 454, p99 798 ms, all over budget.
  - прим.: Directionally correct; ROI cannot fix it because MTI is full-frame.
- ✓ **FT640 focal length from 48.7 degree HFOV and 640 px width**  
  - заявлено: About 707 px, about 1.41 mrad per px
  - вывод: 320 divided by tan of 24.35 degrees equals 707.1 px; code reports 707.0756.
  - прим.: Exactly correct; the 1.33 mrad class label is about six percent optimistic.
- ✓ **Johnson detection budget for the FT640 optics**  
  - заявлено: Detect about 115 to 190 m, the 1.1 km figure struck
  - вывод: Not independently re-derivable without the NETD and atmospheric model.
  - прим.: Plausible paper budget, not measured; no radiometric or NETD calibration exists, correctly lab-blocked.
- ✓ **Clean-clone importability**  
  - заявлено: Runs with the fpv path on the import path
  - вывод: Project requires Python 3.11 but the system is 3.9.6; the seeker and guidance spine imports succeed; conftest injects the fpv directory.
  - прим.: No ImportError on the core spine; the verifier degrades to an HMAC dev fallback without pynacl, explicitly not for field use.

**Верификация (уверенность):** high — all six findings re-checked at their cited file:line and largely confirmed by reading executable code and re-running the latency harness and import/crypto probes. Findings [0],[2],[3],[4] are fully confirmed at every pointer. Finding [1] confirmed with machine-dependent absolute numbers (direction and full-frame-MTI mechanism verified). Finding [5] partially-confirmed (substance real, ~35-file count inflated by the overloaded 'gate' token). Finding [6] partially-confirmed (invariants and honest envelope verified; 'modified-polar IMM' is a non-standard label inherited from the plan — the code IMM is angle-only). Quant checks [0]/[1] re-run live (baseline and look-down both fail budget by ~3-37x); [2] re-derived exactly (f_px=707.0756, IFOV=1.414 mrad/px, 1.33 mrad label 6.0% optimistic); [3] correctly flagged as non-derivable paper budget; [4] refined — seeker/guidance spine imports OK but the fpv.safety package __init__ is broken (dangling 'cuas' import) and Ed25519 is fully unavailable, both missed by the analyst.

*Опровергнуто/преувеличено аналитиком (поймал верификатор):*
- Quant-check [4]: 'the seeker and guidance spine imports succeed ... conftest injects the fpv directory' is true for the seeker/guidance modules (imm, geometry, range_observer, pipeline all import cleanly under PYTHONPATH=fpv, verified), but the analyst OMITS that importing the fpv.safety PACKAGE fails on a clean clone: fpv/safety/__init__.py:5 does `from cuas.g2u.verifier import ...` and `cuas` is not vendored → ModuleNotFoundError. The verifier MODULE imports only because the system __init__ short-circuits; `from fpv.safety.verifier import ...` triggers the broken __init__ and fails. Not a fabrication, but an importability claim that is materially incomplete.
- Finding [5] file count: 'about 35 files match racing, yolo, or gate' overstates by counting the overloaded token 'gate'. Reproducible counts: 4 (filename), 19 (content racing|yolo), 41 (content incl. gate|lock). The '~35' lands only via the ambiguous 'gate'/'lock' string, which also matches legitimate SAFETY gate modules — so the headline number is inflated relative to the genuine RGB/YOLO legacy footprint.
- Finding [6] terminology: characterizing the IMM as a genuinely-honored 'modified-polar IMM' is imprecise — the code IMM state is [az,el,az_rate,el_rate] angle-only (imm.py:5,269) with inverse-range in a separate diagnostics observer; this is not the classical modified-polar (inverse-range-bearing) formulation. The analyst inherits the master plan's non-standard redefinition without flagging it.

*Пропущено аналитиком, добавил верификатор:*
- **[high] fpv.safety package is un-importable on a clean clone (dangling cuas dependency)** — The safety package cannot be loaded via its public __init__ on this repo; any consumer doing `from fpv.safety import verify_event` breaks. This both undercuts the 'safety core is real' framing and is a concrete clean-clone import failure the analyst's quant-check [4] missed (it only checked the seeker/guidance spine).  
  *(ev: fpv/safety/__init__.py:5 `from cuas.g2u.verifier import (FORBIDDEN_FIELD_VALUES, G2UVerifyError, canonical_payload, load_schema, publish_event, verify_envelope, verify_event, ...)`. The `cuas` package is not present in 03-fpv: `import fpv.safety` and `from fpv.safety.verifier import ...` both raise ModuleNotFoundError: No module named 'cuas' (reproduced under PYTHONPATH=fpv). The verifier.py module body is self-contained and a re-implementation lives in 03-fpv, so the __init__ points at a stale ground-system path.)*
- **[medium] Ed25519 signing is entirely unavailable in this environment, not merely degraded** — The analyst's note that the verifier 'degrades to an HMAC dev fallback without pynacl' understates the gap: with neither crypto lib installed, the signed-authorization chain the README's kinetic gate depends on is not exercisable even in principle here. Combined with finding [0] (verifier not wired into arming) and the missed __init__ break, the entire signed-auth story is currently non-functional, not just dev-mode.  
  *(ev: Both `nacl` (PyNaCl) and `cryptography` are ABSENT (verified import probes). verifier.py:231-247 sign_envelope tries PyNaCl then cryptography and, with neither, RAISES G2UVerifyError('Ed25519 signing requires PyNaCl or cryptography; use hmac: key_id for dev only'). So on this machine the 'production MUST use Ed25519' path cannot run at all — only the HMAC dev fallback works.)*
- **[medium] ROI gating, even when enabled in the pipeline, is bit-identical-by-default and only narrows detection — the latency story has no ROI-enabled measurement at all** — Strengthens finding [1]: the ROI optimization is not just insufficient (MTI full-frame) — it is entirely unmeasured by the repo's own latency harness, so any claim that ROI recovers real-time budget is unsupported by data, not merely physically blocked.  
  *(ev: pipeline.py:89 roi_gating defaults False; :130-135 'default-OFF -> roi=None -> bit-identical'; :206 _detect_roi returns None unless roi_gating AND tracker holds a lock; :254/268 ROI feeds ONLY the detect call; :293 MTI is full-frame regardless. latency_hwil.py exposes NO roi flag, so NO in-repo benchmark ever measures the ROI-on path. There is therefore zero measured evidence that ROI helps even the detection stage, let alone the stack.)*
- **[medium] allow_synthetic_bench default and the synthetic flag are the only thing separating bench from a live-arm path; verifier_passed is operator-trusted with no provenance** — The arming state machine's safety rests entirely on the CALLER honestly setting verifier_passed/synthetic and on no caller flipping allow_synthetic_bench=True. There is no enforced binding to the (un-inverted, un-wired) verifier. This is the integration gap behind finding [0], made concrete at the arming-machine boundary.  
  *(ev: arming.py:76 synthetic:bool=True with comment 'live engagement REQUIRES synthetic=False'; :116 ArmingConfig.allow_synthetic_bench=False. authorized():89 blocks synthetic auths unless allow_synthetic_bench. But verifier_passed (:70) is a plain caller-supplied bool — nothing in the module validates a signature, schema, ROE, or civcas; the docstring's 'verifier-passed' (line 21) is aspirational. The 'committed' check (:93-103) only validates keypress-timestamp-in-window, not any cryptographic authorization.)*
- **[medium] Honest-acceptance sensor_delay_s=0.030 is hardcoded as the measurement assumption that the latency harness contradicts** — Directly couples findings [1]/[4] to finding [6]: every honest miss number is conditioned on a 30 ms delay the system does not meet, so even the 'REAL favorable-case capability' (head-on ~0.033 m) is over-credited because the sensor-delay input is below measured compute latency.  
  *(ev: test_s3_honest_acceptance.py:52 sensor_delay_s=0.030 default and :141 SimConfig(sensor_delay_s=0.030); the miss-distance envelope (head-on ~0.033 m, quartering collapse) is computed against a 30 ms sensor delay. The latency harness measures p50 35-57 ms / p99 105-620 ms on faster-than-Pi silicon, i.e. the real per-frame delay back-propagated into the sim is optimistic by 2-20x.)*

*Вердикты «опровергнуто/частично»:*
- [partially-confirmed] [5] ~35 files of RGB racing-gate/YOLO legacy co-mingled with thermal work — Substance is real (RGB racing-gate + YOLO-against-absent-model legacy is present and the lock engine targets racing gates), but the '~35 files' headline is loose/over-counted; honest range is ~19 (racing|yolo) to ~41 (incl. ambiguous 'gate'/'lock').
- [partially-confirmed] [6] Architecture invariants coherent in the spine but unhonorable as integrated; honest gate pins near-head-on-only envelope — Confirmed that the analyst faithfully reports the plan's invariants and the honest-test envelope. Caveat the analyst missed/blurred: calling the IMM 'modified-polar' follows the plan's own non-standard redefinition; the code IMM is angle-only, not classic MPC. The completeness-not-doctrine framing is sound.


---
