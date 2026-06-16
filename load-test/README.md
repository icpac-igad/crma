# CRMA scenario-mode load test

Answer one question: **how many participants can run a scenario act1 → act3 in
parallel before the Cloud Run stack degrades or errors?** Initial target: **50**.

## Results so far (2026-06-16)

The first ladder run did **not** measure capacity — it exposed a functional bug:
the FE proxied to the private API with an identity token Cloud Run rejected
(`&format=full`), so 66% of requests failed (401→500/401), not from load. After
the fix (`arco-ibf` `6fb07d8`, Cloud Build `2fbfc145`) the **same** ladder is
clean and now measures real capacity:

| | Pre-fix | Post-fix |
|---|---|---|
| Failures | 3,778 / 5,711 (**66%**) | **0 / 4,972 (0.0%)** |
| 429 / 503 | 0 | 0 |
| p99 latency | 150 ms* | 13 s |

\* misleading — pre-fix 2/3 of requests failed *fast* (~50 ms, no work). Post-fix
every request succeeds and does the real GCS + pandas work, so latency is now the
honest signal. Per ladder level (current `max=2 / min=0`):

- **≤ 25 users:** comfortable, p95 < 0.5 s.
- **30–45 users:** tail blows out to ~2.7–3.2 s — CPU-bound groupby on 2 × 1-vCPU
  plus `min-instances=0` cold starts during scale-up.
- **50 users:** recovers (p95 1.1 s) once both instances are warm.

**Verdict at 50: functional PASS** (zero errors, no overload). Performance is
marginal only for a *synchronized* burst — addressed by the scaling levers below.

## Why Locust (not Selenium)

| Tool | What it drives | Cost for 50 users | Use here |
|------|----------------|-------------------|----------|
| **Locust** (chosen) | HTTP requests (Python, web UI, ramps, CSV) | tiny — 50–500 VUs on a laptop | **capacity / load** |
| Playwright | a real headless browser | ~300–700 MB RAM **each** → 50 = 15–35 GB | a few sessions to confirm the JS flow still works under load |
| Selenium | a real browser, older API | same RAM cost, slower | not recommended |
| k6 | HTTP (JS, very efficient) | tiny | great, but not Python |

The scenario **acts are client-side** (quiz, Q7/Q8 commit, debrief comparison
are React + `localStorage`) — they make **no** server calls. The only server
load is the data the runner fetches as the round cursor moves: calendar →
regions → BN-DAG → debrief MDX. Locust replays exactly those calls against the
**public frontend**, which proxies to the private API — so one tool exercises
the whole chain. Browser automation would spend 99% of its cost rendering React
that never touches Cloud Run. Keep a 2–3 session Playwright smoke for *functional*
"does it complete act1→act3", and use Locust for *volume*.

## The stack you are testing (from the deploy configs)

```
Locust VU ──HTTP──▶ crma-frontend (public)  ──identity-token proxy──▶ crma-api (private) ──▶ GCS
                    512Mi · 1 CPU · max 2                              512Mi · 1 CPU · max 2
                    concurrency 40                                     concurrency 80
                    min-instances 0  (cold start)                      min-instances 0  (cold start)
```

**The binding constraint is `max-instances = 2` on both services**, plus
`min-instances = 0` (cold start on the first burst). Measured cold-start latency
on the live FE: `/api/ibf-flood-calendar?country=KEN` took **9.1 s** (server-side
parquet groupby), `bn-dag` returns ~118 KB JSON. With only 2 instances × 1 CPU
doing SSR + proxy + pandas, a simultaneous burst of 50 will queue.

## Run it

```bash
cd load-test
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
mkdir -p results

# Headless, ramp to 50 over 10s, hold 10 min, write CSVs:
locust -f locustfile.py --headless -u 50 -r 5 -t 10m \
  --host https://crma-frontend-yiyrp6yumq-uc.a.run.app \
  --csv results/run50

# Or interactive (recommended first time) — live charts, manual ramp:
locust -f locustfile.py --host https://crma-frontend-yiyrp6yumq-uc.a.run.app
# open http://localhost:8089
```

