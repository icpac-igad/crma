"""
CRMA scenario-mode load test (Locust).

Goal: find how many participants can run a scenario act1 -> act3 in parallel
before the Cloud Run stack (frontend + private API) degrades or errors.

Each Locust user = one participant. A user picks a flood or drought scenario
and plays it through the three acts, with realistic think-time between rounds
(reading evidence, answering quiz questions -- which are client-side and make
no server calls). The HTTP calls below are exactly what the browser issues to
the PUBLIC frontend, which proxies to the private API.

Run (headless, target = 50 users, 5/s ramp, 10 min):
    locust -f locustfile.py --headless \
        -u 50 -r 5 -t 10m \
        --host https://crma-frontend-yiyrp6yumq-uc.a.run.app \
        --csv results/run

Run with the web UI (interactive ramp + live charts):
    locust -f locustfile.py --host https://crma-frontend-yiyrp6yumq-uc.a.run.app
    # then open http://localhost:8089

Read DEVELOPMENT note: max-instances is currently 2 on BOTH services. Expect
queueing / 429 / 503 / slow tails well before 50 truly-concurrent users until
that is raised. See README.md.
"""

import os
import random

from locust import HttpUser, LoadTestShape, between, task

from scenarios import (
    DROUGHT_PROFILE,
    FLOOD_PROFILE,
    MANIFEST,
    MDX_RK_SAMPLE,
    TOPOJSON,
)

# Think-time between rounds: a participant reads the evidence and answers the
# Act-I quiz before advancing. Real sessions are tens of seconds per round.
THINK_MIN, THINK_MAX = 4.0, 12.0


class Participant(HttpUser):
    # Locust waits this long between @task selections. Within a task we also
    # sleep explicitly to model per-round reading time.
    weight = 3  # ~3 scenario participants per 1 MDX-stress user (see MdxStress)
    wait_time = between(2, 6)

    def on_start(self):
        # Each VU is one of the two scenario kinds, ~60/40 flood/drought
        # (flood is the heavier path: BN-DAG JSON ~118 KB/day).
        self.profile = FLOOD_PROFILE if random.random() < 0.6 else DROUGHT_PROFILE

    def _think(self):
        import gevent

        gevent.sleep(random.uniform(THINK_MIN, THINK_MAX))

    def _cursor_path(self, template):
        p = self.profile
        keys = p.get("round_dates") or p.get("round_inits")
        return template.format(date=random.choice(keys), init=random.choice(keys))

    @task
    def full_session(self):
        """One complete act1 -> act3 walkthrough."""
        p = self.profile

        # --- Page load: SSR of the scenario route (scenario JSON is bundled) ---
        with self.client.get(
            f"/scenario/{p['event_id']}",
            name="00 page /scenario/[id]",
            catch_response=True,
        ) as r:
            if r.status_code >= 400:
                r.failure(f"page {r.status_code}")

        # Map topojson loads once per session.
        self.client.get(TOPOJSON, name="01 topojson")

        # --- ACT I: what is happening? Calendar + map regions at round 1. ---
        # Quiz (EPS literacy, 9-q template, Q7/Q8 commit) is client-side: think only.
        self.client.get(p["calendar"], name=f"10 calendar ({p['kind']})")
        keys = p.get("round_dates") or p.get("round_inits")
        first = keys[0]
        self.client.get(
            p["regions"].format(date=first, init=first),
            name=f"11 regions ({p['kind']})",
        )
        self._think()  # answer Act I quiz

        # --- ACT II: what do we think is happening? BN-DAG revealed per round. ---
        for key in keys:
            self.client.get(
                p["regions"].format(date=key, init=key),
                name=f"20 regions/round ({p['kind']})",
            )
            self.client.get(
                p["bn_dag"].format(date=key, init=key),
                name=f"21 bn-dag/round ({p['kind']})",
            )
            self._think()  # inspect BN, advance cursor

        # --- ACT III: what should we do and why? Debrief opens RK storyline MDX. ---
        # The debrief resolves its file through the manifest first, then fetches
        # the raw MDX. The manifest is the slow GCS read (~3-4 s cold) -- include
        # it so the test exercises the real MDX failure mode under concurrency.
        with self.client.get(
            MANIFEST, name="29 mdx manifest", catch_response=True
        ) as r:
            if r.status_code >= 400:
                r.failure(f"manifest {r.status_code}")
        with self.client.get(
            p["debrief_mdx"], name=f"30 debrief mdx ({p['kind']})", catch_response=True
        ) as r:
            if r.status_code >= 400:
                r.failure(f"debrief mdx {r.status_code}")
        self._think()  # read your-estimate vs engine-indication comparison


class MdxStress(HttpUser):
    """
    Dedicated MDX-API pressure (the 'failed abruptly' regression).

    A full-session Participant only touches MDX once at the very end, so a pure
    scenario test under-loads the MDX path. This user concentrates load on the
    two MDX endpoints -- the heavy manifest read and per-file raw reads -- to
    find where the API starts shedding (429/503) or timing out on GCS reads.

    Mix it in at a chosen ratio via the --class-picker UI or by weighting, e.g.
        locust -f locustfile.py Participant MdxStress --host ...
    Keep its weight modest; it is meant to surface the MDX ceiling, not to be
    the whole population.
    """

    weight = 1  # vs Participant (default weight 1); raise to bias toward MDX
    wait_time = between(1, 4)

    @task(1)
    def manifest(self):
        with self.client.get(
            MANIFEST, name="MDX manifest", catch_response=True
        ) as r:
            if r.status_code >= 400:
                r.failure(f"manifest {r.status_code}")

    @task(4)
    def raw(self):
        path = random.choice(MDX_RK_SAMPLE)
        with self.client.get(
            f"/api/mdx/raw/{path}", name="MDX raw", catch_response=True
        ) as r:
            if r.status_code >= 400:
                r.failure(f"raw {r.status_code}")


# ---------------------------------------------------------------------------
# Optional step-ladder load shape. Dormant by default (so plain `locust -f`
# runs honour the manual -u/-r). Enable with env LADDER=1 to ramp through
# distinct plateaus -- 5 -> 15 -> 30 -> 50 users -- so the per-level capacity
# is readable in the stats instead of one flat ramp-and-hold. ~10 min total.
# When the shape is active, Locust ignores -u/-r/-t and follows these stages.
# ---------------------------------------------------------------------------
if os.environ.get("LADDER") == "1":

    class StepLadder(LoadTestShape):
        # (cumulative_end_seconds, target_users, spawn_rate)
        stages = [
            (90, 5, 5),    # 0:00-1:30   warm-up, 5 users
            (210, 15, 5),  # 1:30-3:30   15 users
            (360, 30, 5),  # 3:30-6:00   30 users
            (600, 50, 5),  # 6:00-10:00  50 users (the target)
        ]

        def tick(self):
            t = self.get_run_time()
            for end, users, rate in self.stages:
                if t < end:
                    return (users, rate)
            return None  # past last stage -> stop the test
