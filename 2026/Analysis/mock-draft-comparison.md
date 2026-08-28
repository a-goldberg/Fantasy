# Mock draft comparison

Generated from 15 nonpartial screenshots, representing 14 unique rosters, and the current 2026-08-27 Draft Room data.

## Method

- Projected-points score: best legal offensive lineup (2 QB, 2 RB, 3 WR, 1 TE, 1 RB/WR/TE flex) using the league-specific DraftSheets PTS column.
- Projection source: the Aug. 26 DraftSheets sheet configured for this league's 10-team, non-PPR, two-QB scoring.
- Market score: sum of the 14 best current consensus two-QB ADPs on each offensive roster. The current board combines Fantasy Football Calculator and FantasyPros market data. Lower is better. Fourteen normalizes the one early 15-of-17 screenshot.
- Illustrative balanced index: 50% projected-points percentile, 30% ADP percentile, 10% lower starter injury risk, and 10% bye-week coverage. These weights are useful, not objectively correct.
- Kicker and defense are excluded from projected-points and ADP comparisons because they are not covered comparably by the offensive projection source.
- `mock_results2.png` is a 15-of-17 screenshot, but it contains a complete nine-player offensive starting lineup and 14 offensive players, so it remains comparable under the normalized measures.
- `mock_results15-draftkick-20260827.png` duplicates the roster in `mock_results11-draftkick-20260827.png`; it is retained in the audit but counted once in rankings and trends.

## Overall ranking

| Rank | Mock | Simulator | Starter pts | ADP sum | Injury risk | Bye failures | Index |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | mock_results9-draftkick.png | DraftKick | 1489.0 | 852.0 | 68.6 | 1 | 72.3 |
| 2 | mock_results4.png | Unlabeled | 1533.0 | 932.8 | 67.1 | 1 | 68.5 |
| 3 | mock_results7-fantasyguru.png | FantasyGuru | 1510.0 | 914.1 | 71.9 | 1 | 66.9 |
| 4 | mock_results14-fantasyguru-20260827.png | FantasyGuru | 1497.0 | 897.4 | 76.4 | 1 | 66.9 |
| 5 | mock_results13-fantasyguru-20260827.png | FantasyGuru | 1498.0 | 933.2 | 74.6 | 0 | 60.4 |
| 6 | mock_results10-draftkick-20260827.png | DraftKick | 1478.0 | 899.6 | 64.8 | 1 | 59.2 |
| 7 | mock_results6-draftkick.png | DraftKick | 1453.0 | 891.4 | 62.3 | 1 | 54.6 |
| 8 | mock_results11-draftkick-20260827.png | DraftKick | 1486.0 | 923.4 | 63.7 | 2 | 50.8 |
| 9 | mock_results2.png | Unlabeled | 1444.0 | 900.0 | 59.4 | 1 | 40.8 |
| 10 | mock_results5-RB,QB,WR,WR.png | Unlabeled | 1466.0 | 964.6 | 64.7 | 0 | 40.4 |
| 11 | mock_results8-fantasyguru.png | FantasyGuru | 1409.0 | 888.9 | 65.7 | 1 | 38.5 |
| 12 | mock_results8-draftkick.png | DraftKick | 1449.0 | 911.5 | 77.2 | 1 | 32.3 |
| 13 | mock_results12-fantasyguru-20260827.png | FantasyGuru | 1457.0 | 933.6 | 68.1 | 1 | 32.3 |
| 14 | mock_results3 vs wr heavy league.png | Unlabeled | 1432.0 | 957.4 | 66.6 | 1 | 16.2 |

## Metric leaders

- Highest projected starting lineup: **mock_results4.png** (1533.0 points).
- Strongest current ADP roster: **mock_results9-draftkick.png** (normalized ADP sum 852.0).
- Best illustrative balanced index: **mock_results9-draftkick.png** (72.3).

## Change over time

- Earlier set (8 unique rosters, through mock_results9-draftkick.png): 1467.0 average starter points; 912.6 average ADP sum; 49.8 average index.
- Aug. 27 QA set (6 unique rosters): 1477.5 average starter points; 916.5 average ADP sum; 50.3 average index.
- Change: +10.5 starter points; +3.8 ADP sum (lower is better); +0.5 index points.
- Spearman time correlation: projected points 0.34; balanced score 0.17.

A positive correlation suggests later mocks improved; a value near zero suggests randomness; a negative value suggests later mocks weakened on that measure. With only 14 unique rosters, treat this as directional evidence, not proof.

## Simulator averages (unique rosters)

| Simulator | N | Starter pts | ADP sum | Index |
|---|---:|---:|---:|---:|
| DraftKick | 5 | 1471.0 | 895.6 | 53.8 |
| FantasyGuru | 5 | 1474.2 | 913.4 | 53.0 |
| Unlabeled | 4 | 1468.8 | 938.7 | 41.5 |

## Extraction audit

| Mock | Roster | Offense | Positions | Projection coverage | Note |
|---|---:|---:|---|---:|---|
| mock_results2.png | 15 | 14 | DST 1, QB 3, RB 5, TE 1, WR 5 | 9/9 | 15-of-17 snapshot |
| mock_results3 vs wr heavy league.png | 17 | 15 | DST 1, K 1, QB 3, RB 6, TE 1, WR 5 | 9/9 |  |
| mock_results4.png | 17 | 15 | DST 1, K 1, QB 3, RB 5, TE 1, WR 6 | 9/9 |  |
| mock_results5-RB,QB,WR,WR.png | 17 | 15 | DST 1, K 1, QB 3, RB 4, TE 2, WR 6 | 9/9 |  |
| mock_results6-draftkick.png | 17 | 15 | DST 1, K 1, QB 3, RB 5, TE 1, WR 6 | 9/9 |  |
| mock_results7-fantasyguru.png | 17 | 15 | DST 1, K 1, QB 3, RB 5, TE 1, WR 6 | 9/9 |  |
| mock_results8-fantasyguru.png | 17 | 15 | DST 1, K 1, QB 3, RB 5, TE 1, WR 6 | 9/9 |  |
| mock_results9-draftkick.png | 17 | 15 | DST 1, K 1, QB 3, RB 5, TE 1, WR 6 | 9/9 |  |
| mock_results8-draftkick.png | 17 | 15 | DST 1, K 1, QB 3, RB 6, TE 1, WR 5 | 9/9 |  |
| mock_results10-draftkick-20260827.png | 17 | 15 | DST 1, K 1, QB 3, RB 5, TE 1, WR 6 | 9/9 |  |
| mock_results11-draftkick-20260827.png | 17 | 15 | DST 1, K 1, QB 3, RB 5, TE 1, WR 6 | 9/9 |  |
| mock_results12-fantasyguru-20260827.png | 17 | 15 | DST 1, K 1, QB 3, RB 5, TE 1, WR 6 | 9/9 |  |
| mock_results15-draftkick-20260827.png | 17 | 15 | DST 1, K 1, QB 3, RB 5, TE 1, WR 6 | 9/9 | Duplicate of mock_results11-draftkick-20260827.png |
| mock_results13-fantasyguru-20260827.png | 17 | 15 | DST 1, K 1, QB 3, RB 4, TE 2, WR 6 | 9/9 |  |
| mock_results14-fantasyguru-20260827.png | 17 | 15 | DST 1, K 1, QB 3, RB 5, TE 1, WR 6 | 9/9 |  |
