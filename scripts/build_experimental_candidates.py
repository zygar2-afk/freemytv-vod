#!/usr/bin/env python3
"""Generate a NON-PRODUCTION candidate catalog from the visible VOD listing.

This is a diagnostic artifact only. Neither dates nor platform availability
have been independently confirmed; no Filmweb scores are imported.
"""
import datetime as dt
import json
import pathlib
import re
import urllib.request
import zoneinfo

from inspect_vod_markup import CardInspector, candidates_from_cards
import probe_vod_source as source

OUTPUT = pathlib.Path("out/experimental_vod_candidates.json")

def build():
    # Check source robots rules before a single bounded listing fetch.
    source.probe()
    req = urllib.request.Request(source.SOURCE, headers={
        "User-Agent": source.USER_AGENT, "Accept": "text/html"
    })
    with urllib.request.urlopen(req, timeout=15) as response:
        if "text/html" not in response.headers.get("Content-Type", "").lower():
            raise RuntimeError("Unexpected content type")
        body = response.read(source.MAX_BYTES + 1)
        if len(body) > source.MAX_BYTES:
            raise RuntimeError("Source HTML exceeds size cap")
    parser = CardInspector()
    parser.feed(body.decode("utf-8", "replace"))
    today = dt.datetime.now(zoneinfo.ZoneInfo("Europe/Warsaw")).date()
    groups = {}
    for candidate in candidates_from_cards(parser.cards):
        date = dt.date.fromisoformat(candidate["vodAddedAt"])
        if not 0 <= (today - date).days <= 6:
            continue
        links = candidate.get("filmwebLinkCandidates", [])
        if len(links) != 1:
            continue
        match = re.search(r"-([0-9]+)$", links[0])
        if not match:
            continue
        film_id = match.group(1)
        entry = groups.setdefault(film_id, {
            "filmwebId": film_id, "filmwebUrl": links[0],
            "title": candidate["title"], "providers": [],
            "datesAdded": [], "status": "CANDIDATE_UNVERIFIED",
            "ratingVerifiedByFilmweb": False,
            "editorialRecommendationVerified": False,
        })
        if entry["title"].strip().casefold() != candidate["title"].strip().casefold():
            raise RuntimeError("Title mismatch for Filmweb ID " + film_id)
        association = {"name": candidate["provider"],
                       "vodAddedAt": candidate["vodAddedAt"],
                       "outsideSubscriptionLabelPresent": candidate["outsideSubscriptionLabelPresent"]}
        if association not in entry["providers"]:
            entry["providers"].append(association)
        if candidate["vodAddedAt"] not in entry["datesAdded"]:
            entry["datesAdded"].append(candidate["vodAddedAt"])
    movies = sorted(groups.values(), key=lambda x: (max(x["datesAdded"]), x["title"]), reverse=True)
    for item in movies:
        item["providers"].sort(key=lambda x: (x["name"], x["vodAddedAt"]))
        item["datesAdded"].sort()
    output = {"region": "PL", "source": source.SOURCE,
              "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
              "todayWarsaw": today.isoformat(),
              "productionReady": False, "movies": movies}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Diagnostic catalog: {len(parser.cards)} listing cards, {len(movies)} distinct recent films")
    print(f"Saved {OUTPUT}; NOT a verified Filmweb recommendation feed")

if __name__ == "__main__":
    build()
