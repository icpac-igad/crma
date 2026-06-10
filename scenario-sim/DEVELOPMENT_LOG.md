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

---

## Current live state

- **Drought Phase 1 complete and deployed**: 11 drought scenarios + 1 flood seed.
- Each scenario: event-scoped calendar (monthly) **+** country-zoomed choropleth
  **+** per-boundary BN DAG, all following the round cursor; evidence bound to the
  live BN-DAG; advisory from the engine; debrief = RK loss & damage deep link.
- **Country filtering** is server-side on both calendar and choropleth.
- No external runtime dependency (hazard assets are out of the drought flow).

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

- **Phase 2 — Flood**: only `nairobi_flood_2026` has a daily BN replay. Other flood
  events need a `flood_data_prep` → Julia BN run first (verify ECMWF reforecast back
  to 2019). Then author flood scenarios on the same schema (daily cursors).
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
