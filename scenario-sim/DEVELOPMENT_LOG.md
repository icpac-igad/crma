# Scenario Mode — Development Log

Chronological list of changes, so future work on the scenario-simulation routine
has a single reference. Newest at the bottom. Each entry: **what / why / files /
commit(s) / deploy**.

Repos & branches:
- **Frontend** `arco-ibf` (branch `cmra-web`) — the app + scenario UI.
- **Backend** `cno-e4drr` (branch `main`) — `devops/crma-api-cr/app.py` (FastAPI).
- **Design** `cmra` / `scenario-sim` (branch `main`) — plans, scenario JSON scripts, docs.

Live URLs: frontend `https://crma-frontend-yiyrp6yumq-uc.a.run.app/scenario` ·
API `crma-api` (private Cloud Run, reached via the frontend's identity-token proxy).

Deploy commands: frontend `cno-e4drr/devops/crma-fe-cr/ → bash _build_fe.sh`;
API `cno-e4drr/devops/crma-api-cr/ → bash _build_api.sh` (both rsync the working
tree → Cloud Build → Cloud Run; FE is frontend-only, API needs an API rebuild).

---

## Foundation (prior session)

0. **Initial Scenario Mode** — dedicated `/scenario` + `/scenario/[eventId]` route,
   scenario JSON schema (`app/types/scenario.ts`), `ScenarioRunner`, launcher in the
   Risk-Decisions stage, `PipelineProvider` gains `syncUrl` so the store can be
   driven without navigating to `/`. Reuses `DisasterMap`/`BoundaryDagPanel(Drought)`.
   - `arco-ibf` `837414f` · design `cmra` `830fd29`.

---

## Current session

1. **note1 realignment → evidence/CRMA-centric.**
   - Evidence cards **bind to the live BN-DAG** at the cursor (`raw`/`state` via
     `/api/{bn-dag,drought-bn-dag}`; `bn_node → ant/exc/spa/trn/tail` flood,
     `cur/def/spa/trn` drought); `[live BN]` vs `[scripted]` fallback offline.
   - Surface engine CRMA state + posterior + `P(High+Extreme)` as a **risk advisory**.
   - Move hazard footprint from a decision-time tab → **debrief** (optional).
   - Drop **competitive scoring/leaderboard**; keep formative quiz prompts.
   - Files: `ScenarioRunner.tsx`, `types/scenario.ts`, scenarios, `SCENARIO_MODE.md`.
   - `arco-ibf` `61fffd2` · design `81579ee`.

2. **Drought-first: RM rounds → RK debrief, no hazard in the flow.**
   - Debrief opens the **Risk-Knowledge EM-DAT storyline** via the exact deep link
     from `DevOps-hazard-modeling/README.md` (`hazard + debrief.rk_month +
     emdat_event_key`). Added `debrief.rk_month`.
   - `layers.hazard` made **optional**; drought scenarios omit it → zero external
     runtime dependency.
   - Product phasing: **P1 drought → P2 flood → P3 drought+hazard/impact →
     P4 flood+hazard/impact**.
   - `arco-ibf` `704bfd9` · design `7d08151`.

3. **Complete drought Phase 1 — all 11 events.**
   - Generated the 9 remaining drought scenarios from the template (3 rounds:
     outlook → deficit+CDI → confirmation); registered all 11 drought + 1 flood.
   - `arco-ibf` `3c42cf4` · design `240728e`.

4. **Country-focus choropleth + EM-DAT-derived round windows.**
   - `DisasterMap` gains `focusCountry` → fits the d3 projection to one country's
     admin-1s (small countries fill the frame); all polygons still drawn as context.
   - Round cursors anchored to real **EM-DAT `Start`/`End`** (`emdat_drought_adm1.parquet`):
     **T-6 months (lead) → onset → peak/duration**.
   - Fixed latent `DisasterMap` optional-`selectedMonth` type.
   - `arco-ibf` `6e78ff4` · design `9d39c9e`.

5. **Docs:** `docs/SCENARIO_MODE_UPDATES.md` (country-focus generation, EM-DAT
   windows, deploy). `arco-ibf` `4dc42aa`.
   - **▶ Deploy #1 (frontend):** Cloud Build `4419b850` — drought Phase 1 goes live.

6. **Event-scoped calendar beside the choropleth.**
   - Add `DisasterCalendar` to the scenario visuals: **monthly for drought, daily
     for flood**; `startYear/endYear` bracket the round cursors (focus on the event
     window); store-driven so it colours RM cells and highlights the active cursor.
   - `arco-ibf` `0e2b100`.
   - **▶ Deploy #2:** Cloud Build `24598ea1` + push.

7. **Calendar country filter — v1 (client-side aggregation).**
   - `DisasterCalendar` gains `focusCountry`: the cell count was an EA-wide aggregate
     (over all 227 admin-1); re-aggregate to the country by fetching per-period
     regions across the window and counting that country's admin-1s. (Cost: one
     regions fetch per period.)
   - `arco-ibf` `467acf1`.
   - **▶ Deploy #3:** Cloud Build `6be7854e` + push.

