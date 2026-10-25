#!/usr/bin/env python3
"""Generate reproducible synthetic growth events and dashboard metrics."""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DATA = ROOT / "app" / "data"
RAW_DATA = ROOT / "data"
START = date(2026, 1, 1)
END = date(2026, 10, 26)
CHANNELS = ["Meta", "Google", "TikTok", "Affiliate", "Email", "Organic", "Direct"]
PAID = {"Meta", "Google", "TikTok", "Affiliate"}
WEIGHTS = [0.22, 0.23, 0.10, 0.08, 0.11, 0.16, 0.10]
COLORS = {"Meta":"#3b82d0","Google":"#20a783","TikTok":"#111827","Affiliate":"#e4a141","Email":"#8a78e8","Organic":"#66a8ba","Direct":"#a8b3c0"}


def date_range(start: date, end: date):
    for offset in range((end - start).days + 1):
        yield start + timedelta(days=offset)


def median_abs_deviation(values: list[float]) -> float:
    med = statistics.median(values)
    return statistics.median([abs(v - med) for v in values]) or 1.0


def generate(seed: int = 42) -> dict:
    rng = random.Random(seed)
    dates = list(date_range(START, END))
    date_keys = [d.isoformat() for d in dates]
    touchpoints: list[dict] = []
    orders: list[dict] = []
    sessions = defaultdict(lambda: defaultdict(float))
    spend = defaultdict(lambda: defaultdict(float))
    attributed = {model: defaultdict(lambda: defaultdict(lambda: {"orders":0.0,"revenue":0.0})) for model in ("first","last","linear")}

    # Media spend has a mild trend, weekday pattern, and one planted campaign spike.
    base_spend = {"Meta": 3700, "Google": 3200, "TikTok": 1550, "Affiliate": 900}
    for d in dates:
        weekday = d.weekday()
        weekly = 1.12 if weekday in (4,5) else 0.92 if weekday == 0 else 1.0
        growth = 1.0 + ((d - START).days / len(dates)) * 0.08
        for channel, base in base_spend.items():
            value = base * weekly * growth * rng.uniform(0.88, 1.12)
            if d == date(2026, 9, 17) and channel == "Meta":
                value *= 1.85
            spend[d.isoformat()][channel] = round(value, 2)

    # Synthetic customer paths; touchpoint sequences are intentionally multi-channel.
    for i in range(4600):
        user = f"u_{i+1:05d}"
        first_day = rng.choice(dates[:-32])
        path_length = rng.choices([1,2,3,4], [0.18,0.39,0.32,0.11])[0]
        path = [rng.choices(CHANNELS, WEIGHTS)[0]]
        for step in range(1, path_length):
            # Returning sessions often arrive through search or direct traffic.
            path.append(rng.choices(CHANNELS, [0.12,0.30,0.08,0.05,0.15,0.10,0.20])[0])
        path_dates = sorted([first_day + timedelta(days=rng.randint(0, min(24, path_length*7))) for _ in path])
        for j, (channel, event_day) in enumerate(zip(path, path_dates)):
            campaign = f"{channel.lower()}_always_on_{event_day:%Y%m}" if channel in PAID else f"{channel.lower()}_owned_{event_day:%Y%m}"
            medium = {"Meta":"paid_social","Google":"cpc","TikTok":"paid_social","Affiliate":"affiliate","Email":"email","Organic":"organic","Direct":"direct"}[channel]
            touchpoints.append({"event_id":f"e_{i+1:05d}_{j+1}","user_id":user,"event_date":event_day.isoformat(),"channel":channel,"medium":medium,"campaign":campaign,"touch_index":j+1})
            sessions[event_day.isoformat()][channel] += 1

        # Conversion probability is affected by journey length and paid/owned mix.
        paid_touches = sum(channel in PAID for channel in path)
        probability = min(0.56, 0.22 + (0.045 * paid_touches) + (0.035 if path_length > 1 else 0))
        if rng.random() < probability:
            order_day = min(END, path_dates[-1] + timedelta(days=rng.randint(0,8)))
            revenue = round(rng.lognormvariate(7.55, 0.45), 2)  # synthetic INR order value
            customer_type = "New" if rng.random() < 0.68 else "Returning"
            order = {"order_id":f"o_{i+1:05d}","user_id":user,"order_date":order_day.isoformat(),"revenue_inr":revenue,"customer_type":customer_type,"path":path}
            orders.append(order)
            weights = {"first":[(path[0],1.0)],"last":[(path[-1],1.0)],"linear":[(c,1/len(path)) for c in path]}
            for model, shares in weights.items():
                for channel, share in shares:
                    attributed[model][order_day.isoformat()][channel]["orders"] += share
                    attributed[model][order_day.isoformat()][channel]["revenue"] += revenue*share

    # Inject a few identifiable source-quality defects, then quarantine them.
    bad_rows = [
        {"event_id":"bad_missing_utm_1","user_id":"u_bad_01","event_date":"2026-09-02","channel":"Meta","medium":"paid_social","campaign":"","touch_index":1},
        {"event_id":"bad_missing_utm_2","user_id":"u_bad_02","event_date":"2026-09-12","channel":"Google","medium":"cpc","campaign":"","touch_index":1},
        {"event_id":"bad_duplicate_1","user_id":"u_00003","event_date":"2026-02-04","channel":"Meta","medium":"paid_social","campaign":"meta_always_on_202602","touch_index":1},
        {"event_id":"bad_date_1","user_id":"u_bad_03","event_date":"not-a-date","channel":"TikTok","medium":"paid_social","campaign":"tiktok_launch","touch_index":1},
    ]
    if len(touchpoints) > 2:
        # Reuse a real event ID so the duplicate check is demonstrated by the sample.
        bad_rows[2] = {**touchpoints[2], "event_date":"2026-02-04"}
    # Rejected rows are reported but not included in analytics.
    quality_checks = [
        {"label":"Required fields complete","status":"pass","result":f"{len(touchpoints):,} rows checked"},
        {"label":"Paid UTMs present","status":"review","result":"2 rows quarantined"},
        {"label":"Unique event IDs","status":"review","result":"1 duplicate quarantined"},
        {"label":"Valid event dates","status":"review","result":"1 invalid date quarantined"},
        {"label":"Attribution weights reconcile","status":"pass","result":"100% of orders allocated"},
    ]

    daily = {model:[] for model in ("first","last","linear")}
    for model in daily:
        for key in date_keys:
            for channel in CHANNELS:
                daily[model].append({
                    "date":key,"channel":channel,"spend":round(spend[key].get(channel,0),2),
                    "sessions":int(sessions[key].get(channel,0)),
                    "orders":round(attributed[model][key][channel]["orders"],3),
                    "revenue":round(attributed[model][key][channel]["revenue"],2),
                })

    # Cohort matrix based on synthetic first-order month and repeat behavior.
    cohort_rows=[]
    for month_index in range(6):
        cohort_month=date(2026,5+month_index,1).strftime("%b ’26")
        base=max(32, int(460*rng.uniform(0.68,1.22)))
        retention=[100]
        current=100
        for step in range(1,6):
            current=max(8, int(current*rng.uniform(0.58,0.80)))
            retention.append(current if month_index+step<6 else None)
        cohort_rows.append({"cohort":cohort_month,"size":base,"retention":retention})

    # Transparent baseline forecast: trailing weekday averages with a light trend adjustment.
    actual_by_day=[]
    last_model=daily["last"]
    for d in dates:
        rows=[r for r in last_model if r["date"]==d.isoformat()]
        actual_by_day.append({"date":d.isoformat(),"orders":sum(x["orders"] for x in rows),"revenue":sum(x["revenue"] for x in rows)})
    tail=actual_by_day[-56:]
    day_groups=defaultdict(list)
    for row in tail:
        day_groups[date.fromisoformat(row["date"]).weekday()].append(row)
    base_orders={weekday:statistics.mean(x["orders"] for x in rows) for weekday,rows in day_groups.items()}
    base_revenue={weekday:statistics.mean(x["revenue"] for x in rows) for weekday,rows in day_groups.items()}
    forecast=[]
    for offset in range(1,15):
        d=END+timedelta(days=offset); wd=d.weekday()
        adjustment=1+min(0.025, offset*0.001)
        orders_fc=base_orders.get(wd,statistics.mean(x["orders"] for x in tail))*adjustment
        revenue_fc=base_revenue.get(wd,statistics.mean(x["revenue"] for x in tail))*adjustment
        forecast.append({"date":d.isoformat(),"orders":round(orders_fc,1),"revenue":round(revenue_fc,0),"lower":round(orders_fc*.84,1),"upper":round(orders_fc*1.16,1)})

    # A campaign spike is surfaced only when its measured efficiency also drops.
    last_rows=[r for r in daily["last"] if r["date"]>= (END-timedelta(days=60)).isoformat()]
    paid_roas=defaultdict(list)
    for row in last_rows:
        if row["channel"] in PAID and row["spend"]>0:
            paid_roas[row["channel"]].append(row["revenue"]/row["spend"])
    anomalies=[]
    for channel, values in paid_roas.items():
        med=statistics.median(values); mad=median_abs_deviation(values)
        candidates=[]
        for row in last_rows:
            if row["channel"]!=channel or row["spend"]<=0: continue
            ratio=row["revenue"]/row["spend"]
            if row["spend"]>base_spend[channel]*1.55 and ratio<med-0.8*mad:
                candidates.append((row,ratio))
        if candidates:
            row,ratio=min(candidates,key=lambda x:x[1])
            anomalies.append({"date":row["date"],"severity":"High","title":f"{channel} spend/ROAS needs a check","detail":f"Spend rose while attributed ROAS fell to {ratio:.2f}x. Review campaign mix and tracking."})
    if not anomalies:
        anomalies=[{"date":"2026-09-17","severity":"Review","title":"Meta spend spike detected","detail":"Synthetic example: spend rose 85% on one day. Validate conversion and campaign-tag joins before reallocating budget."}]

    # Demo score: each check category with quarantined rows deducts two points.
    review_categories=sum(1 for check in quality_checks if check["status"]=="review")
    quality_score=max(0, 100-(2*review_categories))
    data={
        "asOf":END.isoformat(),"generatedAt":datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),"metadata":{"synthetic":True,"seed":seed,"periodStart":START.isoformat(),"periodEnd":END.isoformat(),"touchpoints":len(touchpoints),"orders":len(orders)},
        "colors":COLORS,"channels":[{"channel":c,"paid":c in PAID} for c in CHANNELS],"daily":daily,
        "attribution":{model:[{"channel":c,"paid":c in PAID,"spend":round(sum(spend[d].get(c,0) for d in date_keys),0),"orders":round(sum(attributed[model][d][c]["orders"] for d in date_keys),1),"revenue":round(sum(attributed[model][d][c]["revenue"] for d in date_keys),0)} for c in CHANNELS] for model in ("first","last","linear")},
        "cohorts":cohort_rows,"forecast":forecast,"anomalies":anomalies,
        "quality":{"score":quality_score,"checks":quality_checks,"quarantinedRows":len(bad_rows)},
        "journeys":[{"id":f"path_{i+1:03d}","customerType":o["customer_type"],"revenue":o["revenue_inr"],"path":[{"channel":c,"paid":c in PAID} for c in o["path"]]} for i,o in enumerate(orders[:12])]
    }
    return data,touchpoints,bad_rows


def main():
    parser=argparse.ArgumentParser(description="Build a synthetic GrowthPulse dashboard snapshot.")
    parser.add_argument("--seed",type=int,default=42)
    args=parser.parse_args()
    APP_DATA.mkdir(parents=True,exist_ok=True); RAW_DATA.mkdir(parents=True,exist_ok=True)
    data,touchpoints,bad_rows=generate(args.seed)
    (APP_DATA/"demo.json").write_text(json.dumps(data,separators=(",",":")),encoding="utf-8")
    # Keep a small readable synthetic source sample in the repository.
    sample=touchpoints[:300]+bad_rows
    with (RAW_DATA/"synthetic_touchpoints_sample.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=["event_id","user_id","event_date","channel","medium","campaign","touch_index"])
        writer.writeheader(); writer.writerows(sample)
    print(f"Generated synthetic snapshot: {APP_DATA/'demo.json'}")
    print(f"Journeys={data['metadata']['orders']:,}; touchpoints={data['metadata']['touchpoints']:,}; quarantined={len(bad_rows)}")


if __name__=="__main__": main()
