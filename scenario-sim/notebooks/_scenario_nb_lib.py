"""
_scenario_nb_lib.py — shared helpers for the per-event scenario notebooks.

Each notebook in this directory documents ONE scenario JSON from
`scenario-sim/scenarios/` and reproduces, from the raw ARCO (Analysis-Ready
Cloud-Optimized) stores, the evidence-card values that the scenario simulator
shows a trainee. The journey is always:

    ARCO store  ->  subset / reanalysis transform  ->  admin-1 zonal reduce
                ->  Gaussian soft-bin  ->  evidence-node probability vector
                ->  Julia BN posterior  ->  CRMA state

The actual data + BN code lives in the sibling `bn-ibf` repo; this module is a
thin orchestration layer so a notebook stays narration + calls and never forks
the operational pipeline (`flood_data_prep.py` / `drought_data_prep.py` /
`*_bn_ibf_v1.jl`).

Nothing here is hazard-specific beyond the two `import_prep()` branches; the
notebooks pass their scenario JSON in and the helpers read hazard / gid_1 /
peak / stores off it.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
THIS_DIR = Path(__file__).resolve().parent                  # .../scenario-sim/notebooks
SCENARIO_DIR = THIS_DIR.parent / "scenarios"                # .../scenario-sim/scenarios
CACHE_DIR = THIS_DIR / "cache"


def bn_ibf_root() -> Path:
    """Root of the sibling bn-ibf repo (holds flood_ibf/ and drought_ibf/).

    Override with the BN_IBF_ROOT env var; defaults to the sibling checkout.
    """
    env = os.environ.get("BN_IBF_ROOT")
    if env:
        return Path(env).resolve()
    return (THIS_DIR.parents[2] / "bn-ibf").resolve()       # /scratch/notebook/bn-ibf


def hazard_dir(hazard: str) -> Path:
    return bn_ibf_root() / ("flood_ibf" if hazard == "flood" else "drought_ibf")


def adm1_path() -> str:
    """Absolute path to the committed 227-region admin-1 boundaries.

    Lives in flood_ibf/ (committed there); drought prep runs from drought_ibf/
    so we always pass the absolute path rather than rely on cwd.
    """
    return str(hazard_dir("flood") / "icpac_adm1v3.geojson")


# --------------------------------------------------------------------------- #
# Scenario loading
# --------------------------------------------------------------------------- #
def load_scenario(event_id: str) -> dict:
    """Read the scenario JSON the notebook documents (by its event_id)."""
    path = SCENARIO_DIR / f"{event_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"scenario {event_id!r} not found at {path}. "
            f"Available: {sorted(p.stem for p in SCENARIO_DIR.glob('*.json'))}"
        )
    return json.loads(path.read_text())


def peak_date(scenario: dict) -> str:
    """Best-known event peak date string (YYYY-MM-DD for flood, YYYY-MM for drought)."""
    return scenario["peak"]["date"]


def forecast_source(scenario: dict, override: str = "auto") -> str:
    """Which forecast store the flood prep should read.

    Historical events (pre-2025) replay the WeatherBench2 archived ECMWF
    IFS-ENS (`ifs_ens_wb2`); the live operational window (>=2025, e.g. Nairobi
    Mar-2026) reads the recent-only ECMWF icechunk store (`ecmwf_icechunk`).
    """
    if override != "auto":
        return override
    yr = int(peak_date(scenario)[:4])
    return "ecmwf_icechunk" if yr >= 2025 else "ifs_ens_wb2"


# --------------------------------------------------------------------------- #
# Windows
# --------------------------------------------------------------------------- #
def flood_window(peak: str, pre: int = 10, post: int = 5) -> list[pd.Timestamp]:
    """[peak-pre, peak+post] inclusive daily window (the 16-day run layout)."""
    p = pd.Timestamp(peak)
    start = p - pd.Timedelta(days=pre)
    end = p + pd.Timedelta(days=post)
    return list(pd.date_range(start, end, freq="D"))


def drought_inits(scenario: dict) -> list[str]:
    """Monthly init cursors the drought rounds step through (from the JSON)."""
    return [r["cursor_date"] for r in scenario["rounds"]]


# --------------------------------------------------------------------------- #
# Importing the operational prep module (for the ARCO-demo cells)
# --------------------------------------------------------------------------- #
def import_prep(hazard: str):
    """Import `flood_data_prep.py` / `drought_data_prep.py` as a module.

    Used by the notebook's "open the ARCO store" and "soft-bin" cells so the
    demonstration calls the same code the operational pipeline runs. Requires
    the data-stack deps (icechunk, xarray, zarr>=3, regionmask, ...) in the
    running kernel — launch the notebook under `uv run` with those `--with`
    packages (see build_all.py / README).
    """
    d = hazard_dir(hazard)
    name = "flood_data_prep" if hazard == "flood" else "drought_data_prep"
    sys.path.insert(0, str(d))
    spec = importlib.util.spec_from_file_location(name, str(d / f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# uv invocation (subprocess prep) — keeps the notebook kernel light
# --------------------------------------------------------------------------- #
_UV_PKGS = [
    "--with", "icechunk", "--with", "xarray", "--with", "zarr>=3",
    "--with", "dask", "--with", "numpy", "--with", "pandas",
    "--with", "geopandas", "--with", "regionmask", "--with", "netcdf4",
    "--with", "pyarrow", "--with", "scipy", "--with", "fsspec",
    "--with", "s3fs", "--with", "gcsfs", "--with", "bottleneck",
]

# init calendar month -> SEAS5 target season (lead-3/4/5 convention), copied
# from run_drought_bn_backfill.INIT_TO_SEASON so each init forecasts a season
# within SEAS5's 1..6 lead range.
INIT_TO_SEASON = {12: "MAM", 1: "MAM", 2: "MAM",
                  3: "JJA", 4: "JJA", 5: "JJA",
                  6: "OND", 7: "OND", 8: "OND",
                  9: "DJF", 10: "DJF", 11: "DJF"}


def season_for_init(init_month: str) -> str:
    """'YYYY-MM' -> operational target season."""
    return INIT_TO_SEASON[int(init_month.split("-")[1])]


def _run(cmd: list[str], cwd: Path) -> None:
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)


def event_cache(event_id: str) -> Path:
    d = CACHE_DIR / event_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# --------------------------------------------------------------------------- #
# Flood pipeline (mirrors run_flood_event.sh, but for our derived window)
# --------------------------------------------------------------------------- #
def run_flood_prep(scenario: dict, *, pre=10, post=5, rp_years=2,
                   fsource="auto", adm1=None, force=False) -> Path:
    """Soft-evidence prep over the whole window in one range-mode process.

    Returns the directory holding flood_inputs_<D>_soft.csv (227 rows each).
    """
    fdir = hazard_dir("flood")
    adm1 = adm1 or adm1_path()
    win = flood_window(peak_date(scenario), pre, post)
    start, end = win[0].date(), win[-1].date()
    out_dir = event_cache(scenario["event_id"]) / "bn_inputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    done = sorted(out_dir.glob("flood_inputs_*_soft.csv"))
    if done and not force:
        print(f"  [cache] {len(done)} prep CSVs present in {out_dir} (force=True to rerun)")
        return out_dir
    cmd = ["uv", "run", *_UV_PKGS, "python", "flood_data_prep.py",
           "--date", str(start), "--end-date", str(end),
           "--rp-years", str(rp_years),
           "--forecast-source", forecast_source(scenario, fsource),
           "--soft-evidence", "--adm1", adm1, "--out-dir", str(out_dir)]
    _run(cmd, fdir)
    return out_dir


def run_flood_bn(scenario: dict, in_dir: Path, *, expect: int,
                 cost_loss_ratio=0.20, force=False) -> Path:
    """DBN sequence over the window via run_flood_dbn_window.jl.

    Returns the event output dir (holds dbn/flood_bn_v1_<D>.csv + combined).
    """
    fdir = hazard_dir("flood")
    out_dir = event_cache(scenario["event_id"]) / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / "dbn").exists() and not force:
        print(f"  [cache] BN output present in {out_dir} (force=True to rerun)")
        return out_dir
    # Assert against the prep CSVs that ACTUALLY exist, not the nominal window —
    # the operational ECMWF store is recent-only, so pre-peak days may be absent.
    n_csv = len(list(in_dir.glob("flood_inputs_*_soft.csv")))
    cmd = ["julia", f"--project={fdir}", "run_flood_dbn_window.jl",
           "--input-dir", str(in_dir), "--out-dir", str(out_dir),
           "--expect", str(n_csv or expect)]
    _run(cmd, fdir)
    return out_dir


# --------------------------------------------------------------------------- #
# Drought pipeline (mirrors run_drought_bn_backfill.py per-init steps)
# --------------------------------------------------------------------------- #
def run_drought_prep(scenario: dict, init_month: str, *, rp_years=5,
                     season=None, ensemble_size=51,
                     adm1=None, force=False) -> Path:
    """Soft-evidence drought prep for one monthly init -> one CSV.

    `season` defaults to the operational target season for the init month
    (so the SEAS5 lead stays within 1..6).
    """
    ddir = hazard_dir("drought")
    adm1 = adm1 or adm1_path()
    season = season or season_for_init(init_month)
    out = event_cache(scenario["event_id"]) / "bn_inputs" / f"drought_inputs_{init_month}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not force:
        print(f"  [cache] {out.name} present (force=True to rerun)")
        return out
    cmd = ["uv", "run", *_UV_PKGS, "--with", "pyogrio", "--with", "aiobotocore",
           "python", "drought_data_prep.py",
           "--init-month", init_month, "--target-season", season,
           "--ensemble-size", str(ensemble_size), "--rp-years", str(rp_years),
           "--soft-evidence", "--adm1", adm1, "--out", str(out)]
    _run(cmd, ddir)
    return out


def run_drought_bn(scenario: dict, in_csv: Path, *, tail=True, force=False) -> Path:
    """Julia/RxInfer drought BN on one prep CSV -> one output CSV."""
    ddir = hazard_dir("drought")
    out = event_cache(scenario["event_id"]) / "output" / in_csv.name.replace(
        "drought_inputs", "drought_bn_v1")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not force:
        print(f"  [cache] {out.name} present (force=True to rerun)")
        return out
    cmd = ["julia", f"--project={ddir}", "drought_bn_ibf_v1.jl",
           "--input-csv", str(in_csv), "--output-csv", str(out),
           "--no-agreement"]
    if tail:
        cmd.append("--tail-risk")
    _run(cmd, ddir)
    return out


# --------------------------------------------------------------------------- #
# Reading BN output + comparing to the scenario card values
# --------------------------------------------------------------------------- #
_GID_COLS = ("id", "boundary_id", "gid_1", "GID_1")


def boundary_row(csv_path: Path, gid_1: str) -> pd.Series:
    """Pull the single admin-1 row for this scenario's gid_1 from a CSV."""
    df = pd.read_csv(csv_path)
    for c in _GID_COLS:
        if c in df.columns:
            hit = df[df[c].astype(str) == gid_1]
            if len(hit):
                return hit.iloc[0]
    # fall back to country if the gid is absent (e.g. small-boundary fill)
    raise KeyError(f"gid_1 {gid_1!r} not found in {csv_path.name} "
                   f"(columns: {list(df.columns)[:8]}...)")


