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

import random

from locust import HttpUser, between, task

from scenarios import DROUGHT_PROFILE, FLOOD_PROFILE, TOPOJSON

# Think-time between rounds: a participant reads the evidence and answers the
# Act-I quiz before advancing. Real sessions are tens of seconds per round.
THINK_MIN, THINK_MAX = 4.0, 12.0


class Participant(HttpUser):
    # Locust waits this long between @task selections. Within a task we also
    # sleep explicitly to model per-round reading time.
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
        self.client.get(p["debrief_mdx"], name=f"30 debrief mdx ({p['kind']})")
        self._think()  # read your-estimate vs engine-indication comparison
