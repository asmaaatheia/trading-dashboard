# Statistical SL/TP Variant Test

- Scope: 2026-05-25 to 2026-05-29, Friday-to-Monday carryover excluded.
- MT5 trades: 362
- MT5 scoped PnL: 23.44
- MT5 ending equity basis: 101392.09

| Variant | SL basis | TP basis | SL | TP | Trades | PnL | Ending equity | PF | Max DD |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| Original | Original settings | Original settings | 250 | 350 | 362 | 4.17 | 101372.82 | 1.0084 | 50.67 |
| A | winner MAE 85% | winner MFE 70% | 185 | 375 | 362 | -25.56 | 101343.09 | 0.9438 | 70.95 |
| B | winner MAE 90% | winner MFE 75% | 205 | 380 | 362 | -11.80 | 101356.85 | 0.9752 | 73.36 |
| C | winner MAE 95% | winner MFE 75% | 220 | 380 | 362 | -11.41 | 101357.24 | 0.9767 | 71.29 |
| D | winner MAE 95% | winner MFE 80% | 220 | 385 | 362 | -17.46 | 101351.19 | 0.9646 | 74.26 |
| E | all-trade MAE 75% | winner MFE 75% | 255 | 380 | 362 | 2.42 | 101371.07 | 1.0047 | 53.12 |
| F | original SL | winner MFE 75% | 250 | 380 | 362 | 9.36 | 101378.01 | 1.0184 | 50.11 |
| G | winner MAE 95% | original TP | 220 | 350 | 362 | -9.40 | 101359.25 | 0.9803 | 70.27 |

Best statistical variant by replay PnL: F (250/380) with PnL 9.36.
Original replay PnL: 4.17.
The best statistical variant improved versus original in this replay.
