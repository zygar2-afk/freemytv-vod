#!/usr/bin/env python3
"""Build NON-PRODUCTION separate TOP-10 VOD film and series sample.

Date is the date ADDED TO VOD according to the source, never release year.
The ranking is a popularity proxy (vote count) with a minimum rating guard,
not real audience/view counts. This feed is not independently verified.
"""
import datetime as dt
import json
import pathlib
import re
import urllib.parse
import zoneinfo

import probe_vod_source as source
from inspect_vod_markup import CardInspector, candidates_from_cards
from probe_weekly_pagination import fetch, next_url, MAX_PAGES
from build_experimental_candidates import rating_from_listing

OUT = pathlib.Path("out/experimental_vod_top10.json")
TOP = 10
MIN_RATING = 7.0
MIN_VOTES = 100

def collect(url, media_type, page_limit, today):
    grouped = {}
    pages = []
    visited = set()
    stop = "PAGE_LIMIT"
    for page in range(1, page_limit + 1):
        if url in visited:
            stop = "PAGINATION_LOOP"
            break
        visited.add(url)
        html = fetch(url)
        cards = CardInspector()
        cards.feed(html)
        candidates = candidates_from_cards(cards.cards)
        if not candidates:
            stop = "EMPTY_OR_UNPARSEABLE_PAGE"
            break
        pages.append({"page":page, "cards":len(cards.cards), "candidates":len(candidates)})
        for row in candidates:
            try:
                added = dt.date.fromisoformat(row["vodAddedAt"])
            except (KeyError, ValueError):
                continue
            if not 0 <= (today - added).days <= 6:
                continue
            links = row.get("filmwebLinkCandidates", [])
            if len(links) != 1:
                continue
            m = re.search(r"-([0-9]+)$",urllib.parse.urlsplit(links[0]).path)
            if not m:
                continue
            rating = rating_from_listing(row)
            if rating is None:
                continue
            identity = m.group(1)
            value = grouped.setdefault(identity, {
                "filmwebId": identity, "filmwebUrl": links[0],
                "mediaType": media_type, "title": row["title"],
                "providers": [], "datesAdded": [], "listingRating": rating,
                "ratingVerifiedByFilmweb": False,
                "editorialRecommendationVerified": False,
                "status": "CANDIDATE_UNVERIFIED",
            })
            if value["title"].strip().casefold() != row["title"].strip().casefold():
                value["conflict"] = True
            if value["listingRating"] != rating:
                value["conflict"] = True
            provider = {"name":row["provider"],"vodAddedAt":row["vodAddedAt"],
                        "outsideSubscriptionLabelPresent":row["outsideSubscriptionLabelPresent"]}
            if provider not in value["providers"]:
                value["providers"].append(provider)
            if row["vodAddedAt"] not in value["datesAdded"]:
                value["datesAdded"].append(row["vodAddedAt"])
        if page < page_limit:
            upcoming = next_url(html, url, page) if media_type == "film" else None
            # Series pagination URL is not yet validated: do not guess it.
            if not upcoming:
                stop = "SERIES_PAGINATION_UNVERIFIED" if media_type == "series" else "NO_RECOGNIZED_NEXT_PAGE"
                break
            url = upcoming
    selected = [
        value for value in grouped.values()
        if not value.get("conflict") and value["providers"]
        and value["listingRating"]["rating"] >= MIN_RATING
        and value["listingRating"]["votesApprox"] >= MIN_VOTES
    ]
    # Popularity proxy: count of votes first, rating as the tiebreaker.
    selected.sort(key=lambda x:(x["listingRating"]["votesApprox"],
               x["listingRating"]["rating"],max(x["datesAdded"]),x["title"]), reverse=True)
    for value in selected:
        value["providers"].sort(key=lambda p:(p["name"],p["vodAddedAt"]))
        value["datesAdded"].sort()
    return selected[:TOP], {
        "pages":pages, "stoppedBecause":stop,
        "eligibleInSample":len(selected), "fullSevenDayCoverageVerified":False,
    }

def main():
    today = dt.datetime.now(zoneinfo.ZoneInfo("Europe/Warsaw")).date()
    movies, movie_meta = collect(source.SOURCE,"film",MAX_PAGES,today)
    shows, show_meta = collect("https://nowoscivod.pl/seriale","series",1,today)
    data = {
        "region":"PL", "generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "todayWarsaw":today.isoformat(), "productionReady":False,
        "selection":{
            "periodDays":7,"topPerCategory":TOP,
            "popularityProxy":"approximate listing votes (not actual VOD views)",
            "minRating":MIN_RATING,"minimumVotes":MIN_VOTES,
            "rankingIsComplete":False,"ratingsVerifiedOnFilmweb":False,
        },
        "movies":movies, "series":shows,
        "diagnostics":{"films":movie_meta,"series":show_meta},
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"EXPERIMENTAL TOP 10: {len(movies)} films, {len(shows)} series")
    print(f"Film sample: {movie_meta['pages']} Series sample: {show_meta['pages']}")
    print("Incomplete 7-day source coverage; no production publication.")
if __name__=="__main__":
    main()
