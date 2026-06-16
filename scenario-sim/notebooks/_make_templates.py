#!/usr/bin/env python3
"""
_make_templates.py — generate flood_template.ipynb and drought_template.ipynb.

The two templates are the only hand-maintained notebooks; build_all.py uses
papermill to stamp one executed notebook per scenario into built/. Each
template reads its OWN scenario JSON at runtime (via the EVENT_ID parameter)
and walks the ARCO -> evidence-node -> Julia-BN journey for that event.

Run:  python _make_templates.py    # writes the two .ipynb next to this file
"""
from __future__ import annotations
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def md(src: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": src.splitlines(keepends=True)}


def code(src: str, tags: list[str] | None = None) -> dict:
    meta = {"tags": tags} if tags else {}
    return {"cell_type": "code", "execution_count": None, "metadata": meta,
            "outputs": [], "source": src.strip("\n").splitlines(keepends=True)}


def notebook(cells: list[dict]) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4, "nbformat_minor": 5,
    }


# --------------------------------------------------------------------------- #
# Shared head cells (intro + parameters + scenario load + framing)
# --------------------------------------------------------------------------- #
def head_cells(hazard: str) -> list[dict]:
    other = "drought" if hazard == "flood" else "flood"
    default_event = ("nairobi_flood_2026" if hazard == "flood"
                     else "kenya_asal_drought_2020")
    return [
        md(f"""# Scenario analysis — {hazard.title()} event

This notebook is the **data provenance** for one `{hazard}` scenario in the CRMA
scenario simulator. It reproduces, from the raw **ARCO** (Analysis-Ready
Cloud-Optimized) stores, the evidence-card values the trainee sees — proving each
number came from real reanalysis/forecast data subjected to the operational
transform, not a hand-typed card.

**The journey** (every section below is one hop):

```
ARCO store  ->  subset / reanalysis transform  ->  admin-1 zonal reduce
            ->  Gaussian soft-bin  ->  evidence-node probability vector
            ->  Julia / RxInfer BN posterior  ->  CRMA state
```

Method references: `bn-ibf/{hazard}_ibf/README.md` and (flood) the 11+1-event
run record `bn-ibf/flood_ibf/2026-06-09-11flood_events_run_crma_record.md`.
The {other} analogue lives in the sibling `{other}_template.ipynb`."""),

        code(f"""
# --- parameters (papermill injects per-scenario overrides here) ---
EVENT_ID        = "{default_event}"
BN_IBF_ROOT     = None          # None -> sibling bn-ibf checkout; or set a path
FORECAST_SOURCE = "auto"        # auto | ifs_ens_wb2 | ecmwf_icechunk (flood)
WINDOW_PRE      = 10            # days before peak (flood window)
WINDOW_POST     = 5            # days after peak  (flood window)
RP_YEARS        = {2 if hazard == 'flood' else 5}
COST_LOSS_RATIO = 0.20
RUN_LIVE        = True          # False -> narrate from cache only, no cloud/Julia
""", tags=["parameters"]),

        code("""
import os, sys
if BN_IBF_ROOT:
    os.environ["BN_IBF_ROOT"] = BN_IBF_ROOT
sys.path.insert(0, os.path.dirname(os.path.abspath("_scenario_nb_lib.py")) or ".")
import _scenario_nb_lib as L
import pandas as pd
from IPython.display import Markdown, display

scenario = L.load_scenario(EVENT_ID)
display(Markdown(
    f"## {scenario['title']}\\n\\n"
    f"- **Hazard / country / admin-1**: {scenario['hazard']} · "
    f"{scenario['country']} · {scenario['admin1']}  (`{scenario['gid_1']}`)\\n"
    f"- **Forecastability**: {scenario['forecastability']}\\n"
    f"- **Peak (hidden until debrief)**: {scenario['peak']['date']}\\n"
    f"- **EM-DAT key**: {scenario.get('emdat_event_key','—')}\\n\\n"
    f"> {scenario['brief_outcome_free']}"
))
"""),
    ]


