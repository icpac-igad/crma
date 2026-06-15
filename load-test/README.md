# CRMA scenario-mode load test

Answer one question: **how many participants can run a scenario act1 → act3 in
parallel before the Cloud Run stack degrades or errors?** Initial target: **50**.

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

## If 50 doesn't pass — the levers (in the cloudbuild.yaml deploy args)

Both `crma-api-cr/cloudbuild.yaml` and `crma-fe-cr/cloudbuild.yaml`:

| Lever | Now | Suggested for 50 |
|-------|-----|------------------|
| `--max-instances` | 2 | **10** (FE) / **10** (API) |
| `--min-instances` | 0 | **1** (kills first-burst cold start) |
| `--memory` (API) | 512Mi | **1Gi** (headroom for cached parquet) |
| `--cpu` | 1 | keep 1; scale out, not up |
| `--concurrency` | 40 FE / 80 API | leave; CPU is the limit, not slots |

Re-run the same `locust` command after each change to confirm the curve moves.

## Files
- `locustfile.py` — the virtual-participant act1→act3 journey.
- `scenarios.py` — real flood/drought event profiles (dates, endpoints).
- `results/` — CSV output (`*_stats.csv`, `*_failures.csv`).
