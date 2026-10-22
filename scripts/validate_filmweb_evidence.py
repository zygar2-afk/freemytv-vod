#!/usr/bin/env python3
"""Offline Filmweb evidence gate. No network requests or automated Filmweb access.

Input: JSON array of review records. Each record must include:
  filmwebUrl, filmwebId, title, verifiedAt,
  ratingSourceType ("manual_filmweb_page"), userRating, votes
Optionally: editorialRecommended and editorialSource (requires URL).
This only checks evidence format, NOT truth of claimed data.
"""
import datetime as dt
import json
import pathlib
import re
import sys
from urllib.parse import urlsplit

def check(row):
    errors = []
    if not isinstance(row, dict):
        return ["Expected JSON object"]
    url = row.get("filmwebUrl", "")
    parts = urlsplit(url) if isinstance(url, str) else urlsplit("")
    if parts.scheme != "https" or parts.hostname not in ("filmweb.pl", "www.filmweb.pl"):
        errors.append("Invalid Filmweb URL")
    match = re.search(r"-(\\d+)$", parts.path)
    if not match or str(row.get("filmwebId", "")) != match.group(1):
        errors.append("Filmweb ID does not match URL")
    if not isinstance(row.get("title"), str) or not row["title"].strip():
        errors.append("Missing title")
    if row.get("ratingSourceType") != "manual_filmweb_page":
        errors.append("Unsupported rating evidence type")
    rating = row.get("userRating")
    if type(rating) not in (float, int) or not 0 <= rating <= 10:
        errors.append("Invalid user rating")
    if type(row.get("votes")) is not int or row["votes"] < 0:
        errors.append("Invalid vote count")
    try:
        date = dt.date.fromisoformat(row["verifiedAt"])
        if date > dt.datetime.now(dt.timezone.utc).date():
            errors.append("Verification date is in the future")
    except (ValueError, TypeError, KeyError):
        errors.append("Invalid verifiedAt date")
    if row.get("editorialRecommended") is True:
        editorial = row.get("editorialSource", "")
        source_url = urlsplit(editorial) if isinstance(editorial, str) else urlsplit("")
        if source_url.scheme != "https" or source_url.hostname not in ("filmweb.pl", "www.filmweb.pl"):
            errors.append("Editorial recommendation lacks Filmweb evidence URL")
    return errors

def main():
    if len(sys.argv) != 2:
        print("Usage: validate_filmweb_evidence.py PATH_TO_JSON", file=sys.stderr)
        return 2
    rows = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Input must be a JSON array")
    invalid = [(i, check(row)) for i, row in enumerate(rows) if check(row)]
    print(json.dumps({"checked": len(rows), "formatValid": len(rows) - len(invalid),
                      "formatInvalid": [{"index": i, "issues": issues} for i, issues in invalid],
                      "independentlyVerified": False,
                      "note": "Schema checks do not verify page contents or authorization"},
                     ensure_ascii=False, indent=2))
    return 1 if invalid else 0

if __name__ == "__main__":
    raise SystemExit(main())
