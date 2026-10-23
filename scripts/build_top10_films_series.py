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
from probe_series_source import next_series_url

OUT = pathlib.Path("out/experimental_vod_top10.json")
TOP = 10
FILM_MIN_RATING = 5.0
FILM_MIN_VOTES = 20
SERIES_MIN_RATING = 5.0
SERIES_MIN_VOTES = 20
MOVIE_WINDOW_DAYS = 7
SERIES_WINDOW_DAYS = 21

def collect(url, media_type, page_limit, today):
    days = MOVIE_WINDOW_DAYS if media_type == "film" else SERIES_WINDOW_DAYS
    min_rating = FILM_MIN_RATING if media_type == "film" else SERIES_MIN_RATING
    min_votes = FILM_MIN_VOTES if media_type == "film" else SERIES_MIN_VOTES
    grouped = {}
    pages = []
    visited = set()
    stop = "PAGE_LIMIT"
    audit = {"total":0,"recent":0,"idValid":0,"yearUnknown":0,"yearOlder":0,"yearCurrent":0,"ratingMissing":0,"belowThreshold":0,"qualified":0}
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
            audit["total"] += 1
            try:
                added = dt.date.fromisoformat(row["vodAddedAt"])
            except (KeyError, ValueError):
                continue
            if not 0 <= (today - added).days < days:
                continue
            audit["recent"] += 1
            links = row.get("filmwebLinkCandidates", [])
            if len(links) != 1:
                continue
            m = re.search(r"-([0-9]+)$",urllib.parse.urlsplit(links[0]).path)
            if not m:
                continue
            audit["idValid"] += 1
            # Require a production released in the current calendar year; this
            # is a conservative safeguard against old catalog additions, not
            # proof of a premiere within the past seven days.
            year_match = re.search(r"-(19[0-9]{2}|20[0-9]{2})-[0-9]+$",
                                   urllib.parse.unquote(urllib.parse.urlsplit(links[0]).path))
            if not year_match:
                audit["yearUnknown"] += 1
                continue
            if int(year_match.group(1)) != today.year:
                audit["yearOlder"] += 1
                if media_type == "film":
                    continue
            else:
                audit["yearCurrent"] += 1
            rating = rating_from_listing(row)
            if rating is None:
                audit["ratingMissing"] += 1
                continue
            if rating["rating"] < min_rating or rating["votesApprox"] < min_votes:
                audit["belowThreshold"] += 1
                continue
            audit["qualified"] += 1
            identity = m.group(1)
            value = grouped.setdefault(identity, {
                "filmwebId": identity, "filmwebUrl": links[0],
                "mediaType": media_type, "title": row["title"],
                "providers": [], "datesAdded": [], "listingRating": rating,
                "ratingVerifiedByFilmweb": False,
                "editorialRecommendationVerified": False,
                "status": "CANDIDATE_UNVERIFIED",
                "displayCategory": "NOWO_W_VOD" if media_type == "series" else "NOWOSC_FILMOWA_VOD",
                "seasonPremiereVerified": False,
            })
            if value["title"].strip().casefold() != row["title"].strip().casefold():
                value["conflict"] = True
            if value["listingRating"] != rating:
                value["conflict"] = True
            provider = {"name":row["provider"],"vodAddedAt":row["vodAddedAt"],
                        "availabilityEvidenceUrl": url,
                        "outsideSubscriptionLabelPresent":row["outsideSubscriptionLabelPresent"]}
            if provider not in value["providers"]:
                value["providers"].append(provider)
            if row["vodAddedAt"] not in value["datesAdded"]:
                value["datesAdded"].append(row["vodAddedAt"])
        if page < page_limit:
            upcoming = (next_url(html, url, page) if media_type == "film"
                        else next_series_url(html, url, page + 1))
            # Series pagination URL is not yet validated: do not guess it.
            if not upcoming:
                stop = "SERIES_PAGINATION_UNVERIFIED" if media_type == "series" else "NO_RECOGNIZED_NEXT_PAGE"
                break
            url = upcoming
    selected = [
        value for value in grouped.values()
        if not value.get("conflict") and value["providers"]
        and value["listingRating"]["rating"] >= min_rating
        and value["listingRating"]["votesApprox"] >= min_votes
    ]
    # Popularity proxy: count of votes first, rating as the tiebreaker.
    selected.sort(key=lambda x:(x["listingRating"]["votesApprox"],
               x["listingRating"]["rating"],max(x["datesAdded"]),x["title"]), reverse=True)
    for value in selected:
        # This date proves only a listing claim about catalog addition,
        # never a new season or a first production premiere.
        if media_type == "series":
            latest = max(value["datesAdded"])
            value["premiereEvidence"] = {
                "event":"new_on_vod", "premiereDatePL":latest,
                "sourceUrl":value["providers"][0]["availabilityEvidenceUrl"],
                "checkedAt":today.isoformat(), "checkedBy":"automated_listing_parser",
                "verifiedByIndependentSource":False,
            }
        value["providers"].sort(key=lambda p:(p["name"],p["vodAddedAt"]))
        value["datesAdded"].sort()
    return selected[:TOP], {
        "windowDays":days, "pages":pages, "stoppedBecause":stop,
        "eligibleInSample":len(selected), "filterAudit":audit,
        "fullSevenDayCoverageVerified":False,
    }

def main():
    today = dt.datetime.now(zoneinfo.ZoneInfo("Europe/Warsaw")).date()
    movies, movie_meta = collect(source.SOURCE,"film",MAX_PAGES,today)
    shows, show_meta = collect("https://nowoscivod.pl/seriale","series",MAX_PAGES,today)
    data = {
        "region":"PL", "generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "todayWarsaw":today.isoformat(), "productionReady":False,
        "selection":{
            "filmPeriodDays":MOVIE_WINDOW_DAYS,"seriesPeriodDays":SERIES_WINDOW_DAYS,
            "topPerCategory":TOP,
            "popularityProxy":"approximate historical listing votes; NOT trending growth or VOD watch counts",
            "filmMinimumRating":FILM_MIN_RATING,"filmMinimumVotes":FILM_MIN_VOTES,
            "seriesMinimumRating":SERIES_MIN_RATING,"seriesMinimumVotes":SERIES_MIN_VOTES,
            "filmProductionYearRequired":today.year,
            "seriesProductionYearRequired":None,
            "seriesNewSeasonReleaseIndependentlyVerified":False,
            "productionReleaseInPastWeekVerified":False,
            "rankingIsComplete":False,"ratingsVerifiedOnFilmweb":False,
        },
        "movies":movies, "series":shows,
        "diagnostics":{"films":movie_meta,"series":show_meta},
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"EXPERIMENTAL TOP 10: {len(movies)} films, {len(shows)} series")
    print(f"Film sample: {movie_meta['pages']} Series sample: {show_meta['pages']}")
    print("Film filter audit:", json.dumps(movie_meta["filterAudit"], ensure_ascii=False))
    print("Series filter audit:", json.dumps(show_meta["filterAudit"], ensure_ascii=False))
    print("Incomplete 7/21-day source coverage; no production publication.")
if __name__=="__main__":
    main()
