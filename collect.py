"""Log NSW emergency department waiting counts for every hospital that reports them.

Source: NSW Health "Emergency Department waiting times in major NSW hospitals"
(https://www.emergencywait.health.nsw.gov.au), via the public API the page itself calls.
Run every 15 minutes. Appends one row per hospital to data/YYYY-MM.csv (UTC month).
"""
import csv, json, os, time, urllib.request
from datetime import datetime, timezone

API = "https://rted-web-external.citc.health.nsw.gov.au/api/GetHospitalWaitingDetails/{}"
HEAD = {"User-Agent": "Primara Research ED wait log (research; contact robert@primara.com.au)", "Accept": "application/json"}
FIELDS = ["polled_utc", "hospital_id", "hospital", "lhd", "facility_id", "wait_count", "source_updated_utc",
          "bed_capacity", "usual_patients_this_hour", "usual_month", "usual_day_of_week", "usual_hour", "error"]

def get(url):
    req = urllib.request.Request(url, headers=HEAD)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    hospitals = json.load(open(os.path.join(here, "hospitals.json")))
    now = datetime.now(timezone.utc)
    rows = []
    for h in hospitals:
        row = {"polled_utc": now.strftime("%Y-%m-%d %H:%M"), "hospital_id": h["hospitalID"], "hospital": h["name"], "lhd": h["lhd"]}
        try:
            d = get(API.format(h["hospitalID"]))
            w = (d.get("waitingDetails") or [{}])[0]
            b = (d.get("bedDetails") or [{}])[0]
            u = (d.get("historicalDetails") or [{}])[0]
            row.update(facility_id=w.get("facilityIdentifier") or b.get("facilityIdentifier"), wait_count=w.get("waitCount"),
                       source_updated_utc=w.get("lastUpdatedDate"), bed_capacity=b.get("bedCapacity"),
                       usual_patients_this_hour=u.get("statisticValue") if u.get("statisticIdentifier") == "usual_patients" else None,
                       usual_month=u.get("month"), usual_day_of_week=u.get("dayOfWeek"), usual_hour=u.get("hourOfDay"))
        except Exception as e:
            row["error"] = str(e)[:200]
        rows.append(row)
        time.sleep(0.5)  # be gentle: about 30 seconds per sweep
    os.makedirs(os.path.join(here, "data"), exist_ok=True)
    path = os.path.join(here, "data", now.strftime("%Y-%m") + ".csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new: w.writeheader()
        w.writerows(rows)
    ok = sum(1 for r in rows if not r.get("error"))
    print(f"{now:%Y-%m-%d %H:%M} UTC: {ok}/{len(rows)} hospitals logged to {path}")

if __name__ == "__main__":
    main()
