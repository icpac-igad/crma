From Forecast to Action: Interactive Simulation for Impact-Based Decision-Making in Hydro-Meteorological Crisis Settings in East Africa

This simulation immerses participants in a drought-flood escalation using Continuous Risk Monitoring and Assessment platform developed under the CRAF'd project at ICPAC. Via JupyterHub/Google colab, participants access ensemble prediction data, hazard thresholds, exposure-vulnerability layers, and CLIMADA impact model from 11 event-based storylines from EM-DAT disaster database across 11 East African countries. Working backward from loss and damage, participants reconstruct the impact-based forecasting chain to identify which signals preceded each crisis. As a simulation exercise, participants assume the roles of stakeholders to evaluate evolving forecast and risk evidence. As storylines escalate, participants assess when anticipatory actions should be initiated through local governance structures and humanitarian actors. Decisions are explored through a Bayesian Network framework encoding the causal logic linking forecast signals, exposure, vulnerability, and action thresholds, illustrating how earlier interventions could reduce loss and damage. The session produces recommendations for co-designing tools that bridge probabilistic forecasting, evidence-based risk assessment, and humanitarian response.

---

## Revised framing (CRMA/evidence-centric — note1 realignment)

*The text above is the abstract as submitted. The implementation has converged on
a crisper, CRMA-centric framing in which hazard and impact modelling (RIM2D, wflow,
CLIMADA) are treated as supporting science used to build the historical storylines,
rather than as components participants must operate during the exercise.*

> An interactive scenario simulation environment built on the Continuous Risk
> Monitoring and Assessment (CRMA) framework. Participants replay historical
> hydro-meteorological events as they unfold in time, evaluate evolving forecast and
> observation evidence, observe Bayesian risk-state updates, and make anticipatory
> action and disaster-risk-management decisions under uncertainty. It serves both as
> a training environment for CRMA operational workflows and as a simulation exercise
> for exploring forecast-to-action pathways and missed opportunities in DRM.

Three modules: **Scenario Library** (historical drought/flood events) · **CRMA
Engine** (Bayesian evidence updating + risk-state transitions) · **Decision
Simulator** (anticipatory action / DRM decision logging with debrief).

