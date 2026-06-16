"""
Real scenario profiles used by the load test.

Each profile is one participant's act1 -> act3 journey expressed as the HTTP
calls the browser actually issues against the PUBLIC frontend origin. The
frontend (Next.js) proxies every /api/* call to the private crma-api Cloud Run
with an identity token, so hitting the FE exercises the whole chain:

    Locust VU -> crma-frontend (SSR + proxy) -> crma-api (pandas + GCS) -> GCS

The acts themselves (quiz, Q7/Q8 commit, debrief comparison) are client-side
React + localStorage, so they generate NO server traffic -- they only add
think-time. The server load is the data fetches the runner fires as the user
moves the round cursor (calendar / regions / BN-DAG / debrief MDX).

Dates/init-months below are taken from DEVELOPMENT_LOG.md event windows:
  flood  kenya_nairobi_flood_2024 : daily 2024-04-09 -> 2024-04-23
  drought (KEN)                    : monthly 2022-01 -> 2022-12
"""

# A flood participant: daily cursor across a 3-round (lead -> escalation -> onset)
# window. Country GID prefix drives the server-side calendar groupby.
FLOOD_PROFILE = {
    "kind": "flood",
    "event_id": "kenya_nairobi_flood_2024",
    "country": "KEN",
    "calendar": "/api/ibf-flood-calendar?country=KEN",
    # one cursor per round (Act II reveals BN-DAG; Act I only the calendar/map)
    "round_dates": ["2024-04-11", "2024-04-17", "2024-04-23"],
    "regions": "/api/ibf-flood-regions/{date}",
    "bn_dag": "/api/bn-dag/{date}",
    "debrief_mdx": "/api/mdx/raw/rk/fl-rk-2024-04.mdx",
}

# A drought participant: monthly init cursor (outlook -> deficit+CDI -> confirm).
DROUGHT_PROFILE = {
    "kind": "drought",
    # Real registered slug (see registry.ts). `kenya_drought_2022` does NOT
    # exist — that wrong slug is why the earlier run saw a (correct) 404.
    "event_id": "kenya_asal_drought_2020",
    "country": "KEN",  # gid_1 = KEN.40_1
    "calendar": "/api/ibf-drought-calendar?country=KEN",
    # The scenario's actual round cursors (outlook → deficit+CDI → confirmation).
    "round_inits": ["2020-06", "2020-12", "2022-12"],
    "regions": "/api/ibf-drought-regions/{init}",
    "bn_dag": "/api/drought-bn-dag/{init}",
    "debrief_mdx": "/api/mdx/raw/rk/dr-rk-2020-12.mdx",  # rk_month 2020-12
}

# Shared static asset the DisasterMap loads once (served by the API, ~90 KB).
TOPOJSON = "/icpac_adm1v3.json"

# --- MDX endpoints (the "failed abruptly" concern) -------------------------
# The Act III debrief resolves its storyline file through the manifest, then
# fetches the raw MDX. The manifest is one large JSON (~3000+ files) read from
# GCS on every call -- it is the slow path (~3-4 s cold) and the prime suspect
# for the MDX API failing under concurrency. We exercise both:
#   GET /api/mdx/manifest                 (heavy read, no obvious server cache)
#   GET /api/mdx/raw/{tab}/{filename}     (per-file GCS read)
MANIFEST = "/api/mdx/manifest"

# A spread of REAL rk storyline files (verified present in the live manifest),
# so the dedicated MDX-stress task hits 200s, not 404s -- a load test that
# 404s tells you nothing about MDX serving capacity. Mix of flood + drought so
# different GCS objects are pulled (defeats any per-object edge caching).
MDX_RK_SAMPLE = [
    "rk/fl-rk-1990-0016-TZA.mdx",
    "rk/fl-rk-1990-0352-KEN.mdx",
    "rk/fl-rk-1990-04.mdx",
    "rk/fl-rk-1990-05.mdx",
    "rk/fl-rk-1990-08.mdx",
    "rk/fl-rk-2024-04.mdx",
    "rk/dr-rk-1990-01.mdx",
    "rk/dr-rk-1991-01.mdx",
    "rk/dr-rk-1991-10.mdx",
    "rk/dr-rk-1991-9224-KEN.mdx",
    "rk/dr-rk-1993-11.mdx",
    "rk/dr-rk-2022-01.mdx",
]
