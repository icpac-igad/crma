# CRMA Scenario Simulation — MVP Implementation Plan

*From Forecast to Action* (see [`published_ss.md`](published_ss.md)) realised as a thin
**Scenario Mode** wrapper over the existing CRMA app, not a new application.

This plan consolidates the design dialogue. It supersedes the open-ended options in
[`scenario-sim-plan.md`](scenario-sim-plan.md) (kept for reference).

---

## 1. Core decision: wrapper, not new app

The deployed CRMA app (`arco-ibf`, branch `cmra-web`) already has three pipeline
stages: `risk-knowledge`, `risk-monitoring`, and a **stubbed `risk-decisions`**.
**The simulation *is* the `risk-decisions` stage.** Everything else is reuse:

| Sim need | Reused CRMA piece | New? |
|---|---|---|
| Calendar + choropleth | `DisasterCalendar`, `DisasterMap` | — |
| Situation brief / loss & damage | `risk-knowledge` EM-DAT MDX (`/api/emdat-event-markdown/{key}`) | — |
| Evidence room + BN panel | `risk-monitoring` parquet + `BNDag` / `BNDagDrought` (real `bn-dag/*.json`) | gate by round |
| Hazard model tab | RIM2D / wflow GIF-PNG (HuggingFace, hotlinked) | embed only |
| Impact tab | EM-DAT recorded loss at debrief (CLIMADA deferred) | Phase 3 |
| **Quiz + decision log + score** | — | **the only real new code** |

The "game engine" is **data**: one scenario JSON per event + a `ScenarioController`
that steps a date cursor and gates reveals. No new BN math — the engine already
produces a time-evolving posterior (flood daily, drought monthly + DBN), so
"replay as if unfolding today" is just stepping the calendar through artifacts that
already exist in `gs://crma-mdx-store`.

---

## 2. Locked decisions (this MVP)

| Decision | Choice | Consequence |
|---|---|---|
| Event set | **Nairobi flood + 2 droughts** | all layers ready, no date conflicts |
| Hazard assets | **Hotlink HuggingFace** | zero copy; external runtime dep; wflow is CC-BY-NC |
| Impact / CLIMADA | **Deferred to Phase 3** | impact = recorded EM-DAT loss at debrief |
| Session state | **browser localStorage** | single-player / per-station; no API change for MVP |

### The MVP trio (fully aligned across all three layers)

| Event | Hazard sim (hotlink) | BN replay | Loss narrative | Forecastability |
|---|---|---|---|---|
| **Nairobi flood 2026** | RIM2D `preview.gif` | flood **daily** Mar 1–15 2026 | 2026 Kenya floods (≥108 deaths) | **tail** (mean benign, tail fires 2-day lead) |
| **Kenya ASAL drought 2020–23** | wflow `ken_wrsi.png` | drought **monthly**, init `2020-12` | EM-DAT `2020-9609-KEN` | **strong** (multi-season deficit) |
| **Uganda Karamoja drought 2022** | wflow `uga_wrsi.png` | drought **monthly**, init `2022-07` | EM-DAT `2022-9436-UGA` | **strong** |

Lead onboarding with a **drought** (strong, slow signal → confidence-building); use
**Nairobi** for the advanced "the mean lies, read the tail" lesson.

#### Asset URLs (HuggingFace `resolve`)

```
flood  Nairobi : https://huggingface.co/datasets/E4DRR/rim2d-simulations/resolve/main/nairobi_2026-03-06/preview.gif
drought Kenya  : https://huggingface.co/datasets/E4DRR/wflow.jl-simulations/resolve/main/v4_wrsi_plots/ken_wrsi.png
drought Uganda : https://huggingface.co/datasets/E4DRR/wflow.jl-simulations/resolve/main/v4_wrsi_plots/uga_wrsi.png
```

> **Note** — both datasets are **hazard** outputs (inundation extent / water-stress
> index), *not* impact. The Hazard tab carries a `validation: illustrative` badge:
> these footprints have minimal validation and must never drive the alert level. The
> BN posterior + cost-loss rule is the decision signal; the hazard GIF shows "what the
> footprint looks like," EM-DAT shows "what actually happened."

