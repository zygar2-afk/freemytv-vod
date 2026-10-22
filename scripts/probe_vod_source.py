#!/usr/bin/env python3
"""Conservative source-availability probe. NEVER publishes unverified movies.

This checks whether a candidate VOD source is reachable and visibly contains
addition-date labels. It does not scrape Filmweb, harvest listings, or edit
vod_recommendations.json. A stable, permitted data interface is still required.
"""
import argparse
import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

SOURCE = "https://nowoscivod.pl/filmy"
USER_AGENT = "FreeMyTV-VOD-Research/0.1 (+https://github.com/zygar2-afk/freemytv-vod)"
MAX_BYTES = 250_000


def probe(url=SOURCE):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "nowoscivod.pl":
        raise ValueError("Only the reviewed HTTPS source hostname is allowed")

    robots = urllib.robotparser.RobotFileParser()
    robots.set_url("https://nowoscivod.pl/robots.txt")
    # If robots.txt is unavailable, do not assume crawling is permitted.
    try:
        with urllib.request.urlopen(
            urllib.request.Request(robots.url, headers={"User-Agent": USER_AGENT}),
            timeout=12,
        ) as response:
            if response.status != 200:
                raise RuntimeError("robots.txt did not return HTTP 200")
            robots.parse(response.read(100_000).decode("utf-8", "replace").splitlines())
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError("robots.txt could not be verified; no listing fetched") from exc

    if not robots.can_fetch(USER_AGENT, url):
        raise RuntimeError("Source disallowed by robots.txt; no listing fetched")

    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError("Listing returned HTTP " + str(response.status))
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type.lower():
            raise RuntimeError("Unexpected listing content type")
        html = response.read(MAX_BYTES + 1)
        if len(html) > MAX_BYTES:
            raise RuntimeError("Listing exceeds byte limit")

    text = html.decode("utf-8", "replace")
    labels = len(re.findall(r"Data\s+dodania", text, re.IGNORECASE))
    return {
        "source": url,
        "checkedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "robotsAllowed": True,
        "htmlBytes": len(html),
        "dateLabelMatches": labels,
        "readyForAutomaticPublication": False,
        "reason": "Need an authorized, stable structured feed and title-level evidence",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=SOURCE)
    args = parser.parse_args()
    try:
        result = probe(args.url)
    except (OSError, ValueError, RuntimeError) as exc:
        result = {
            "source": args.url,
            "readyForAutomaticPublication": False,
            "error": str(exc),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
