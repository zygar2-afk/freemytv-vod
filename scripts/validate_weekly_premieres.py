#!/usr/bin/env python3
"""Validate externally verified weekly premiere records before publishing.

This is an OFFLINE evidence checker. It makes no requests to Filmweb.
The source must be supplied by a human review or an authorized feed.
Neither a production year nor a VOD addition-date by itself is proof
of a new-production premiere in the past seven calendar days.
"""
import datetime as dt
import json
import pathlib
import sys
import zoneinfo
from urllib.parse import urlsplit

def valid_url(value):
    if not isinstance(value, str):
        return False
    u = urlsplit(value)
    return u.scheme == "https" and bool(u.hostname)

def validate(feed, today):
    problems = []
    if feed.get("region") != "PL":
        problems.append("Region must be PL")
    for bucket in ("movies", "series"):
        days = 7 if bucket == "movies" else 21
        items = feed.get(bucket)
        if not isinstance(items, list):
            problems.append(bucket + ": missing list")
            continue
        if len(items) > 10:
            problems.append(bucket + ": exceeds TOP 10")
        for i, item in enumerate(items):
            name = f"{bucket}[{i}]"
            if not isinstance(item, dict):
                problems.append(name + ": expected object")
                continue
            if not item.get("title"):
                problems.append(name + ": missing title")
            # Premiere evidence is mandatory and must describe the NEW PRODUCTION,
            # not merely the date an old title appeared in a VOD catalogue.
            evidence = item.get("premiereEvidence")
            if not isinstance(evidence, dict):
                problems.append(name + ": no premiereEvidence")
                continue
            event = evidence.get("event")
            if event not in ("new_movie_premiere", "new_series_premiere", "new_season_premiere", "new_on_vod"):
                problems.append(name + ": invalid event type")
            if event == "new_on_vod":
                if bucket != "series" or item.get("displayCategory") != "NOWO_W_VOD" or item.get("seasonPremiereVerified") is not False:
                    problems.append(name + ": new_on_vod cannot be represented as a confirmed premiere")
                if evidence.get("verifiedByIndependentSource") is not False:
                    problems.append(name + ": candidate provenance flag missing")
            elif evidence.get("checkedBy") == "automated_listing_parser":
                problems.append(name + ": automated listing cannot verify a new season or production premiere")
            if not valid_url(evidence.get("sourceUrl")):
                problems.append(name + ": premiere needs HTTPS evidence URL")
            if not evidence.get("checkedBy") or not evidence.get("checkedAt"):
                problems.append(name + ": premiere evidence lacks review metadata")
            try:
                premiere_date = dt.date.fromisoformat(evidence["premiereDatePL"])
                if not 0 <= (today - premiere_date).days < days:
                    problems.append(name + f": premiere not within {days} days")
            except (KeyError, ValueError, TypeError):
                problems.append(name + ": premiereDatePL missing/invalid")
            providers = item.get("providers")
            if not isinstance(providers, list) or not providers:
                problems.append(name + ": missing Polish VOD provider")
                continue
            if not any(valid_url(p.get("availabilityEvidenceUrl")) and p.get("name") for p in providers if isinstance(p, dict)):
                problems.append(name + ": no provider with verifiable availability URL")
    return problems

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: validate_weekly_premieres.py path/to/feed.json")
    feed = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    today = dt.datetime.now(zoneinfo.ZoneInfo("Europe/Warsaw")).date()
    problems = validate(feed, today)
    print(json.dumps({"datePL":str(today),"validation":"PASS" if not problems else "BLOCKED","errors":problems},ensure_ascii=False,indent=2))
    return 1 if problems else 0

if __name__ == "__main__":
    raise SystemExit(main())
