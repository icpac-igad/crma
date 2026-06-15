# CRMA scenario load test — results (2026-06-15)

Target: `https://crma-frontend-yiyrp6yumq-uc.a.run.app/scenario`
Harness: Locust step-ladder (`LADDER=1`), classes `Participant` + `MdxStress`,
plateaus 5 → 15 → 30 → 50 users over ~10 min. Raw output in `results/`.

## Headline

- **Capacity at 50 users: PASS.** 5,711 requests, p50 **47 ms**, p95 **120 ms**,
  p99 150 ms, max 930 ms. **No 429/503 anywhere** — the 2×instance / concurrency-40
  (FE) + concurrency-80 (API) setup carried the request volume without overload.
- **Correctness: FAIL.** 3,778 / 5,711 (66%) of requests failed, but **none from
  load** — every failure reproduces on a *single* `curl`, at 1 user. The load
  test surfaced pre-existing functional breakage in the live deploy, not a
  capacity ceiling.

## Per-endpoint result

| Endpoint (Locust name)        | Reqs | Fail % | Status | Note |
|-------------------------------|-----:|-------:|--------|------|
| 01 topojson                   |  327 |   0%   | 200 | static asset, fine |
| 10 calendar (flood)           |  179 |   0%   | 200 | works |
| 29 / MDX manifest             |  683 |   0%   | 200 | FE-handled, works |
| 30 debrief mdx (flood+drought)|  298 |   0%   | 200 | **pre-rendered scenario files work** |
| 00 page /scenario/[id]        |  327 |  45%   | **404** | flood page OK; `kenya_drought_2022` 404s |
| 10 calendar (drought)         |  148 | 100%   | **500** | server error |
| 11/20 regions (flood+drought) | 1416 | 100%   | **500** | server error |
| 21 bn-dag (flood+drought)     |  937 | 100%   | **500** | server error |
| MDX raw (general files)       | 1548 |  83%   | **401** | non-pre-rendered MDX + all media |

## Three distinct defects (load-independent)

1. **IBF data endpoints 500.** `ibf-flood-regions/{date}`, `ibf-drought-regions/{init}`,
   `bn-dag/{date}`, `drought-bn-dag/{init}`, and `ibf-drought-calendar` all 500 on
   every request. `ibf-flood-calendar?country=KEN` (same boundary parquet) **works**,
   so the parquet loads — the 500 is downstream (likely a NaN→`int()`/`float()` row
   conversion in the region serializer, or missing bn-dag JSON / drought parquet in
   GCS). **Needs Cloud Run logs to pin** (`gcloud logging read`), unavailable in this
   env.
2. **MDX raw + media 401 ("the MDX API failing abruptly").** `/api/mdx/raw/*` and
   `/api/mdx/media/*` return a **Google GFE 401** (request hit the *private* API with
   no identity token) for everything **except** the handful of pre-rendered scenario
   debrief files (`fl-rk-2024-04`, `dr-rk-2022-01` → 200, confirmed not a cache
   artifact via cache-buster). Effect in normal use: a debrief's text loads, but any
   **image/video referenced inside the MDX (`/api/mdx/media/*`) is 401 → media breaks**.
   Root cause is in the FE route handlers / `next.config` rewrites (arco-ibf), which
   were not available in this environment to inspect.
3. **Drought scenario pages 404.** `/scenario/kenya_drought_2022` (and variants) 404;
   `/scenario/kenya_nairobi_flood_2024` works. The drought event pages appear not to
   be generated/deployed in the live FE.

## Conclusion

The 50-user target is **not** capacity-bound — latency stayed flat with zero
overload errors. The blocker is that the **live deployment is functionally broken**
for the drought path, the IBF region/bn-dag endpoints, and general MDX/media. These
are almost certainly fixed by redeploying the current committed API + FE code
(several commits are local-only per `scenario-sim/DEVELOPMENT_LOG.md`), then re-running
this ladder to confirm clean. Re-run with:

    cd load-test && . .venv/bin/activate
    LADDER=1 locust -f locustfile.py --headless Participant MdxStress \
      --host https://crma-frontend-yiyrp6yumq-uc.a.run.app \
      --csv results/ladder --html results/ladder.html
