#!/usr/bin/env python3
"""Bounded diagnostic for Polish VOD serials: pagination and unrated candidates.

No automated Filmweb access. Neither addition to the VOD listing nor the
production year establishes a new season premiere. Never publishes this file.
"""
import datetime as dt
import json
import pathlib
import re
from urllib.parse import urljoin, urlsplit, parse_qs
import zoneinfo

from inspect_vod_markup import CardInspector, candidates_from_cards
from probe_weekly_pagination import fetch, Pagination
from build_experimental_candidates import rating_from_listing

SERIES_URL = "https://nowoscivod.pl/seriale"
MAX_PAGES = 4
OUTPUT = pathlib.Path("out/experimental_series_needs_review.json")

def next_series_url(html, current, expected):
    nav = Pagination()
    nav.feed(html)
    for href in nav.links:
        url = urljoin(current, href)
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "nowoscivod.pl" or parsed.path != "/seriale":
            continue
        q = parse_qs(parsed.query)
        if q.get("page") != [str(expected)]:
            continue
        # Use only an observed same-site link, never synthesize URLs.
        if any(v not in ("serial", "series", "tv") for k in ("directType", "type[0]", "type[]") for v in q.get(k, [])):
            continue
        return url
    return None

def main():
    today = dt.datetime.now(zoneinfo.ZoneInfo("Europe/Warsaw")).date()
    url = SERIES_URL
    visited = set()
    pages = []
    unrated = {}
    stop = "PAGE_LIMIT"
    rated = 0
    for index in range(1, MAX_PAGES + 1):
        if url in visited:
            stop = "PAGINATION_LOOP"
            break
        visited.add(url)
        html = fetch(url)  # independently checks robots and response size
        inspector = CardInspector()
        inspector.feed(html)
        candidates = candidates_from_cards(inspector.cards)
        if not candidates:
            stop = "EMPTY_OR_UNPARSEABLE_PAGE"
            break
        recent = 0
        for item in candidates:
            try:
                added = dt.date.fromisoformat(item["vodAddedAt"])
            except (ValueError, KeyError):
                continue
            if not 0 <= (today - added).days <= 6:
                continue
            recent += 1
            rating = rating_from_listing(item)
            if rating is not None:
                rated += 1
                continue
            links = item.get("filmwebLinkCandidates", [])
            if len(links) != 1:
                continue
            identity = re.search(r"-([0-9]+)$", urlsplit(links[0]).path)
            if identity is None:
                continue
            key = identity.group(1)
            entry = unrated.setdefault(key, {
                "filmwebId": key, "title":item["title"], "filmwebUrl":links[0],
                "mediaType":"series", "providers":[], "datesAdded":[],
                "category":"NEW_ON_VOD_UNRATED_NEEDS_REVIEW",
                "ratingVerified":False, "newSeasonPremiereVerified":False,
                "premiereEvidence":None, "publishable":False
            })
            if entry["title"].casefold() != item["title"].casefold():
                entry["conflictingTitle"] = True
            if item["provider"] not in entry["providers"]:
                entry["providers"].append(item["provider"])
            if item["vodAddedAt"] not in entry["datesAdded"]:
                entry["datesAdded"].append(item["vodAddedAt"])
        pages.append({"page":index,"cards":len(inspector.cards),
                      "parsed":len(candidates),"recent":recent})
        if index < MAX_PAGES:
            following = next_series_url(html, url, index + 1)
            if following is None:
                stop = "SERIES_PAGINATION_LINK_NOT_VERIFIED"
                break
            url = following
    result = {
        "source":SERIES_URL, "dateWarsaw":today.isoformat(),
        "pages":pages, "stopReason":stop, "recentWithRating":rated,
        "unratedNeedsReview":sorted(unrated.values(), key=lambda x:x["title"].casefold()),
        "seasonPremieresConfirmed":0,
        "seasonPremiereValidationMethod":"external documented evidence required; not inferable from listing",
        "completeWeekCoverageVerified":False, "productionReady":False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"pages":pages,"stopReason":stop,"unratedNeedsReview":len(unrated),
                      "recentWithRating":rated,"seasonPremieresConfirmed":0},ensure_ascii=False,indent=2))

if __name__ == "__main__":
    main()
