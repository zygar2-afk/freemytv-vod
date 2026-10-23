#!/usr/bin/env python3
"""Read-only source check for the Polish VOD series listing.

Does not publish recommendations. A successful HTTP request alone does not
prove that series dates, ratings, or availability are usable.
"""
import datetime as dt
import json
from urllib.parse import urlsplit

from inspect_vod_markup import CardInspector, candidates_from_cards
from probe_weekly_pagination import fetch, next_url

SERIES_URL = "https://nowoscivod.pl/seriale"
MAX_PAGES = 2

def main():
    page_url = SERIES_URL
    pages = []
    visited = set()
    for index in range(1, MAX_PAGES + 1):
        if page_url in visited:
            break
        visited.add(page_url)
        html = fetch(page_url)  # robots verification and bounded read
        inspector = CardInspector()
        inspector.feed(html)
        candidates = candidates_from_cards(inspector.cards)
        recent = 0
        date_parse_errors = 0
        today = dt.datetime.now(dt.timezone.utc).date()
        for item in candidates:
            try:
                d = dt.date.fromisoformat(item["vodAddedAt"])
                if 0 <= (today - d).days <= 6:
                    recent += 1
            except (ValueError, KeyError):
                date_parse_errors += 1
        pages.append({
            "pageNumber": index,
            "cardCount": len(inspector.cards),
            "parsedCandidates": len(candidates),
            "recentCandidates": recent,
            "dateParseErrors": date_parse_errors,
            "withFilmwebLink": sum(bool(c.get("filmwebLinkCandidates")) for c in candidates),
            "withRatingLabel": sum(bool(c.get("listingRatingLabel")) for c in candidates),
            "withVotesLabel": sum(bool(c.get("listingVotesLabel")) for c in candidates),
            "sampleTitleAndDate": [
                {"title": c["title"], "date": c["vodAddedAt"]}
                for c in candidates[:3]
            ],
        })
        following = next_url(html, page_url, index)
        if not following or urlsplit(following).path != "/seriale":
            break
        page_url = following
    print(json.dumps({
        "source": SERIES_URL,
        "pagesChecked": pages,
        "schemaVerifiedForProduction": False,
        "weeklyCoverageVerified": False,
        "publicationEnabled": False,
        "nextStep": "Confirm serial-specific parsing and pagination before any ranking."
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
