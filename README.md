# CRMA — Continuous Risk Monitoring and Assessment
## Scenario Simulation Exercise

Participants relive a real East African **drought or flood** as it unfolded.
Working only with the evidence available **at the time**, they grade each admin-1
region with a risk colour — the call a Disaster Operations Centre (DOC) has to make.

**End outcome:** every admin-1 marked with a **CRMA colour grade**, justified by the
evidence weighed.

> 🟢 **Monitor**  ·  🟡 **Evaluate**  ·  🟠 **Assess**  ·  🔴 **Actionable Risk**

A date **cursor** is stepped through the event window:

- **Flood** — *daily*, a **~15-day** window (lead → escalation → onset).
- **Drought** — *monthly*, a **multi-month** window (here the **OND** short-rains
  season<sup>†</sup>).

---

### Act I — Understanding the Event · *What is happening?*

The monitoring **calendar/timeline** for the event's window is read (daily for
flood, monthly for drought) to build the situational picture.

![Monitoring calendar](docs/calendar.jpg)

*Monitoring calendar — monthly for drought (shown), daily for flood; each cell
shaded by the share of admin-1s at Actionable Risk.*

### Act II — Evidence Evaluation & Risk Assessment · *What do we think is happening?*

The evidence is classified and weighed — **hard** (what we measure) · **soft** (what
we estimate) · **virtual** (what we imagine). A **Bayesian Network** combines it into
a hidden **risk grade** (Minimal → Extreme, *expert-rules judgment*) and a **CRMA
decision**.

![Per-boundary Bayesian Network](docs/decision_bn.jpg)

*Per-admin-1 BN: evidence nodes (Current SPI-3, Forecast Deficit, Spatial, Trend) →
hidden risk-level grade → CRMA decision (here **Monitor / green**, P(High∪Extreme) = 0%, γ = 0.20).*

### Act III — Decision & Reflection · *What should we do, and why?*

Participants commit a **CRMA colour grade** for each admin-1. The recorded **loss &
damage** is then revealed and compared with their call and with the model.

![Admin-1 risk map](docs/admin1_map.jpg)

*The end outcome — each admin-1 graded green → red on the available evidence
(Risk Monitoring, Dec 2023).*


