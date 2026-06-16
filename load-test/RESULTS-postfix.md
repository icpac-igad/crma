# CRMA scenario load test — POST-FIX results (2026-06-16)

Re-run of the step-ladder (5 → 15 → 30 → 50 users, ~10 min, classes
`Participant` + `MdxStress`) **after the FE↔API authentication fix was
deployed**. Compare against the pre-fix baseline in [`RESULTS.md`](RESULTS.md).
Raw output: `results/ladder_postfix.*`.

## What changed since the baseline

The live frontend image was stale (pre-fix). The deployed fix:

1. **Identity-token proxy corrected.** The old `next.config.js` rewrite was a
   dumb proxy that forwarded `/api/*` to the **private** API *without* an
   identity token → Google GFE `401`/`403` (and `500` where the FE handler
   swallowed the error). Replaced with **Next.js API route handlers using
   `apiFetch()`** that attach the token; the rewrite is now **local-dev-only**.
   This is exactly the "live image is stale vs. the local-only commits" cause
   inferred in `RESULTS.md`.
2. **`&format=full` removed** from the token audience/verify path — that
   parameter was the root cause of the token failing to verify.
3. **`output: 'standalone'`** is patched in at build time by `_build_fe.sh`
   (kept out of the committed `next.config.js` because it breaks local HMR);
   the build also relies on `typescript.ignoreBuildErrors: true`. A rebuild
   that skips the `sed` patch ships an image with no `server.js` and won't
   start — so the patch must be present.
4. **Fail-loud** behaviour: `mdx/media` now returns an honest `404` (was a
   disguised `401`) when an asset genuinely isn't in the bucket — the request
   now reaches the API authenticated.

## Headline: correctness fixed, capacity now measurable

| | Pre-fix ([`RESULTS.md`](RESULTS.md)) | Post-fix (this run) |
|---|---|---|
| Total requests | 5,711 | 4,972 |
| **Failures** | **3,778 (66%)** | **0 (0.0%)** |
| 429 / 503 (overload) | 0 | 0 |
| p50 | 47 ms | 170 ms |
| p95 | 120 ms | 1.5 s |
| p99 | 150 ms | 13 s |
| max | 930 ms | 22 s |

**Every previously-broken endpoint now passes 100%** — drought
calendar/regions, flood & drought `bn-dag`, general MDX `raw`, and the drought
scenario page (with the corrected `kenya_asal_drought_2020` slug + real
cursors `2020-06 → 2020-12 → 2022-12`).

The latencies went **up**, and that is the expected, healthy result: pre-fix,
2/3 of requests failed *fast* (~50 ms `401`/`500` with no work). Now every
request actually succeeds — reading parquet/JSON from GCS, running the pandas
groupby, returning real payloads (`bn-dag` ~118 KB, regions 37–80 KB). So this
is the **first run that measures true capacity**.

## Capacity by user level (the real answer to "how many in parallel")

| Users | req/s | fail/s | p50 | p95 | p99 |
|------:|------:|-------:|----:|----:|----:|
| 5  | 1.5 | 0 | 100 ms | 300 ms | 300 ms |
| 15 | 3.9 | 0 | 110 ms | 200 ms | 300 ms |
| 25 | 4.5 | 0 | 150 ms | 440 ms | 540 ms |
| **30** | 9.1 | 0 | 290 ms | **2.8 s** | **3.2 s** |
| 40 | 7.7 | 0 | 350 ms | 2.7 s | 2.8 s |
| 50 | 13.3 | 0 | 260 ms | 1.1 s | 1.3 s |

- **Up to ~25 users: comfortable.** p95 < 0.5 s, snappy.
- **30–45 users: the tail blows out** to ~2.7–3.2 s p95/p99. The 2×(1 vCPU,
  512 Mi, min-instances 0) stack is CPU-bound on the pandas groupby + GCS
  reads, and `min-instances=0` cold starts (the calendar groupby was ~9 s cold)
  add multi-second stalls — these drive the aggregate p99 13 s / max 22 s seen
  during the ramp transitions.
- **50 users: recovers** (p95 1.1 s, throughput 13 req/s) once both instances
  warmed and the per-instance parquet cache filled.

## Verdict for the 50-participant target

- **Functionally: PASS.** 50 concurrent users, **zero errors, no 429/503** —
  the stack does not shed load at the target.
- **Performance: marginal on current settings.** Self-paced arrival (people
  drifting in) → fine, low duty cycle. A **synchronized workshop burst**
  ("everyone click Start") → first-clicks eat cold starts and the 30–45 band
  shows 2–3 s tails. Usable but janky.

**Recommended (all in the two `cloudbuild.yaml` deploy args, not the build
scripts):** `--min-instances=1` (kills the cold-start stalls — biggest win),
`--max-instances≥4`, and bump the API to `--cpu=2 --memory=1Gi` (the groupby is
CPU-bound; 1 Gi also de-risks OOM on the boundary-parquet cache). Re-run this
ladder after to confirm the tail flattens.

## Re-run command

    cd load-test && . .venv/bin/activate
    LADDER=1 locust -f locustfile.py --headless Participant MdxStress \
      --host https://crma-frontend-yiyrp6yumq-uc.a.run.app \
      --csv results/ladder_postfix --csv-full-history --html results/ladder_postfix.html
