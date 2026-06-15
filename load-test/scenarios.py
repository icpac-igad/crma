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
    "event_id": "kenya_drought_2022",
    "country": "KEN",
    "calendar": "/api/ibf-drought-calendar?country=KEN",
    "round_inits": ["2022-01", "2022-06", "2022-10"],
    "regions": "/api/ibf-drought-regions/{init}",
    "bn_dag": "/api/drought-bn-dag/{init}",
    "debrief_mdx": "/api/mdx/raw/rk/dr-rk-2022-01.mdx",
}

# Shared static asset the DisasterMap loads once (served by the API, ~90 KB).
TOPOJSON = "/icpac_adm1v3.json"