# --------------------------------------------------------------------------- #
# FLOOD body
# --------------------------------------------------------------------------- #
def flood_body() -> list[dict]:
    return [
        md("""## 1. The ARCO datasets — open the cloud-optimized stores

The flood pipeline reads three ARCO stores, all anonymous-readable from
`source.coop` / WeatherBench2. We open them **lazily** — nothing downloads yet;
we only inspect structure (dims, chunks, members) to show they are
analysis-ready and cloud-optimized."""),
        code("""
prep = L.import_prep("flood")            # the operational flood_data_prep module

imerg = prep.open_icechunk("observations/imerg_hh_icechunk")   # reanalysis-grade obs
print("IMERG HH icechunk:", dict(imerg.sizes))

fsrc = L.forecast_source(scenario, FORECAST_SOURCE)
print("\\nForecast source:", fsrc)
ecmwf = (prep.open_ifs_ens_wb2() if fsrc == "ifs_ens_wb2"
         else prep.open_ecmwf_store(pencil=False))            # 50/51-member ensemble TP
print("ECMWF/IFS-ENS:", dict(ecmwf.sizes))

cmorph = prep.load_cmorph_thresholds_icechunk("observations/cmorph_rp_icechunk", RP_YEARS)
print(f"\\nCMORPH {RP_YEARS}-yr RP thresholds (durations):", list(cmorph)[:7])
"""),
        md("""### A raw field straight off the store
One small read to prove the store is live: the IMERG **7-day antecedent**
rainfall over East Africa ending on the (hidden) peak date — the same reanalysis
field the antecedent node consumes, shown here *before* any admin-1 reduction.
(`imerg_daily_totals` returns the 7 daily fields over `[D-7, D)`; we sum them.)"""),
        code("""
import matplotlib.pyplot as plt
D = pd.Timestamp(L.peak_date(scenario))
ant7 = prep.imerg_daily_totals(imerg, D).sum("time")     # (lat, lon) mm, 7-day sum
ant7.plot(figsize=(6, 4), cmap="Blues", vmax=200)
plt.title(f"IMERG 7-day antecedent rainfall (mm) ending {D.date()}")
plt.xlabel("lon"); plt.ylabel("lat"); plt.show()
"""),

        md("""## 2. Reanalysis / transform -> admin-1 evidence

We now run the **operational** prep over the 16-day window `[peak-10, peak+5]`.
Each day is its own BN analysis: a 7-day IMERG antecedent + a 50/51-member ECMWF
forecast out to 7 days, reduced to the 227 admin-1 polygons. The prep emits one
soft-evidence CSV per day (`flood_inputs_<D>_soft.csv`, 227 rows × ~40 cols)."""),
        code("""
win = L.flood_window(L.peak_date(scenario), WINDOW_PRE, WINDOW_POST)
print(f"Window: {win[0].date()} .. {win[-1].date()}  ({len(win)} days)")

if RUN_LIVE:
    in_dir = L.run_flood_prep(scenario, pre=WINDOW_PRE, post=WINDOW_POST,
                              rp_years=RP_YEARS, fsource=FORECAST_SOURCE)
else:
    in_dir = L.event_cache(EVENT_ID) / "bn_inputs"
print("prep CSVs in:", in_dir)
"""),
        md("""### The evidence row for *this* scenario's boundary
Pull the single admin-1 row (`gid_1`) on the peak day and show the raw evidence
the BN will consume: antecedent mm, exceedance prob, tail ratio, spatial,
trend."""),
        code("""
peak_csv = in_dir / f"flood_inputs_{pd.Timestamp(L.peak_date(scenario)).date()}_soft.csv"
row = L.boundary_row(peak_csv, scenario["gid_1"])
cols = [c for c in ["name", "country", "antecedent_rainfall_mm", "antecedent_category",
                    "ecmwf_eprob_heavy", "ens_max_ratio", "spatial_coverage",
                    "rainfall_trend", "trend_slope_mm_per_day", "target_date"]
        if c in row.index]
display(row[cols].to_frame("value"))
"""),

        md("""## 3. Scalar -> evidence node (Gaussian soft-binning)

Each scalar above becomes a **probability vector** over its node's states via the
operational `soft_bin()` (σ ≈ 25-30 % of the narrowest bin). That vector — not
its argmax — is what the BN ingests on each parent's Pearl virtual-evidence
channel. The card "135 mm -> Saturated" is just the argmax of `ant_p1..p5`."""),
        code("""
import matplotlib.pyplot as plt
import numpy as np

pairs = [   # (short soft_bin code, the prep CSV column it bins)
    ("ant",  row.get("antecedent_rainfall_mm", np.nan)),
    ("exc",  row.get("ecmwf_eprob_heavy", np.nan)),
    ("tail", row.get("ens_max_ratio", np.nan)),
    ("spa",  row.get("spatial_coverage", np.nan)),
    ("trn",  row.get("trend_slope_mm_per_day", np.nan)),
]
fig, axes = plt.subplots(2, 3, figsize=(15, 6)); axes = axes.ravel()
computed = {}                                  # short code -> argmax state label
for ax, (node, val) in zip(axes, pairs):
    if pd.isna(val):
        ax.set_visible(False); continue
    labels = L.FLOOD_NODE_LABELS[node]
    vec = L.plot_soft_bin(prep, node, float(val), labels, ax=ax)
    computed[node] = labels[int(vec.argmax())]
for ax in axes[len(pairs):]:
    ax.set_visible(False)
plt.tight_layout(); plt.show()
print("argmax states:", computed)
"""),
        md("""### Card check — recomputed vs scenario JSON
Confirm the values we just derived from ARCO match the `value_by_date` the
simulator shows the trainee for each evidence card (matched by `bn_node`)."""),
        code("""
# map each card's bn_node back to the short code we computed above
bn_to_short = {bn: s for s, bn in L.FLOOD_SHORT2BN.items()}
by_card = {c["id"]: computed.get(bn_to_short.get(c.get("bn_node", ""), ""), "—")
           for c in scenario["evidence_cards"]}
display(L.card_vs_computed(scenario, by_card))
"""),

        md("""## 4. Julia / RxInfer BN inference

The evidence CSVs go to the **Julia** BN (`run_flood_dbn_window.jl`): RxInfer
message passing, 5 soft-evidence parents -> hidden `risk_level`, DBN temporal
coupling (α=0.6, lookback=7), then the cost-loss CRMA rule (γ=0.20). The BN is
Julia; only the data prep above is Python."""),
        code("""
if RUN_LIVE:
    out_dir = L.run_flood_bn(scenario, in_dir, expect=len(win),
                             cost_loss_ratio=COST_LOSS_RATIO)
else:
    out_dir = L.event_cache(EVENT_ID) / "output"
peak_out = out_dir / "dbn" / f"flood_bn_v1_{pd.Timestamp(L.peak_date(scenario)).date()}.csv"
brow = L.boundary_row(peak_out, scenario["gid_1"])
show = [c for c in ["risk_level", "crma_state", "traffic_light",
                    "risk_minimal", "risk_low", "risk_moderate", "risk_high",
                    "risk_extreme", "crma_explanation"] if c in brow.index]
display(brow[show].to_frame("posterior / CRMA"))
"""),

        md("""## 5. Round-by-round CRMA timeline

The scenario stages evidence over rounds (`reveal_evidence` per `cursor_date`).
We replay the CRMA call at each round's cursor and across the full window —
reproducing this event's row in the run-record table (worst CRMA, worst day vs
peak, earliest Assess+)."""),
        code("""
rows = []
for f in sorted((out_dir / "dbn").glob("flood_bn_v1_*.csv")):
    d = f.stem.replace("flood_bn_v1_", "")
    try:
        r = L.boundary_row(f, scenario["gid_1"])
        rows.append({"date": d, "risk_level": r.get("risk_level"),
                     "crma_state": r.get("crma_state"),
                     "tail_ratio": r.get("ens_max_ratio")})
    except KeyError:
        pass
timeline = pd.DataFrame(rows).sort_values("date")
display(timeline)

print("\\nScenario rounds (what the trainee is shown when):")
for rd in scenario["rounds"]:
    print(f"  R{rd['round']} {rd['cursor_date']}  reveal={rd.get('reveal_evidence')}"
          f"  | engine: {rd.get('engine_state','')}")
"""),

        md("""## 6. DBN carry + counterfactual

The combined DBN output shows yesterday's posterior blended into today (why the
peak day stays elevated). The scenario's counterfactual injects virtual evidence
on `R_obs` to illustrate the no-regret-action world."""),
        code("""
combined = out_dir / "flood_bn_v1_dbn_window.csv"
if combined.exists():
    dbn = pd.read_csv(combined)
    sub = dbn[dbn[[c for c in L._GID_COLS if c in dbn.columns][0]].astype(str)
              == scenario["gid_1"]]
    display(sub.head(20))
cf = scenario.get("counterfactual", {})
display(Markdown(f"**Counterfactual** (virtual-evidence node "
                 f"`{cf.get('virtual_evidence_node','—')}`): {cf.get('prompt','')}\\n\\n"
                 f"> {cf.get('narrative','')}"))
"""),

        md("""## 7. Debrief — loss & reconstruction

The recorded loss/damage (EM-DAT) and the reconstruction-quiz prompts that close
the simulation. The peak date is revealed here."""),
        code("""
db = scenario.get("debrief", {})
display(Markdown(
    f"- **Loss markdown endpoint**: `{db.get('loss_markdown','—')}`\\n"
    f"- **Risk-Knowledge month**: {db.get('rk_month','—')}\\n"
    f"- **EM-DAT key**: {L.emdat_key(scenario)}\\n\\n"
    f"**Reconstruction quiz**:\\n" +
    "\\n".join(f"  - {q}" for q in db.get("reconstruction_quiz", []))
))
"""),
    ]


