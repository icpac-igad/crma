#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "papermill", "ipykernel", "jupyter-client", "nbformat",
#   "pandas", "matplotlib", "icechunk", "xarray", "zarr>=3", "dask", "numpy",
#   "geopandas", "regionmask", "netcdf4", "pyarrow", "scipy",
#   "fsspec", "s3fs", "gcsfs", "bottleneck", "pyogrio", "aiobotocore",
# ]
# ///
"""
build_all.py — stamp one executed notebook per scenario into built/.

Run as `./build_all.py ...` (PEP 723 inline deps — uv installs them) or
`uv run --script build_all.py ...`. The deps live in the `# /// script` block
above (not the shebang) to stay under the kernel's 256-byte shebang limit.

For every scenario JSON in `scenario-sim/scenarios/`, picks the matching
template (flood/drought), injects EVENT_ID (plus any CLI overrides) via
papermill, executes it live (ARCO reads + Julia BN), and writes
`built/<event_id>.ipynb`.

The `uv run` shebang pulls the full data stack so the in-notebook ARCO/soft-bin
cells and the subprocess prep both work. Julia must be on PATH for the BN step
(`export PATH="$HOME/.juliaup/bin:$PATH"`).

Examples:
    ./build_all.py                              # all 23, live
    ./build_all.py --only nairobi_flood_2026    # one event
    ./build_all.py --hazard flood               # only flood scenarios
    ./build_all.py --no-run                     # narrate from cache (RUN_LIVE=False)
    ./build_all.py --list                        # list scenarios + chosen template
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import papermill as pm

HERE = Path(__file__).resolve().parent
SCEN = HERE.parent / "scenarios"
BUILT = HERE / "built"
TEMPLATES = {"flood": HERE / "flood_template.ipynb",
             "drought": HERE / "drought_template.ipynb"}


def ensure_kernel() -> str:
    """Register an ipykernel for *this* (uv) Python so papermill can find it.

    The uv-run env is ephemeral and has no kernelspec by default; install one
    into the user dir (HOME is writable) and return its name.
    """
    import jupyter_client.kernelspec as ks
    name = "scenario-nb"
    try:
        ks.KernelSpecManager().get_kernel_spec(name)
        return name
    except Exception:                                            # noqa: BLE001
        from ipykernel import kernelspec as ik
        ik.install(user=True, kernel_name=name, display_name="scenario-nb")
        return name


def scenarios() -> list[tuple[str, str]]:
    """(event_id, hazard) for every scenario JSON."""
    out = []
    for p in sorted(SCEN.glob("*.json")):
        haz = json.loads(p.read_text())["hazard"]
        out.append((p.stem, haz))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="single event_id")
    ap.add_argument("--hazard", choices=["flood", "drought"], help="filter by hazard")
    ap.add_argument("--no-run", action="store_true",
                    help="RUN_LIVE=False — narrate from cache, skip cloud/Julia")
    ap.add_argument("--forecast-source", default="auto")
    ap.add_argument("--list", action="store_true", help="list and exit")
    ap.add_argument("--continue-on-error", action="store_true",
                    help="keep going if one event fails")
    args = ap.parse_args()

    BUILT.mkdir(exist_ok=True)
    todo = scenarios()
    if args.only:
        todo = [(e, h) for e, h in todo if e == args.only]
    if args.hazard:
        todo = [(e, h) for e, h in todo if h == args.hazard]
    if not todo:
        print("no scenarios match the filter", file=sys.stderr); return 1

    if args.list:
        for e, h in todo:
            print(f"  {h:8} {e}  <- {TEMPLATES[h].name}")
        return 0

    if not TEMPLATES["flood"].exists() or not TEMPLATES["drought"].exists():
        print("templates missing — run `python _make_templates.py` first", file=sys.stderr)
        return 1

    kernel = ensure_kernel()
    failures = []
    for i, (event_id, hazard) in enumerate(todo, 1):
        out = BUILT / f"{event_id}.ipynb"
        print(f"\n[{i}/{len(todo)}] {hazard} {event_id} -> {out.name}")
        params = {"EVENT_ID": event_id, "RUN_LIVE": not args.no_run,
                  "FORECAST_SOURCE": args.forecast_source}
        try:
            pm.execute_notebook(str(TEMPLATES[hazard]), str(out),
                                parameters=params, cwd=str(HERE),
                                kernel_name=kernel)
        except Exception as exc:                                     # noqa: BLE001
            print(f"  FAILED: {exc}", file=sys.stderr)
            failures.append(event_id)
            if not args.continue_on_error:
                return 2
    if failures:
        print(f"\n{len(failures)} failed: {failures}", file=sys.stderr)
        return 2
    print(f"\nDone — {len(todo)} notebooks in {BUILT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