---

## 3. Two design principles that prevent the exercise from backfiring

### 3a. Hide the outcome during the decision; reveal loss & damage at debrief

The abstract's "working backward from loss and damage" is the **debrief logic**, not
the participant's real-time information state. Showing the full EM-DAT narrative up
front anchors everyone and removes the decision tension.

- **Forward rounds** → minimal, **outcome-free** brief (region, season, what's normal,
  who's exposed).
- **Debrief** → full EM-DAT loss MDX **+ the quiz on it**, reframed as forensic
  reconstruction: *"which signals you saw actually preceded this?"*

Encoded as `hindsight: "off"` (60-min workshop, decide blind) vs `"on"` (5-min
onboarding speed-run, teach the chain forensically).

### 3b. Weak/ambiguous evidence is the lesson, not a flaw — if scored on reasoning

Real forecasts often do **not** cleanly point at the imminent event (Nairobi: ensemble
mean ~18 mm "benign," worst member 131 mm, tail crosses threshold). That is the exact
operational condition CRMA's `tail_risk` + soft evidence + storylines exist for. To
keep this from breeding pessimism/confusion:

1. **Score reasoning, not prediction.** "Monitor, but flag the tail + request 24 h
   re-check" scores high even without escalation.
2. **"Insufficient evidence / no-regret action" is a valid, scored answer** —
   `require_uncertainty_note: true`, `allow_no_regret: true`.
3. **Curate by forecastability** (`strong` droughts for onboarding; `tail` flood for the
   hard lesson; optional `surprise` for humility).
4. **Counterfactual = empowerment.** After the forward decision, inject *"what if we had
   acted at T-N"* as **virtual evidence** and show the loss-reduction logic — the same
   Pearl/CDI/DBN operation the engine already uses, and literally the abstract's
   "earlier interventions could reduce loss and damage."

Framing line shown to participants up front:
> *This is not a test of whether you can predict the disaster. Real forecasts are
> uncertain. It is a test of whether you can read the evidence, weigh the uncertainty,
> and make a defensible operational decision — including, when warranted, deciding* not
> *to act, with your reasons.*

---

## 4. Evidence-type taxonomy ↔ the real engine

The hard/soft/virtual quiz maps onto how the BN actually injects evidence — teach it
the engine's way, not the gauge/forecast cartoon:

| Quiz type | In CRMA | Teaching point |
|---|---|---|
| **Hard** | v1 only; **retired in v2** (even observations soft-binned) | "observations carry measurement uncertainty too" |
| **Soft** | the backbone — Gaussian-CDF binning → prob vector on every parent (`ant_p*`, `exc_p*`, `cur_p*`, `def_p*`…) via Pearl identity-CPT channel | "this is what CRMA *is*" |
| **Virtual** | drought **CDI** (14×5 noisy-likelihood, applied after posterior) + flood **DBN** coupling (`R_obs`, α=0.6) + per-member storylines | "a what-if/counterfactual *is* virtual evidence" |

---

## 5. Scenario JSON schema (the "game engine" is this data)

One file per event under `scenarios/`. Annotated reference; see
[`scenarios/nairobi_flood_2026.json`](scenarios/nairobi_flood_2026.json) for a worked
instance.

```jsonc
{
  "event_id": "nairobi_flood_2026",
  "hazard": "flood",                       // flood | drought
  "country": "Kenya",
  "admin1": "Nairobi",
  "gid_1": "KEN.30_1",                     // confirm vs icpac_adm1v3.json; keys the bn-dag JSON
  "emdat_event_key": "2024-0247-KEN",      // RK MDX key for the loss narrative (debrief)
  "forecastability": "tail",               // strong | tail | surprise  → drives debrief framing
  "mode_defaults": { "hindsight": "off", "duration_min": 60 },

  "layers": {                              // which existing endpoints/assets this event uses
    "risk_monitoring": {
      "key_field": "date",                 // flood=date (YYYY-MM-DD), drought=init (YYYY-MM)
      "calendar": "/api/ibf-flood-calendar",
      "regions":  "/api/ibf-flood-regions/{date}",
      "dag":      "/api/bn-dag/{date}"
    },
    "hazard": {
      "type": "rim2d",                     // rim2d | wflow_wrsi
      "asset_url": "https://huggingface.co/datasets/E4DRR/rim2d-simulations/resolve/main/nairobi_2026-03-06/preview.gif",
      "caption": "RIM2D inundation footprint, Nairobi 6 Mar 2026",
      "validation": "illustrative"
    }
  },

  "peak": { "date": "2026-03-06", "hidden_until": "debrief" },
  "simulation_start": { "cursor_date": "2026-03-01", "offset_label": "T-5 days" },

  "rounds": [
    {
      "round": 1, "title": "Early monitoring", "cursor_date": "2026-03-01",
      "reveal_evidence": ["antecedent", "exceedance"], "checkpoint": false
    },
    {
      "round": 2, "title": "Forecast escalation", "cursor_date": "2026-03-04",
      "reveal_evidence": ["tail_risk", "spatial", "dbn_carry"], "checkpoint": true,
      "quiz": ["classify_tail_risk", "interpret_mean_vs_tail", "doc_action_at_T2"]
    },
    {
      "round": 3, "title": "Observed confirmation", "cursor_date": "2026-03-06",
      "reveal_evidence": ["observed_onset"], "checkpoint": true
    }
  ],

  "evidence_cards": [
    {
      "id": "antecedent", "label": "7-day antecedent rainfall (IMERG)",
      "bn_node": "antecedent_rainfall", "evidence_type": "soft",
      "value_by_date": { "2026-03-01": "135 mm → Saturated" }
    },
    {
      "id": "tail_risk", "label": "Ensemble-max / 2-yr RP (p95 pixel)",
      "bn_node": "tail_risk", "evidence_type": "soft",
      "value_by_date": { "2026-03-04": "ratio 1.11 → tail crosses threshold" },
      "teaching_note": "Ensemble MEAN is benign here; only the tail fires. This is the signal."
    },
    {
      "id": "dbn_carry", "label": "Yesterday's posterior carried forward (DBN α=0.6)",
      "bn_node": "R_obs", "evidence_type": "virtual"
    }
  ],

  "decision": {
    "ladder": ["Monitor", "Watch", "Warning", "Emergency Coordination"],
    "crma_mapping": {
      "Monitor": "Monitor", "Watch": "Evaluate",
      "Warning": "Assess", "Emergency Coordination": "Actionable_Risk"
    },
    "require_uncertainty_note": true,
    "allow_no_regret": true
  },

  "counterfactual": {
    "prompt": "What if a precautionary no-regret action were taken at T-2 (Mar 4)?",
    "virtual_evidence_node": "R_obs",
    "narrative": "Even under a benign mean, acting on the tail signal at 2-day lead..."
  },

  "debrief": {
    "loss_markdown": "/api/emdat-event-markdown/2024-0247-KEN",
    "reconstruction_quiz": ["which_signal_preceded", "weight_you_got_wrong"]
  },

  "scoring": {
    "evidence_classification": 20, "evidence_to_bn": 20,
    "uncertainty_reasoning": 20, "doc_operational_logic": 25, "justification": 15
  }
}
```

---

## 6. The 60-minute flow → real stages/endpoints

| Min | Round | Stage / endpoint | Revealed | Engine truth |
|---|---|---|---|---|
| 0–5 | Select | `risk-knowledge` calendar | pick event | — |
| 5–15 | Brief + roles | EM-DAT MDX (**outcome-free** for `hindsight:off`) | region, season, exposure | — |
| 15–30 | T-N early signal | `risk-monitoring` at cursor−N | soft evidence (deficit / antecedent) | real `def_p*` / `ant_p*` |
| 30–45 | Escalation + BN inject | `bn-dag/{date|init}` | parents fire → posterior shifts; CDI/DBN = virtual | real DAG JSON evolution |
| 45–55 | DOC decision | `risk-decisions` (new) | traffic light + hazard GIF overlay | real `crma_state` |
| 55–60 | Debrief + score | reveal EM-DAT loss vs decisions; counterfactual | forensic reconstruction | hindcast comparison |

DOC ladder **Monitor → Watch → Warning → Emergency** maps 1:1 onto the engine's
**Monitor → Evaluate → Assess → Actionable_Risk** (keep engine names as source of truth).

---

## 7. Build surface & phasing

**New code (`arco-ibf`, `stage=risk-decisions`):** `ScenarioController.tsx` (date cursor +
round gating), `EvidenceQuiz.tsx`, `DecisionLog.tsx`, `HazardTab.tsx` (hotlink embed),
`scenarios/*.json`. State in `localStorage`. **Rebuild: frontend only** (`bash _build_fe.sh`).
**No API change, no pipeline runs.**

| Phase | Scope |
|---|---|
| **1 — MVP** | the trio above; quiz + decision log + single-station debrief score |
| **2** | all 11 droughts (real monthly replay — author 11 JSONs); `crma-api` session state + multi-station leaderboard |
| **3** | 10 missing flood replays (re-run `flood_data_prep`→Julia BN — *first verify ECMWF reforecast back to 2019*); CLIMADA hazard→impact tabs (badged); per-event impact BN elicited from loss & damage |

## 8. Open items to confirm before/while building

1. **`gid_1` per event** — confirm Nairobi / Kenya / Karamoja admin-1 IDs against
   `icpac_adm1v3.json` (the `bn-dag/*.json` are keyed by `GID_1`).
2. **Risk-decisions stub state** — confirm `stage=risk-decisions` routing exists in
   `arco-ibf` to hang Scenario Mode off.
3. **Nairobi loss narrative** — RK MDX key `2024-0247-KEN` is the *2024* event; the
   replay/hazard are *2026*. For `hindsight:off` this is invisible (loss only shown at
   debrief); decide whether debrief uses the 2024 EM-DAT MDX or a short 2026 loss note.

---

## 9. Realignment (note1) — evidence/CRMA-centric

Following `note1.md`, the framing is reaffirmed as **forecast + observations +
context → CRMA → decision**, *not* hazard/impact-model driven. The BN is the
simulation engine; hazard/impact modelling is supporting science for building
storylines, not part of the participant flow. Decisions taken:

| Item | Decision |
|---|---|
| Competitive scoring / leaderboard | **Dropped.** Assessment is formative (reasoning capture + debrief). `quiz` kept as non-scored reflection prompts. |
| Terminology | game→simulation, game script→scenario script, player→participant/stakeholder. Engine states stay `Monitor → Evaluate → Assess → Actionable_Risk` (no new "Trigger-Eligible" vocabulary). |
| Hazard footprint (RIM2D/WRSI) | Moved from a decision-time tab to the **debrief** as context/provenance — never a decision input. |
| Evidence values | **Bound to the live BN-DAG** (`raw`/`state` at the cursor); authored strings are the offline fallback. Surfaces the engine's actual per-date evidence, not a paraphrase. |
| Risk advisory | Surface the engine's CRMA state + posterior + `P(High+Extreme)` (the cost-loss decision) as an advisory, separate from the participant's decision. |
| CLIMADA / impact | Stays deferred; "impact" = recorded EM-DAT loss at debrief. |

### Corrected facts (note1 overstatements)

- **GEFS is not wired** — flood evidence is **ECMWF/IFS** only (GEFS = the retired
  `forecast_agreement` node). Drought is **SEAS5/SEAS51** (already the basis). So
  "forecast threshold exceedance" is mostly *surfacing existing BN values*.
- The **satellite-rainfall debrief animation** (IMERG/CHIRPS/CMORPH) does **not**
  exist yet — the RIM2D/wflow GIFs are *model outputs*, not raw-rainfall animations.

### Product phasing

```
Phase 1  Drought — all 11 events (RM rounds → RK debrief; no hazard/impact)   [in progress: 2/11]
Phase 2  Flood   — all flood events (RM rounds → RK debrief)                   [needs flood BN replay]
Phase 3  Drought + hazard/impact modelling (wflow WRSI + CLIMADA)             [later]
Phase 4  Flood   + hazard/impact modelling (RIM2D + CLIMADA)                  [later]
```

Within Phase 1: live BN-DAG evidence binding + risk advisory = **done**; a
satellite-rainfall debrief animation (IMERG/CHIRPS/CMORPH) = optional polish.

---

## 10. Drought-only consolidation (current starting point)

Scope the first production cut to the **11 drought events only**, built **purely on
the deployed CRMA frontend + backend** — no hazard assets, no external runtime
dependency. The simulation is a thin orchestration over two existing CRMA stages:

```
Risk Monitoring (RM)  →  DOC decision  →  Risk Knowledge (RK)
  rounds: drought BN        Monitor/Watch/        debrief: EM-DAT
  replay by init month      Warning/Emergency     loss & damage
  (choropleth + BN DAG)                           storyline
        ▲ hosted in the Risk Decisions stage (launcher shipped) ▲
```

**Backend: nothing to add.** All endpoints already exist and are deployed:
`/api/ibf-drought-calendar`, `/api/ibf-drought-regions/{init}`,
`/api/drought-bn-dag/{init}`, `/api/emdat-event-markdown/{DisNo}`. The drought
monthly BN covers **1981–2026**, so every event's init months are in range.

**The 11 drought events.** Each has a working **RK debrief deep link** in
`pam_team/DevOps-hazard-modeling/README.md` — a replacement key is provided for
every event (including the three without a native EM-DAT record), so there are no
gaps. RK key = the README `event`; RK `month` = `debrief.rk_month`; replay steps a
short pre-peak window of `init` months in RM.

| # | Country | Event | RK month | RK key (Dis No / replacement) |
|--:|---|---|---|---|
| 1 | Burundi | 2021-22 | 2021-01 | `2021-IBF01-BDI` |
| 2 | Djibouti | 2022 | 2022-06 | `2022-9370-DJI` |
| 3 | Eritrea | Highlands 2021-23 | 2021-01 | `2021-IBF03-ERI` |
| 4 | Ethiopia | Blue Nile 2021-22 | 2021-05 | `2021-9546-ETH` |
| 5 | Kenya | Tana/ASAL 2020-23 | 2020-12 | `2020-9609-KEN` **built** |
| 6 | Rwanda | Akagera 2016-17 | 2016-01 | `2016-IBF06-RWA` |
| 7 | Somalia | South-Central 2020-23 | 2020-03 | `2020-9609-SOM` |
| 8 | South Sudan | Upper Nile 2021-23 | 2021-01 | `2021-9639-SSD` |
| 9 | Sudan | Eastern 2022 | 2022-01 | `2022-9788-SDN` |
| 10 | Tanzania | Kagera 2021-22 | 2021-11 | `2021-9848-TZA` |
| 11 | Uganda | Karamoja 2022 | 2022-07 | `2022-9436-UGA` **built** |

Built: 2 (Kenya, Uganda). **To author: 9** — each is the proven drought template
(3 rounds: outlook → deficit+CDI → confirmation) with its own init-month cursors,
`emdat_event_key`, `debrief.rk_month`, country/admin1, and brief. `gid_1` is
optional (auto-opens the BN DAG; otherwise the participant clicks the RM
choropleth).

### Deploy (production Cloud Run) — frontend rebuild only

`_build_fe.sh` rsyncs the **arco-ibf working tree** → Cloud Build → Cloud Run, with
`_API_URL` already wired to the deployed `crma-api`. Because Scenario Mode is a
frontend addition over existing endpoints (and now has **no external asset**), the
production deploy is one command:

```bash
cd cno-e4drr/devops/crma-fe-cr
cp _build_fe.env.example _build_fe.env   # first time
bash _build_fe.sh                        # stages arco-ibf (cmra-web) → builds → deploys public
```

No `crma-api` rebuild, no new env var, no GCS upload. Roll back via
`gcloud run services update-traffic crma-frontend --to-revisions=<prev>=100`.