## How to read it (step-ladder method)

Don't start at 50. Ramp in steps and watch where it breaks:

1. **5 users** — baseline. Everything green, p95 a few seconds (cold start once).
2. **15 users** — should still be clean if instances stayed warm.
3. **30 users** — watch p95 latency and failure %.
4. **50 users** — the target. Then push to **75 / 100** to find the ceiling.

**Pass/fail thresholds (suggested):**
- failure rate **< 1 %** (any 429/503/timeout counts)
- p95 latency **< 5 s** for data calls, **< 3 s** for the page
- no API instance restarts (check Cloud Run logs for OOM — 512 Mi caches several
  parquet frames; the heavy boundary parquets can push it).

**Where it will break first (predictions to confirm):**
- `429 Too Many Requests` / `503` once concurrent requests exceed
  `2 × concurrency` (FE 80, API 160) — but CPU saturates earlier.
- Long p99 tails from cold starts whenever traffic dips and instances scale to 0.
- Possible API OOM at 512 Mi when flood + drought boundary parquets are all cached.

## The current limitation with `max-instances = 2`

The post-fix run shows the ceiling is **compute, not request slots**. FE
(2 × concurrency 40 = 80) and API (2 × 80 = 160) request slots were never
exhausted — that's why there are **zero 429/503**. What saturates is the
**2 vCPUs** (2 instances × 1 CPU) doing the CPU/IO-bound work: the calendar
server-side `groupby`, the per-row region serialization, and the ~118 KB/day
BN-DAG JSON reads from GCS. Above ~25 concurrent *active* requests those 2 vCPUs
queue, so the system degrades by **latency tail**, not errors. `min-instances=0`
adds 9–13 s cold-start spikes whenever it scales from zero. So `max=2` can carry
50 *functionally*, but the tail is multi-second during scale-up and bursts.

### Levers (in the two `cloudbuild.yaml` deploy args)

`crma-api-cr/cloudbuild.yaml` and `crma-fe-cr/cloudbuild.yaml`:

| Lever | Now | For a comfortable 50 / reach 100 |
|-------|-----|------------------|
| `--min-instances` | 0 | **1** — biggest single win (kills cold starts) |
| `--max-instances` | 2 | **≥ 4** (FE + API) for burst headroom |
| `--cpu` | 1 | **2** — the groupby/serialize work is CPU-bound |
| `--memory` (API) | 512Mi | **1Gi** — headroom for cached parquet |
| `--concurrency` | 40 FE / 80 API | leave; CPU is the limit, not slots |

## Rebuilding & scaling — important interaction

**Scaling lives in the `cloudbuild.yaml` deploy step, and a rebuild re-applies
it.** This bit you once before, so make it deliberate:

- **Permanent change** → edit `--max-instances` / `--min-instances` / `--cpu` /
  `--memory` in the two `cloudbuild.yaml` files, then redeploy:
  `cd cno-e4drr/devops/crma-fe-cr && bash _build_fe.sh` (and `crma-api-cr` for the
  API). The FE build also patches `output: 'standalone'` into `next.config.js` and
  relies on `typescript.ignoreBuildErrors` — `_build_fe.sh` handles both.
- **Temporary bump (no rebuild)** → `gcloud run services update crma-frontend
  --region=us-central1 --min-instances=1 --max-instances=4 --cpu=2 --memory=1Gi`
  (and `crma-api`). Applies in seconds — but the **next `_build_*.sh` rebuild
  resets it to the `cloudbuild.yaml` values.** (That is exactly why the
  `2fbfc145` deploy reverted the earlier `min=1/max=5` bump back to `min=0/max=2`.)

Re-run the same `locust` ladder after each change to confirm the curve moves.

## Files
- `locustfile.py` — the virtual-participant act1→act3 journey.
- `scenarios.py` — real flood/drought event profiles (dates, endpoints).
- `results/` — CSV output (`*_stats.csv`, `*_failures.csv`).
