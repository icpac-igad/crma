# Scenario analysis notebooks

One Jupyter notebook per scenario in `../scenarios/` (23 total: 12 flood +
11 drought). Each notebook is the **data provenance** for its scenario — it
reproduces, from the raw **ARCO** (Analysis-Ready Cloud-Optimized) stores, the
evidence-card values the CRMA scenario simulator shows a trainee, proving every
number came from real reanalysis/forecast data put through the operational
transform rather than a hand-typed card.

## The journey each notebook walks

```
ARCO store  ->  subset / reanalysis transform  ->  admin-1 zonal reduce
            ->  Gaussian soft-bin  ->  evidence-node probability vector
            ->  Julia / RxInfer BN posterior  ->  CRMA state
```

This mirrors the operational method documented in:

- `bn-ibf/flood_ibf/README.md` — flood BN-IBF (daily, IMERG + ECMWF/IFS-ENS + CMORPH RP)
- `bn-ibf/flood_ibf/2026-06-09-11flood_events_run_crma_record.md` — the **11+1**
  GHACOF73 flood-event hindcast (commit `75ee284a`), 16-day `[peak-10, peak+5]` windows
- `bn-ibf/drought_ibf/README.md` — drought BN-IBF (monthly, ERA5 + SEAS5 SPI + ERA5 SPI RP)

The data prep is **Python** (`*_data_prep.py`); the Bayesian Network inference is
**Julia / RxInfer** (`*_bn_ibf_v1.jl` / `run_flood_dbn_window.jl`). The notebooks
orchestrate both and never fork the pipeline code.

## Files

| File | Role |
|------|------|
| `_scenario_nb_lib.py` | Shared helpers: load scenario, derive windows, open ARCO stores, run prep + Julia BN, soft-bin plots, card-vs-computed table. |
| `_make_templates.py` | Generates the two templates below (the only hand-maintained notebooks). |
| `flood_template.ipynb` | Flood master notebook — reads its own scenario via the `EVENT_ID` parameter. |
| `drought_template.ipynb` | Drought master notebook (adds the CDI virtual-evidence section). |
| `build_all.py` | papermill driver — stamps one executed notebook per scenario into `built/`. |
| `built/` | Executed per-event notebooks (`<event_id>.ipynb`). |
| `cache/<event_id>/` | Per-event prep CSVs + BN output, so re-rendering doesn't re-hit the cloud. |

## Prerequisites (live mode)

- **`uv`** — the data stack (icechunk, xarray, zarr>=3, regionmask, gcsfs, …)
  installs transiently via the `build_all.py` shebang / `uv run`.
- **Julia ≥ 1.10** on PATH with the `bn-ibf/flood_ibf` project instantiated
  (`export PATH="$HOME/.juliaup/bin:$PATH"`; see `bn-ibf/flood_ibf/README.md`).
- **`icpac_adm1v3.geojson`** present in `bn-ibf/flood_ibf/` and
  `bn-ibf/drought_ibf/` (runtime prerequisite, not in git).
- The sibling **`bn-ibf`** checkout at `../../../bn-ibf` (override with
  `BN_IBF_ROOT`).

## Usage

```bash
# regenerate the two templates after editing _make_templates.py
python _make_templates.py

# list scenarios and the template each maps to
./build_all.py --list

# build one event live (ARCO reads + Julia BN)
./build_all.py --only nairobi_flood_2026

# build all flood / all drought / everything
./build_all.py --hazard flood
./build_all.py --hazard drought
./build_all.py --continue-on-error          # all 23, don't stop on a failure

# narrate from cache only (no cloud / no Julia) — for quick rendering
./build_all.py --no-run
```

### Run a single notebook interactively

Open `flood_template.ipynb` (or `drought_template.ipynb`) in Jupyter, set
`EVENT_ID` in the **parameters** cell to any scenario stem (e.g.
`somalia_flood_2023`), and Run All. Launch the kernel under `uv` so the ARCO/
soft-bin cells have their deps.

## Parameters (papermill `parameters` cell)

| Param | Default | Meaning |
|-------|---------|---------|
| `EVENT_ID` | template default | scenario stem in `../scenarios/` |
| `FORECAST_SOURCE` | `auto` | flood: `ifs_ens_wb2` (historical) vs `ecmwf_icechunk` (≥2025 operational) |
| `WINDOW_PRE` / `WINDOW_POST` | `10` / `5` | flood window `[peak-pre, peak+post]` |
| `RP_YEARS` | `2` (flood) / `5` (drought) | return-period threshold |
| `COST_LOSS_RATIO` | `0.20` | CRMA cost-loss γ |
| `RUN_LIVE` | `True` | `False` → narrate from `cache/`, skip cloud + Julia |

## Notes

- **Flood vs operational**: historical events (pre-2025) replay the WeatherBench2
  archived ECMWF IFS-ENS; the 2026 Nairobi scenario reads the live ECMWF
  icechunk store. `FORECAST_SOURCE=auto` picks this by peak year.
- **Drought authority**: the drought README flags that the Julia BN output is
  authoritative; the Python pgmpy path is a sanity reference only.
- **CDI**: drought scenarios carry a Combined Drought Indicator card as *virtual*
  evidence (`bn_node: cdi_class`) — it multiplies the risk posterior, it is not a
  DAG parent. The drought template has a dedicated section (§3b) for it.
