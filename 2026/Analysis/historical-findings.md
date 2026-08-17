# Corrected historical draft findings

Source of truth: the corrected Google Sheet, **Past Draft Results - 2020-2025**, read on Aug. 15, 2026.  All earlier history-derived outputs should be treated as superseded by the files in this directory.

## Validation

- All eight seasons contain 17 rounds and 170 draft slots.
- Every season contains 10 distinct managers and 17 picks attributed to each manager.
- Danziger appears only in 2018–2021.  Joshua appears only in 2022–2025.  Their records are not combined.
- Keeper markers are preserved.  Keeper counts range from nine to 17 per season.
- The source includes three empty player slots in 2020 and one in 2025.  These remain empty and are not imputed.
- One 2018 player entry, “Kenneth Barber,” does not reconcile to the nflverse player registry.  It remains UNKNOWN.

## Pick-slot anomalies

The corrected manager labels reveal 56 selections outside the manager's inferred home snake slot: 20 in 2019, 14 in 2020, four in 2021, eight in 2023, eight in 2024, and two in 2025.  There are none in 2018 or 2022.

These are not missing-manager errors: each manager still has 17 picks.  The league owner confirmed that all 56 are picks traded during the previous season.  One traded 2023 selection is marked as a keeper; the other 55 are not.  The sheet does not contain the underlying trade details.

The full audit trail is in [pick_slot_anomalies.csv](generated/pick_slot_anomalies.csv).

## Quarterback scarcity

The league drafted 29–32 quarterbacks every season.

| Season | Total QBs | QB5 pick | QB10 pick | QB15 pick | QB20 pick | QB25 pick |
|---:|---:|---:|---:|---:|---:|---:|
| 2018 | 31 | 28 | 47 | 56 | 89 | 101 |
| 2019 | 29 | 46 | 60 | 69 | 82 | 113 |
| 2020 | 29 | 29 | 43 | 54 | 89 | 115 |
| 2021 | 32 | 17 | 39 | 68 | 82 | 100 |
| 2022 | 31 | 13 | 28 | 34 | 85 | 103 |
| 2023 | 30 | 8 | 34 | 48 | 72 | 102 |
| 2024 | 30 | 10 | 32 | 64 | 85 | 115 |
| 2025 | 30 | 10 | 42 | 61 | 86 | 109 |

From 2022–2025, the median positions were pick 33 for QB10, pick 54.5 for QB15, and pick 85 for QB20.  The QB10 median barely changes when keeper QBs are removed (33.5), so the recent early-QB pattern is not merely a keeper artifact.

There were eight runs of at least three consecutive quarterbacks.  The most aggressive was a five-QB run at picks 28–32 in 2022.  The latest was Lamar Jackson, Josh Allen, and Jalen Hurts at picks 2–4 in 2025.

## Current-manager tendencies

These are descriptive tendencies, not forecasts.  “First live QB” excludes quarterbacks already placed as keepers.

| Manager | Seasons | Avg. QBs | Avg. first QB round | Avg. first live QB round |
|---|---:|---:|---:|---:|
| Ori | 8 | 2.88 | 1.75 | 1.75 |
| Tompkins | 8 | 2.88 | 3.88 | 3.88 |
| Greenspan | 8 | 3.38 | 2.88 | 2.88 |
| Goldberg | 8 | 2.88 | 2.12 | 2.12 |
| Jeff | 8 | 3.38 | 3.25 | 3.75 |
| Joshua | 4 | 3.25 | 1.75 | 1.75 |
| Big Leiber | 8 | 3.12 | 1.75 | 2.25 |
| Barry | 8 | 3.00 | 2.62 | 3.12 |
| Nalick | 8 | 3.00 | 5.00 | 5.12 |
| Abe | 8 | 2.62 | 4.38 | 4.38 |

The sharpest early-QB pressure behind Goldberg's No. 4 slot comes from Joshua and Big Leiber.  Ori is also historically aggressive, but he picks before Goldberg in round one and makes two selections between Goldberg's picks 17 and 24.

Goldberg has historically selected a first QB in round 2.12 on average and a second in round 5.88, with 2.88 total QBs per season.  That history supports taking scarcity seriously, but it does not by itself justify paying above the current market for a specific QB.

## Generated data

- [historical_draft_normalized.csv](generated/historical_draft_normalized.csv)
- [manager_tendencies.csv](generated/manager_tendencies.csv)
- [pick_slot_anomalies.csv](generated/pick_slot_anomalies.csv)
- [positional_runs.csv](generated/positional_runs.csv)
- [historical_draft_analysis.json](generated/historical_draft_analysis.json)

## Limits

- Home slots are inferred by the assignment that best explains each season's corrected labels.
- The sheet does not identify the specific transaction behind a confirmed traded pick.
- Manager samples include only eight drafts, and Joshua has four.  Tendencies should receive modest weight.
- Historical availability cannot be compared with market value until contemporaneous ADP for each season is added.
