# NSW emergency department waiting log

Every 15 minutes, logs the number of patients triaged and waiting for treatment at each of the 60 NSW hospitals that publish it, plus emergency bed numbers and NSW Health's "usual patients" figure for that hour.

- Source: NSW Health, Emergency Department waiting times in major NSW hospitals (https://www.emergencywait.health.nsw.gov.au), through the public API the page calls. Public, aggregate counts only: no patient information.
- Data: `data/YYYY-MM.csv`, one row per hospital per sweep. `source_updated_utc` is when NSW Health last refreshed that hospital; de-duplicate on hospital + source time when analysing. Times are UTC (Sydney is UTC+11 in daylight saving, +10 otherwise).
- What it is not: arrivals, waiting times, or reasons for attending. It's a snapshot of how many people are waiting.
- Started October 2026 by Primara Research. Hospital list in `hospitals.json` (refresh if NSW Health adds hospitals).
