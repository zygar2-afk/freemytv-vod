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
DATE_PATTERN = re.compile(r"(?:20[0-9]{2}[ ./-]+[0-9]{1,2}[ ./-]+[0-9]{1,2}|[0-9]{1,2}[ ./-]+[0-9]{1,2}[ ./-]+20[0-9]{2})")


class Inspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = collections.Counter()
        self.links = []
        self.text = []
        self.current_link = None
        self.date_contexts = []
        self.tag_stack = []

    def handle_starttag(self, tag, attrs):
        self.tags[tag] += 1
        if tag not in ("img", "br", "hr", "input", "meta", "link", "source", "wbr"):
            self.tag_stack.append((tag, dict(attrs).get("class", "")[:90]))
        if tag == "a":
            attributes = dict(attrs)
            self.current_link = {"href": attributes.get("href", ""), "label": ""}

    def handle_data(self, data):
        normalized = " ".join(data.split())
        if not normalized:
            return
        self.text.append(normalized)
        if DATE_PATTERN.search(normalized) and len(self.date_contexts) < 5:
            self.date_contexts.append({"dateText": normalized[:55], "ancestors": self.tag_stack[-7:]})
        if self.current_link is not None:
            self.current_link["label"] += " " + normalized

    def handle_endtag(self, tag):
        for i in range(len(self.tag_stack) - 1, -1, -1):
            if self.tag_stack[i][0] == tag:
                del self.tag_stack[i:]
                break
        if tag == "a" and self.current_link is not None:
            self.links.append(self.current_link)
            self.current_link = None



class CardInspector(HTMLParser):
    """Collect complete Bootstrap card text/links for manual structural QA."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.active = None
        self.card_depth = -1
        self.cards = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div" and self.active is None and "card" in attrs.get("class", "").split():
            self.active = {"text": [], "links": [], "imageAlts": []}
            self.card_depth = self.depth
        if self.active is not None:
            if tag == "a" and attrs.get("href"):
                href = attrs["href"]
                if href.startswith("/") and not href.startswith("//"):
                    self.active["links"].append(href[:130])
            if tag == "img" and attrs.get("alt"):
                self.active["imageAlts"].append(attrs["alt"][:100])
        if tag == "div":
            self.depth += 1

    def handle_data(self, text):
        if self.active is not None:
            normalized = " ".join(text.split())
            if normalized and len(self.active["text"]) < 50:
                self.active["text"].append(normalized[:150])

    def handle_endtag(self, tag):
        if tag == "div":
            self.depth = max(0, self.depth - 1)
            if self.active is not None and self.depth == self.card_depth:
                if len(self.cards) < 4:
                    self.cards.append(self.active)
                self.active = None
                self.card_depth = -1


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
    # Look specifically for per-title "Data dodania:", excluding the date filter.
    # This is only a bounded structure probe; it does not assert a film identity.
    raw = body.decode("utf-8", "replace")
    card_markup = []
    matches = list(re.finditer(r"Data\\s+dodania\\s*:", raw, re.IGNORECASE))
    for match in matches[:3]:
        excerpt = raw[max(0, match.start() - 600):min(len(raw), match.end() + 550)]
        card_markup.append(" ".join(excerpt.split())[:1150])
    p = Inspector()
    p.feed(body.decode("utf-8", "replace"))
    cards = CardInspector()
    cards.feed(raw)

    dated_snippets = []
    for idx, part in enumerate(p.text):
        if "data dodania" in part.casefold():
            neighbors = p.text[idx:idx + 5]
            matches = DATE_PATTERN.findall(" ".join(neighbors))
            dated_snippets.append({"dateCandidates": matches[:3], "nextTextLengths": [len(t) for t in neighbors],
                                   "shortContext": [t[:72] for t in neighbors[:4]] if len(dated_snippets) < 5 else []})
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
        "dateElementContexts": p.date_contexts,
        "cardCountSampled": len(cards.cards),
        "cardStructureSamples": cards.cards[:3],
        "boundedCardMarkupSamples": card_markup,
        "perTitleDateLabelMatches": len(matches),
        "labelSectionsWithNearbyDate": sum(bool(s["dateCandidates"]) for s in dated_snippets),
        "nearbyDateSamples": dated_snippets[:5],
        "relativeLinkCount": len(detail_links),
        "relativeLinkPathSamples": detail_links[:MAX_ITEMS],
        "verifiedMovies": 0,
        "readyForAutomaticPublication": False,
        "note": "No reliable title-date-platform join or Filmweb ratings verified",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
