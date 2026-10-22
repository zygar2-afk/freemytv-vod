#!/usr/bin/env python3
"""Diagnostic-only inspection of a VOD listing. No production feed writes.

A date label beside an HTML anchor is NOT proof of a title-level VOD addition.
This script emits aggregate clues and anonymized structural information only.
"""
import collections
from html.parser import HTMLParser
import json
import re
import urllib.request

import probe_vod_source as source

MAX_ITEMS = 12
DATE_PATTERN = re.compile(r"(?:20[0-9]{2}[-./][0-9]{1,2}[-./][0-9]{1,2}|[0-9]{1,2}[-./][0-9]{1,2}[-./]20[0-9]{2})")


class Inspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = collections.Counter()
        self.links = []
        self.text = []
        self.current_link = None

    def handle_starttag(self, tag, attrs):
        self.tags[tag] += 1
        if tag == "a":
            attributes = dict(attrs)
            self.current_link = {"href": attributes.get("href", ""), "label": ""}

    def handle_data(self, data):
        normalized = " ".join(data.split())
        if not normalized:
            return
        self.text.append(normalized)
        if self.current_link is not None:
            self.current_link["label"] += " " + normalized

    def handle_endtag(self, tag):
        if tag == "a" and self.current_link is not None:
            self.links.append(self.current_link)
            self.current_link = None


def main():
    # This independently verifies the robots policy before accessing the listing.
    base = source.probe()
    req = urllib.request.Request(
        source.SOURCE,
        headers={"User-Agent": source.USER_AGENT, "Accept": "text/html"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        body = response.read(source.MAX_BYTES + 1)
        if len(body) > source.MAX_BYTES:
            raise RuntimeError("Response exceeded size cap")
    p = Inspector()
    p.feed(body.decode("utf-8", "replace"))

    dated_snippets = []
    for idx, part in enumerate(p.text):
        if "data dodania" in part.casefold():
            neighbors = p.text[idx:idx + 5]
            matches = DATE_PATTERN.findall(" ".join(neighbors))
            dated_snippets.append({"dateCandidates": matches[:3], "nextTextLengths": [len(t) for t in neighbors]})
    detail_links = []
    for link in p.links:
        href = link["href"]
        # Retain relative URLs only, no page content or external trackers.
        if href.startswith("/") and not href.startswith("//") and link["label"].strip():
            detail_links.append({"path": href[:120], "labelLength": len(link["label"].strip())})
    print(json.dumps({
        "source": source.SOURCE,
        "robotsAllowed": base["robotsAllowed"],
        "tagCounts": {key: p.tags[key] for key in ("article", "time", "a", "h2", "h3")},
        "labelSections": len(dated_snippets),
        "labelSectionsWithNearbyDate": sum(bool(s["dateCandidates"]) for s in dated_snippets),
        "nearbyDateSamples": dated_snippets[:MAX_ITEMS],
        "relativeLinkCount": len(detail_links),
        "relativeLinkPathSamples": detail_links[:MAX_ITEMS],
        "verifiedMovies": 0,
        "readyForAutomaticPublication": False,
        "note": "No reliable title-date-platform join or Filmweb ratings verified",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
