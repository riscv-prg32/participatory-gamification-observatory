# A Participatory Gamification Observatory for Programming Education with the PRG32 Ecosystem
Reproducibility artifacts related to the IEEE eScience 2026 INSTIL 2026 Workshop paper "A Participatory Gamification Observatory for Programming Education with the PRG32 Ecosystem" by Raffaele Montella, Simone Boscaglia, and Ricardo Queiros.

## Abstract
Citizen-science infrastructures increasingly support not only environmental observation, but also participatory inquiry into how people learn, create, and use digital technologies. This paper presents the PRG32 Participatory Gamification Observatory, an open infrastructure that enables students and educators to co-design, conduct, inspect, and reuse multi-institution studies of gamified programming education. The Observatory extends the PRG32 RISC-V retro-computing ecosystem with: (i) a consent-aware event schema; (ii) institution-scoped pseudonymisation and disclosure controls; (iii) a transparent quality gate that retains, rather than silently discards, anomalous records; (iv) research APIs and participant-facing dashboards; and (v) a governance workflow through which contributors can propose questions, inspect aggregate results, and request withdrawal. We evaluate deployment feasibility through a reproducible Monte Carlo capacity-planning study covering laboratory, lecture, and open-course settings. Across 500 replicates, a large lecture deployment yields a median of 10,770 quality-passed sessions after three semesters, while an open course exceeds 10,000 after two. We explicitly avoid treating sessions as independent learners: a cluster-aware analysis shows that telemetry volume is a capacity indicator, not a substitute for participant-level power analysis. The contribution is therefore an auditable design and readiness study for a citizen-science observatory, rather than a claim of demonstrated educational effectiveness.

## Alignment with PRG32 main

This artifact describes an **observatory design and capacity-planning study**. It is
not a deployable observatory service. The implementation baseline reviewed here is
[PRG32 main at `6d9b15d`](https://github.com/riscv-prg32/PRG32/tree/6d9b15d3700e8d9401047ef347498719a5273248)
(13 September 2026). Future changes to PRG32 should be checked against that
revision before applying the design to a deployment.

| Capability | PRG32 baseline | Observatory study |
| --- | --- | --- |
| Local game scores | Persistent top-five scores per game, with a player-name prompt; optional sync to a configured Cartridge Store | Potential input to a consent-governed study, not an observatory event feed |
| Performance measurements | On-device performance summaries and optional frame-metrics upload to MetricsServer | Capacity context only; frame samples are not independent learner observations |
| Consent, institution-scoped pseudonymisation, quality gate, research APIs, participant dashboards, governance and withdrawal | No corresponding implementation in PRG32 main | Proposed architecture and simulated assumptions, not deployed features |

The [PRG32 score API](https://github.com/riscv-prg32/PRG32/blob/6d9b15d3700e8d9401047ef347498719a5273248/docs/cartridge_store/score_api.md)
and [metrics reference](https://github.com/riscv-prg32/PRG32/blob/6d9b15d3700e8d9401047ef347498719a5273248/docs/measurement/metrics_api.md)
describe the implemented data paths. Scores use player names, and the optional
metrics stream is for profiling; neither path by itself supplies the study's
consent or pseudonymisation controls. Do not collect participant data for an
observatory study solely by enabling either feature.

## Reproducing the capacity study

The simulation source and its pinned dependencies are in [`sim/`](sim/). From
that directory, install `requirements.txt` and run `python3 observatory_sim.py`
with the default seed 42, 500 replicates, and three semesters. The committed
CSVs in [`sim/results/`](sim/results/) contain the capacity projections used by
this artifact. The pseudonymisation throughput CSV is a local timing proxy using SHA-256
over a fixed key concatenated with a synthetic record. It is not an HMAC
implementation or a PRG32 firmware measurement, and its timings depend on the
host. These
outputs model deployment readiness, not observed educational outcomes.

## Keywords
citizen science, participatory research, serious games, programming education, learning analytics, RISC-V, privacy, reproducibility

## Presentation
The paper will be presented at the [INSTIL - cItizeN Science engagemenT based on Ict soLutions ](https://www.instil-science.eu) co-located with the 22nd IEEE International Conference on eScience [eScience 2026](https://www.escience-conference.org/2026/), which will be held in Naples, September 28th, October 2nd, 2026.

## How to cite
The BibTeX will be available soon.
