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
                  "coverage": "first page only; incomplete for full 7 days",
                  "eligibleFilmsOnFirstPage": len(eligible)
              }, "movies": movies}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Experimental TOP {TOP_LIMIT}: {len(parser.cards)} listing cards, {len(eligible)} qualifying first-page films, {len(movies)} selected")
    print(f"Saved {OUTPUT}; NOT a verified Filmweb recommendation feed")

if __name__ == "__main__":
    build()
