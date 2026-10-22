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
from probe_weekly_pagination import fetch, next_url, MAX_PAGES

OUTPUT = pathlib.Path("out/experimental_vod_candidates.json")
TOP_LIMIT = 20
MIN_VOTES = 100
MIN_RATING = 7.0

def rating_from_listing(candidate):
    """Unverified score displayed by NowosciVOD, NOT independently verified Filmweb data."""
    label = candidate.get("listingRatingLabel") or ""
    votes = candidate.get("listingVotesLabel") or ""
    score_match = re.search(r"([0-9]+(?:[,.][0-9]+)?)", label)
    vote_match = re.search(r"([0-9]+(?:[,.][0-9]+)?)", votes)
    if not (score_match and vote_match):
        return None
    rating = float(score_match.group(1).replace(",", "."))
    count = float(vote_match.group(1).replace(",", "."))
    if "tys." in votes.lower():
        count = round(count * 1000)
    elif "mln" in votes.lower():
        count = round(count * 1_000_000)
    else:
        count = int(count)
    if not (0 <= rating <= 10 and count >= 0):
        return None
    return {"rating": rating, "votesApprox": int(count), "source": "nowoscivod_listing", "verifiedOnFilmweb": False}


def build():
    today = dt.datetime.now(zoneinfo.ZoneInfo("Europe/Warsaw")).date()
    url = source.SOURCE
    all_cards = []
    pages_fetched = 0
    stop_reason = "PAGE_LIMIT"
    visited = set()
    for page in range(1, MAX_PAGES + 1):
        if url in visited:
            stop_reason = "PAGINATION_LOOP"
            break
        visited.add(url)
        html = fetch(url)
        parser = CardInspector()
        parser.feed(html)
        if not parser.cards:
            stop_reason = "EMPTY_PAGE"
            break
        all_cards.extend(parser.cards)
        pages_fetched += 1
        following = next_url(html, url, page)
        if not following:
            stop_reason = "NO_RECOGNIZED_NEXT_PAGE"
            break
        url = following
    # The listing is not reliably date-sorted. Never equate the page cap,
    # or a missing pagination link, with complete seven-day coverage.
    groups = {}
    for candidate in candidates_from_cards(all_cards):
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
            "mediaType": "film", "listingRating": None,
            "title": candidate["title"], "providers": [],
            "datesAdded": [], "status": "CANDIDATE_UNVERIFIED",
            "ratingVerifiedByFilmweb": False,
            "editorialRecommendationVerified": False,
        })
        if entry["title"].strip().casefold() != candidate["title"].strip().casefold():
            raise RuntimeError("Title mismatch for Filmweb ID " + film_id)
        score = rating_from_listing(candidate)
        if score:
            if entry["listingRating"] and entry["listingRating"] != score:
                # Do not silently choose between conflicting ratings for a title.
                entry["listingRating"] = None
                entry["ratingConflict"] = True
            elif not entry.get("ratingConflict"):
                entry["listingRating"] = score
        association = {"name": candidate["provider"],
                       "vodAddedAt": candidate["vodAddedAt"],
                       "outsideSubscriptionLabelPresent": candidate["outsideSubscriptionLabelPresent"]}
        if association not in entry["providers"]:
            entry["providers"].append(association)
        if candidate["vodAddedAt"] not in entry["datesAdded"]:
            entry["datesAdded"].append(candidate["vodAddedAt"])
    eligible = [item for item in groups.values()
                if not item.get("ratingConflict") and item["listingRating"]
                and item["listingRating"]["rating"] >= MIN_RATING
                and item["listingRating"]["votesApprox"] >= MIN_VOTES]
    movies = sorted(eligible, key=lambda x: (
        x["listingRating"]["rating"], x["listingRating"]["votesApprox"],
        max(x["datesAdded"]), x["title"]), reverse=True)[:TOP_LIMIT]
    for item in movies:
        item["providers"].sort(key=lambda x: (x["name"], x["vodAddedAt"]))
        item["datesAdded"].sort()
    output = {"region": "PL", "source": source.SOURCE,
              "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
              "todayWarsaw": today.isoformat(),
              "productionReady": False, "selection": {
                  "requestedMediaTypes": ["film", "series"],
                  "currentlySupportedMediaTypes": ["film"],
                  "maxItems": TOP_LIMIT, "minimumRating": MIN_RATING,
                  "minimumVotes": MIN_VOTES,
                  "ratingSource": "unverified nowoscivod.pl listing",
                  "coverage": "bounded multi-page sample; full 7-day coverage unverified",
                  "pagesFetched": pages_fetched, "pageLimit": MAX_PAGES,
                  "stopReason": stop_reason,
                  "sourceDateOrderVerified": False,
                  "eligibleSampleFilms": len(eligible)
              }, "movies": movies}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Experimental TOP {TOP_LIMIT}: {len(all_cards)} listing cards over {pages_fetched} pages, {len(eligible)} qualifying sample films, {len(movies)} selected")
    print(f"Saved {OUTPUT}; NOT a verified Filmweb recommendation feed")

if __name__ == "__main__":
    build()