def card_vs_computed(scenario: dict, computed: dict[str, str]) -> pd.DataFrame:
    """Side-by-side table: each evidence card's value_by_date vs what the
    notebook recomputed from the ARCO store. `computed` maps card id -> value.
    """
    rows = []
    for card in scenario["evidence_cards"]:
        vbd = card.get("value_by_date", {})
        rows.append({
            "card": card["id"],
            "bn_node": card.get("bn_node", ""),
            "evidence_type": card.get("evidence_type", ""),
            "source": card.get("source", ""),
            "scenario_value": " | ".join(f"{k}: {v}" for k, v in vbd.items()),
            "recomputed": computed.get(card["id"], "— (run the cell above)"),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Soft-bin demonstration (scalar -> evidence-node probability vector)
# --------------------------------------------------------------------------- #
# Labels keyed by the prep modules' SHORT soft_bin node codes, in the order
# `soft_bin()` *returns* (drought reverses cur/trn/tail, so those label lists are
# the physical order reversed to match the returned vector).
FLOOD_NODE_LABELS = {
    "ant":  ["Dry", "Normal", "Wet", "Very_Wet", "Saturated"],
    "exc":  ["Very_Low", "Low", "Medium", "High", "Very_High"],
    "spa":  ["Localized", "Moderate", "Widespread"],
    "trn":  ["Decreasing", "Stable", "Increasing"],
    "tail": ["None", "Low", "Moderate", "High"],
}
DROUGHT_NODE_LABELS = {
    "cur":  ["Above_Normal", "Normal", "Mild_Drought", "Moderate_Drought", "Severe_Drought"],
    "def":  ["Very_Low", "Low", "Medium", "High", "Very_High"],
    "spa":  ["Localized", "Moderate", "Widespread"],
    "trn":  ["Improving", "Stable", "Deteriorating"],
    "tail": ["Nil", "Low", "Moderate", "High"],
}
# short soft_bin code -> the bn_node id used in the scenario evidence_cards.
FLOOD_SHORT2BN = {"ant": "antecedent_rainfall", "exc": "exceedance_prob",
                  "spa": "spatial_coverage", "trn": "rainfall_trend",
                  "tail": "tail_risk"}
DROUGHT_SHORT2BN = {"cur": "cur", "def": "def", "spa": "spa",
                    "trn": "trn", "tail": "tail"}      # drought cards already use short ids


def plot_soft_bin(prep_mod, node: str, value: float, labels: list[str], ax=None):
    """Show how one scalar becomes a probability vector over a node's states.

    Uses the operational `soft_bin()` so the bars match what the BN actually
    ingests on its virtual-evidence channel.
    """
    import matplotlib.pyplot as plt
    vec = prep_mod.soft_bin(value, node)
    if ax is None:
        _, ax = plt.subplots(figsize=(5, 2.6))
    ax.bar(labels, vec, color="#3b7dd8")
    ax.set_title(f"{node}: {value:g}  ->  argmax = {labels[int(vec.argmax())]}")
    ax.set_ylabel("P(state)")
    ax.set_ylim(0, 1)
    for i, v in enumerate(vec):
        if v > 0.02:
            ax.text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)
    return vec


# --------------------------------------------------------------------------- #
# Debrief: EM-DAT loss markdown
# --------------------------------------------------------------------------- #
def emdat_key(scenario: dict) -> str:
    return scenario.get("emdat_event_key", "")
