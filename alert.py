"""Post a Slack alert when NSW emergency departments spike.

Runs after each collection. Reads data/*.csv, compares the latest sweep with history.
Spike rules (simple on purpose; tune once there is more history):
- Hospital: waiting is at least 15 AND at least double that hospital's median for the same
  hour of day over the past 14 days (needs 7+ days of history). Before that (first week): waiting >= 1.5 x ED beds and >= 10.
- Statewide: total waiting across all hospitals is at least 1.5 times the median total for the
  same hour of day over the past 14 days (needs 7+ days of history).
Each hospital (and the statewide alert) alerts at most once every 3 hours (data/alert_state.json).
Slack webhook comes from the SLACK_WEBHOOK_URL secret. No webhook: prints alerts only.
"""
import csv, glob, json, os, statistics, urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SYD = timezone(timedelta(hours=11))  # AEDT; good enough for labels Oct to Apr
COOLDOWN = timedelta(hours=3)

def load():
    rows = []
    for p in sorted(glob.glob(os.path.join(HERE, "data", "*.csv"))):
        with open(p) as f:
            for r in csv.DictReader(f):
                if r.get("error") or not r.get("wait_count"):
                    continue
                r["t"] = datetime.strptime(r["polled_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                r["wait"] = int(float(r["wait_count"]))
                r["beds"] = int(float(r["bed_capacity"])) if r.get("bed_capacity") else None
                rows.append(r)
    return rows

def main():
    rows = load()
    if not rows:
        return
    latest_t = max(r["t"] for r in rows)
    latest = [r for r in rows if r["t"] == latest_t]
    hist = [r for r in rows if latest_t - timedelta(days=14) <= r["t"] < latest_t - timedelta(hours=1)]
    days = (latest_t - min(r["t"] for r in rows)).days
    hour = latest_t.astimezone(SYD).hour
    same_hour = [r for r in hist if r["t"].astimezone(SYD).hour == hour]

    state_path = os.path.join(HERE, "data", "alert_state.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    def cooled(key):
        last = state.get(key)
        return not last or latest_t - datetime.fromisoformat(last) >= COOLDOWN

    alerts = []
    for r in latest:
        key = r["hospital"]
        if days >= 7:
            base = [h["wait"] for h in same_hour if h["hospital"] == key]
            med = statistics.median(base) if base else None
            hit = med is not None and r["wait"] >= 15 and r["wait"] >= 2 * max(med, 1)
            why = f"usual for this hour about {med:.0f}" if med is not None else ""
        else:
            hit = bool(r["beds"]) and r["wait"] >= 1.5 * r["beds"] and r["wait"] >= 10
            why = f"{r['beds']} ED beds"
        if hit and cooled(key):
            alerts.append(f"*{r['hospital']}*: {r['wait']} waiting ({why})")
            state[key] = latest_t.isoformat()

    total = sum(r["wait"] for r in latest)
    if days >= 7:
        by_sweep = {}
        for h in same_hour:
            by_sweep[h["t"]] = by_sweep.get(h["t"], 0) + h["wait"]
        if by_sweep:
            med_total = statistics.median(by_sweep.values())
            if total >= 1.5 * med_total and cooled("_statewide"):
                alerts.insert(0, f"*NSW statewide*: {total} waiting across {len(latest)} EDs (usual for this hour about {med_total:.0f})")
                state["_statewide"] = latest_t.isoformat()

    json.dump(state, open(state_path, "w"), indent=1)
    if not alerts:
        print(f"No spikes. Statewide waiting: {total}")
        return
    when = latest_t.astimezone(SYD).strftime("%a %d %b, %I:%M%p").replace(" 0", " ")
    text = f":rotating_light: ED spike alert, {when} Sydney time\n" + "\n".join(alerts) + \
           "\nSource: NSW Health ED waiting times (patients triaged and waiting). Data: github.com/primaraau/ed-wait-log"
    print(text)
    hook = os.environ.get("SLACK_WEBHOOK_URL")
    if hook:
        req = urllib.request.Request(hook, data=json.dumps({"text": text}).encode(), headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=20)

if __name__ == "__main__":
    main()