8. **Calendar country filter — v2 (backend endpoint, efficient).**
   - **API:** `/api/ibf-drought-calendar` and `/api/ibf-flood-calendar` gain an
     optional `?country=<GID prefix>` → counts aggregated **server-side** by grouping
     the boundary parquet (one groupby, one response). Omitting it = EA-wide as before.
   - **Frontend:** route handlers forward `?country=`; `fetchIbf{Flood,Drought}Calendar`
     take an optional country; `DisasterCalendar` does **one fetch** instead of N.
   - Files: `crma-api-cr/app.py`; `route.ts` (both calendars); `lib/api/emdat.ts`;
     `DisasterCalendar.tsx`.
   - **API** `cno-e4drr` `acbdae7` · **frontend** `arco-ibf` `e0ce021`.
   - **▶ Deploy:** API Cloud Build `f1e30ff2`; frontend Cloud Build `2baaa4fb`.
   - Verified in prod: KEN `2020-12` = 37/5/3/**2** (47 admin-1) vs EA-wide
     146/40/26/**15** (227); one request returns all 528 months.

9. **Flood RM calendar extended to 2019.**
   - Flood daily BN data already covered the 2019+ event windows (years
     2019/2021/2023/2024/2026; first `2019-05-10`), but the flood `risk-monitoring`
     calendar config started at **2022**, clipping the 2019/2021 events. Set
     `startYear` to **2019** so flood RM aligns with the RK flood storylines (2019+).
     Frontend-only, no data/API change.
   - File: `app/types/pipeline.ts`. `arco-ibf` `39b6fad`.
   - **▶ Deploy:** Cloud Build `ccdde4ec`.

10. **Flood Phase 2 — 10 events + hazard toggle (flood default).**
    - Flood RM daily BN covers the 2019+ event windows, so built flood scenarios for
      **all 11 GHACOF flood events** (Uganda/Eritrea/S.Sudan/Djibouti 2019, Ethiopia
      2021, Rwanda/Somalia 2023, Burundi/Kenya/Tanzania 2024, **Sudan Khartoum 2019**
      on the shared Aug-2019 window `sdn_2019_08`) on the flood template: **daily
      rounds** (lead → escalation → onset) anchored to each event's window; evidence
      binds to the live flood BN-DAG. Kept Nairobi 2026 → **12 flood scenarios**.
      (Eritrea and Sudan share the Aug-2019 window; each scenario focuses its own
      country via `gid_1`.)
    - Scenario index gains a **hazard filter** (Flood / Drought / All), **flood
      default** — 22 events otherwise cluttered the list (`ScenarioBrowser.tsx`, client).
    - Files: `app/content/scenarios/*flood*.json`, `registry.ts`,
      `ScenarioBrowser.tsx`, `page.tsx`. `arco-ibf` `947de3b` · design `9a9bb8c`.
    - **▶ Deploy:** frontend (Cloud Build id in deploy log).

11. **Act I quiz — three-act reorientation (quiz/ design → code).**
    - The scenario flow is reframed into the **three acts** from
      `cmra/quiz/quiz_reorient_three_Acts.md`: Act I *what is happening?* →
      Act II *what do we think is happening?* → Act III *what should we do and why?*
    - **Act I** adds the **evidence-elicitation quiz** (`cmra/quiz/quiz_templates.md`):
      one generic 9-question template for **all 23 events** (flood/drought option
      wording only, no per-event authoring) — strongest evidence → hard/soft/virtual →
      reliability → hazard condition → impact pathway → next evidence →
      **pre-BN risk estimate (Q7) + DOC status (Q8)** → model-trust seed
      (`3act-refinement3.md`). Each question surfaces its **BN purpose** so answers
      read as inputs to the machinery, not a knowledge test. Quiz completion shows
      the "Your answers generated:" evidence inventory and gates Act II.
    - BN DAG panels + risk advisory **hidden in Act I** so Q7/Q8 are committed
      before any model output (quiz commits before BN, per the template).
    - **Act III debrief** opens with the **your-estimate vs engine-indication**
      comparison (Q7/Q8 vs `risk.state`/`crma.state` at the final cursor) + the
      model-criticism reflection ("expert rules made consistent — a risk indication,
      not a calibrated probability"). Formative, unscored (Tier 0 of
      `3act-refinement2.md` — no LLM).
    - Answers persist per event: `localStorage` `scenario:<id>:act1`.
    - Files: `app/lib/scenario/quiz.ts` (new), `ScenarioRunner.tsx`,
      `docs/SCENARIO_MODE.md`. `arco-ibf` `35fee97`.

12. **Act I quiz realigned to each event — EPS literacy + per-event `act1_quiz`.**
    - Template **binds to the event**: hints list the scenario's own round-1
      evidence cards, admin-1, and its forecast system (ECMWF ensemble flood /
      SEAS5 25-member drought) — event-specific feel, zero per-event authoring.
    - Two **forecast-literacy** questions open the quiz for general participants:
      *what is a deterministic forecast?* / *what is an ensemble prediction system?*
      — plain-language teaching notes revealed after answering, tying the ensemble
      spread to why forecasts are **soft** evidence (and mean-vs-tail).
    - New optional scenario-JSON field **`act1_quiz`** (`ScenarioQuizQuestion` in
      `types/scenario.ts`): event-specific questions inserted before the pre-BN
      Q7/Q8 commit. **All 23 scenarios** carry 2 each, authored from the
      **outcome-free** sections of their RK storyline MDX
      (`app/content/events/rk/{fl,dr}-rk-<DisNo>.mdx`, the GHACOF73 deep-link set
      in `DevOps-hazard-modeling/README.md`): climate drivers (ENSO/IOD state),
      seasonal calendar, geography, exposure — impacts/response excluded so the
      outcome stays hidden until Act III.
    - Validation: 23/23 JSONs parse; 46 questions well-formed (`correct` ∈
      options); spoiler word-sweep clean; tsc + prod build + route smoke pass.
    - Files: `quiz.ts`, `ScenarioRunner.tsx`, `types/scenario.ts`, all 23 scenario
      JSONs, `docs/SCENARIO_MODE.md`. `arco-ibf` `e6c2546`.
    - **▶ Deploy (entries 11+12):** Cloud Build `9cdc834d` — SUCCESS, 5m11s;
      verified live (`/scenario/kenya_nairobi_flood_2024` serves the Act I
      banner, EPS literacy questions, and the event-specific `act1_quiz`).

13. **Event-specific hint on every Act I question.**
    - Stock-take of the 13 questions/event: only q1/q2/q5 carried hints (round-1
      cards, brief) and q0a/q0b carried explanations; q3/q4/q6 and the q7/q8/q9
      pre-BN commit rendered **bare**. Now **every** template + commit question
      carries an event-specific hint, derived from the scenario's own data — no
      per-event authoring: q3/q7 from `signalNote()` (forecastability
      strong/tail/surprise); q4 hazard-mechanism nudge (river/flash/urban for
      flood, met/agri/hydro for drought); q5 brief + admin1 fallback; q6 from
      `laterCardList()` (the not-yet-revealed "hidden" cards); q8 reuses the
      authored `decision.checkpoint_prompt`; q9 conceptual → Act III payoff.
    - Count unchanged (13/event); all-answered gate to Act II unchanged.
    - File: `quiz.ts`. `arco-ibf` `1748bd2`.
    - **▶ Deploy:** Cloud Build `886f6bae` — SUCCESS, 4m51s; verified live (hints
      render and vary by event — flood "TAIL-risk case" vs drought "STRONG-signal").

14. **Precise event-date window + window-gated calendar.**
    - **Specific dates, not `YYYY–YYYY`**: the event window is derived from the
      round cursors (drought `YYYY-MM`, flood `YYYY-MM-DD`) and shown as an
      "Event window: start → end (unit)" line in the runner; the calendar header
      now reads the precise window instead of the year span.
    - **Only this event's dates enabled**: `DisasterCalendar` gains optional
      `windowStart`/`windowEnd` — cells outside `[start,end]` render muted
      (`#f3f4f6`, 0.4 opacity), non-clickable, no count label (kept as ambient
      context). In-window cells unchanged. `inWindow()` = lexicographic ISO
      compare at the cell granularity (YYYY-MM monthly, YYYY-MM-DD daily).
    - **Non-breaking**: both props optional; only the scenario runner passes them.
      The dashboard `DisasterCalendar` (DashboardShell) is untouched.
    - Files: `DisasterCalendar.tsx`, `ScenarioRunner.tsx`. `arco-ibf` `fb705d5`.
    - **▶ Deploy:** Cloud Build `43b180d8` — SUCCESS, 5m27s; verified live
      (flood `2024-04-09 → 2024-04-23 (daily)`; drought `2022-01 → 2022-12 (monthly)`).

15. **Fix: Act II round 2 crash on flood scenarios.**
    - Flood virtual-evidence card `dbn_carry` (`R_obs`) carries no `value_by_date`
      (the live BN supplies the value). It is revealed in **round 2**, where the
      evidence stream's `authoredValue` called `Object.keys(card.value_by_date)` on
      `undefined` → "Cannot convert undefined or null to object" → **client-side
      exception on every flood scenario at Act II round 2**. Guard the undefined +
      mark `value_by_date` optional in the type. Drought cards all have it → drought
      was unaffected (the three-act refactor in 11–14 didn't introduce it; it was
      latent in the flood path from the start).
    - Files: `ScenarioRunner.tsx` (`authoredValue`), `types/scenario.ts`.
      `arco-ibf` `a7501f9`.
    - **▶ Deploy:** frontend (Cloud Build id in deploy log).

16. **FE→API auth fix — `&format=full` made Cloud Run reject the identity token.**
    - A Locust load test (`cmra/load-test/`) of the act1→act3 flow surfaced that
      **66% of requests were failing — functionally, not from load** (capacity
      passed at 50 users: 5,711 reqs, p95 120 ms, zero 429/503). Root-caused to a
      single defect: `apiFetch` requested its identity token from the metadata
      server with **`&format=full`**, and Cloud Run service-to-service auth
      **rejects full-format tokens** ("the access token could not be verified" →
      401). Every live API call 401'd; routes doing `res.json()`
      (regions / bn-dag / drought-calendar) turned the 401-HTML into a **500**,
      MDX raw/media passed the **401** through, and a few Next-cached 200s
      (flood-calendar, bn-dag) masked it. Proven via direct API calls (all 200 with
      a *standard* token) + API `httpRequest` logs (401, 0 s) — no API-side bug.
    - **Fix** (`arco-ibf/app/lib/api-fetch.ts`): drop `&format=full` → standard
      token; **fail loud** (no token → clear `502` JSON instead of a silent
      unauthenticated request that became a misleading 500); **`cache: 'no-store'`**
      on proxied calls so a stale 200 / pinned error can't mask live state (also
      forces every proxy route to render dynamically).
    - The live image had been **stale** relative to the committed
      route-handler/`apiFetch` work — the same "tokenless proxy → 403/500" class
      the deploy docs flagged; a rebuild from current source + this fix resolves it.
    - Also fixed the load harness: the drought profile used a non-existent slug
      `kenya_drought_2022` (a correct 404) → real slug **`kenya_asal_drought_2020`**
      with its actual cursors (`cmra/load-test/scenarios.py`).
    - `arco-ibf` `6fb07d8` (branch `cmra-web`, push pending).
    - **▶ Deploy:** frontend Cloud Build `2fbfc145` — SUCCESS, 4m41s; verified
      live: all IBF region/calendar, both BN-DAG paths, MDX raw, and the drought
      scenario page now return **200**. (The Cloud Build deploy reset scaling to
      the `cloudbuild.yaml` baseline `min=0 / max=2`.)

---

## Current live state

- **Phases 1 & 2 complete and deployed**: **11 drought** (monthly) + **12 flood**
  (daily) scenarios; `/scenario` index has a hazard filter (Flood / Drought / All,
  **flood default**). Three-act flow (Act I evidence quiz → Act II belief updating →
  Act III decision & debrief).
- Each scenario: event-scoped calendar (window-gated) **+** country-zoomed choropleth
  **+** per-boundary BN DAG, all following the round cursor; evidence bound to the
  live BN-DAG; advisory from the engine; debrief = RK loss & damage deep link.
- **Country filtering** is server-side on both calendar and choropleth.
- No external runtime dependency (hazard assets out of the flow).

### Outstanding
- **`cno-e4drr` push pending**: commit `acbdae7` is local only; `origin` is an SSH
  URL (`git@github.com:nishadhka/cno-e4drr.git`) and SSH auth isn't available in this
  environment. Push it from a machine with SSH access (the deployed API already runs
  this code — push is for version control only).
- Event **briefs/counterfactuals are drafts** pending SME review.
- `gid_1` is one representative admin-1 per event (some GHACOF names diverge from
  EM-DAT's recorded admin-1s — kept on the named region).

---

## Where to extend next (for future development)

- **Phase 3/4 — hazard/impact**: add wflow WRSI + CLIMADA (drought) and RIM2D +
  CLIMADA (flood) as supporting science / debrief context, not decision inputs.
- **New flood events / dates**: need a `flood_data_prep` → Julia BN run for their
  dates (the 11 GHACOF windows 2019–2024 + Nairobi 2026 are already in).
- **Satellite-rainfall debrief animation** (IMERG/CHIRPS/CMORPH) — new asset; the
  current GIFs are model outputs, not raw rainfall.
- **Hindsight toggle** (`mode_defaults.hindsight`) — schema field, not yet a UI toggle.
- **Server-side session/leaderboard** — decisions are in `localStorage` only.
- **Flood calendar month-clamp** — calendar granularity is years; flood shows the
  whole event year daily. A month-range prop on `DisasterCalendar` would tighten it.

### Key files (scenario routine)
```
arco-ibf/app/scenario/[eventId]/ScenarioRunner.tsx   orchestration: rounds, cursor,
                                                     evidence binding, advisory, debrief
arco-ibf/app/content/scenarios/*.json                the scenario scripts (game data)
arco-ibf/app/types/scenario.ts                       schema
arco-ibf/app/lib/scenario/registry.ts                register a new scenario here
arco-ibf/app/components/dashboard/DisasterMap.tsx        focusCountry (projection zoom)
arco-ibf/app/components/dashboard/DisasterCalendar.tsx   focusCountry (server counts)
cno-e4drr/devops/crma-api-cr/app.py                  per-country calendar endpoints
arco-ibf/docs/SCENARIO_MODE.md  + SCENARIO_MODE_UPDATES.md   developer docs
```