# --------------------------------------------------------------------------- #
# DROUGHT body
# --------------------------------------------------------------------------- #
def drought_body() -> list[dict]:
    return [
        md("""## 1. The ARCO datasets — open the cloud-optimized stores

The drought pipeline is the monthly analogue of flood: ERA5 SPI reanalysis (obs),
SEAS5 51-member SPI-3 forecast (6 lead months), and ERA5 fitted SPI return-period
thresholds. All anonymous-readable. Opened lazily — structure only."""),
        code("""
prep = L.import_prep("drought")          # operational drought_data_prep module

obs = prep.open_zarr_anon(prep.SPI_OBS_PREFIX)            # ERA5 SPI reanalysis
print("ERA5 SPI obs:", dict(obs.sizes))
forecast = prep.open_icechunk_anon(prep.SEAS5_SPI3_PREFIX)   # SEAS5 51-member SPI3
print("SEAS5 SPI3 forecast:", dict(forecast.sizes))
rp = prep.open_icechunk_anon(prep.SPI_RP_PREFIX)         # fitted SPI RP thresholds
print("ERA5 SPI RP thresholds:", dict(rp.sizes))
"""),

        md("""## 2. Reanalysis / transform -> admin-1 evidence

Per monthly init the prep computes: `current_spi3` (latest ERA5 month ≤ target),
`deficit_prob = P(SPI ≤ -1.0)` across SEAS5 leads, `tail = p5(ens_min SPI)`,
spatial coverage, and the 6-month SPI trend — reduced to 227 admin-1 polygons.
Threshold direction is **SPI ≤ RP** (deficit), the mirror of flood's TP ≥ RP."""),
        code("""
inits = L.drought_inits(scenario)          # monthly cursors from the JSON rounds
print("Init months (rounds):", inits)

csvs = {}
for m in inits:
    if RUN_LIVE:
        csvs[m] = L.run_drought_prep(scenario, m, rp_years=RP_YEARS)
    else:
        csvs[m] = L.event_cache(EVENT_ID) / "bn_inputs" / f"drought_inputs_{m}.csv"
print(csvs)
"""),
        code("""
first = next(iter(csvs.values()))
row = L.boundary_row(first, scenario["gid_1"])
cols = [c for c in ["name", "country", "current_spi3", "current_spi3_category",
                    "forecast_deficit_prob", "ens_min_spi", "spatial_coverage",
                    "spi3_trend", "trend_slope_spi_per_month", "target_season",
                    "target_date"] if c in row.index]
display(row[cols].to_frame("value"))
"""),

        md("""## 3. Scalar -> evidence node (Gaussian soft-binning)

Same soft-evidence mechanism as flood, drought node set
(`cur/def/spa/trn/tail`). The probability vector is the virtual evidence fed to
each BN parent."""),
        code("""
import matplotlib.pyplot as plt
import numpy as np
pairs = [   # (short soft_bin code, the prep CSV column it bins)
    ("cur",  row.get("current_spi3", np.nan)),
    ("def",  row.get("forecast_deficit_prob", np.nan)),
    ("tail", row.get("ens_min_spi", np.nan)),
    ("spa",  row.get("spatial_coverage", np.nan)),
    ("trn",  row.get("trend_slope_spi_per_month", np.nan)),
]
fig, axes = plt.subplots(2, 3, figsize=(15, 6)); axes = axes.ravel()
computed = {}
for ax, (node, val) in zip(axes, pairs):
    if pd.isna(val):
        ax.set_visible(False); continue
    labels = L.DROUGHT_NODE_LABELS[node]
    vec = L.plot_soft_bin(prep, node, float(val), labels, ax=ax)
    computed[node] = labels[int(vec.argmax())]
for ax in axes[len(pairs):]:
    ax.set_visible(False)
plt.tight_layout(); plt.show()
print("argmax states:", computed)
"""),

        md("""### 3b. The CDI node — *virtual* evidence, not a BN parent

Drought scenarios add a **Combined Drought Indicator** card
(`evidence_type: virtual`, `bn_node: cdi_class`). The CDI is **not** a parent of
`risk_level`; it multiplies the risk posterior (a 14×5 noisy-likelihood) =
Pearl's virtual evidence. This is the key conceptual difference from the flood
parents — it sharpens the posterior without sitting in the DAG."""),
        code("""
cdi_card = next((c for c in scenario["evidence_cards"]
                 if c.get("bn_node") == "cdi_class"), None)
if cdi_card:
    display(Markdown(
        f"**{cdi_card['label']}**  — type *{cdi_card['evidence_type']}*\\n\\n"
        f"- value_by_date: {cdi_card.get('value_by_date', {})}\\n"
        f"- teaching note: {cdi_card.get('teaching_note','')}\\n\\n"
        "Applied multiplicatively to P(risk_level) after the parent inference, "
        "then renormalized — it cannot create a state the parents gave zero mass."))
else:
    print("This scenario has no CDI card.")
"""),

        md("""## 4. Julia / RxInfer drought BN inference

The CSV goes to `drought_bn_ibf_v1.jl` (RxInfer; **Julia output is
authoritative**, the Python pgmpy path is sanity-only per the drought README).
5 parents -> `risk_level` -> cost-loss CRMA."""),
        code("""
outs = {}
for m, csv in csvs.items():
    outs[m] = L.run_drought_bn(scenario, csv) if RUN_LIVE else (
        L.event_cache(EVENT_ID) / "output" / f"drought_bn_v1_{m}.csv")
first_out = next(iter(outs.values()))
brow = L.boundary_row(first_out, scenario["gid_1"])
show = [c for c in ["risk_level", "crma_state", "traffic_light",
                    "risk_minimal", "risk_low", "risk_moderate", "risk_high",
                    "risk_extreme", "crma_explanation"] if c in brow.index]
display(brow[show].to_frame("posterior / CRMA"))
"""),

        md("""## 5. Round-by-round CRMA timeline (lead -> onset -> peak)

Slow-onset droughts give long lead. We show the CRMA call at each round's init
month so the value of the ~6-month seasonal signal is explicit."""),
        code("""
rows = []
for m, out in outs.items():
    try:
        r = L.boundary_row(out, scenario["gid_1"])
        rows.append({"init": m, "risk_level": r.get("risk_level"),
                     "crma_state": r.get("crma_state")})
    except KeyError:
        pass
display(pd.DataFrame(rows))
for rd in scenario["rounds"]:
    print(f"  R{rd['round']} {rd['cursor_date']}  reveal={rd.get('reveal_evidence')}"
          f"  | engine: {rd.get('engine_state','')}")
"""),

        md("""## 6. Counterfactual & 7. Debrief"""),
        code("""
cf = scenario.get("counterfactual", {})
db = scenario.get("debrief", {})
display(Markdown(
    f"**Counterfactual** (virtual-evidence node "
    f"`{cf.get('virtual_evidence_node','—')}`): {cf.get('prompt','')}\\n\\n"
    f"> {cf.get('narrative','')}\\n\\n---\\n\\n"
    f"**Debrief** — loss `{db.get('loss_markdown','—')}` · "
    f"RK month {db.get('rk_month','—')} · EM-DAT {L.emdat_key(scenario)}\\n\\n"
    "**Reconstruction quiz**:\\n" +
    "\\n".join(f"  - {q}" for q in db.get("reconstruction_quiz", []))
))
"""),
    ]


def main() -> None:
    flood = notebook(head_cells("flood") + flood_body())
    drought = notebook(head_cells("drought") + drought_body())
    (HERE / "flood_template.ipynb").write_text(json.dumps(flood, indent=1))
    (HERE / "drought_template.ipynb").write_text(json.dumps(drought, indent=1))
    print("wrote flood_template.ipynb and drought_template.ipynb")


if __name__ == "__main__":
    main()
