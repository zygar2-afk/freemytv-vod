#!/usr/bin/env python3
"""Bounded, diagnostic-only pagination audit. Does not write production feeds.

Follow the actual same-host ?page=2 navigation link from page 1 and
inspect at most four pages. Stop on unverified ordering, an HTML cap,
or date older than seven calendar days. Report incomplete coverage honestly.
"""
import datetime as dt
import json
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, parse_qs
import urllib.request
import zoneinfo

import probe_vod_source as source
from inspect_vod_markup import CardInspector, candidates_from_cards

MAX_PAGES = 4

class Pagination(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag == "a":
            href=dict(attrs).get("href","")
            if href:
                self.links.append(href)

def fetch(url):
    # Independently check robots.txt for EACH URL, fail closed.
    source.probe(url)
    with urllib.request.urlopen(urllib.request.Request(url,headers={
        "User-Agent":source.USER_AGENT,"Accept":"text/html"}),timeout=15) as r:
        if "text/html" not in r.headers.get("Content-Type","").lower():
            raise RuntimeError("Non-HTML response")
        data=r.read(source.MAX_BYTES+1)
    if len(data)>source.MAX_BYTES:
        raise RuntimeError("Page exceeds byte cap")
    return data.decode("utf-8","replace")

def next_url(html,current,page_number):
    nav=Pagination();nav.feed(html)
    for href in nav.links:
        url=urljoin(current,href)
        p=urlsplit(url)
        if p.scheme!="https" or p.hostname!="nowoscivod.pl" or p.path!="/filmy":
            continue
        q=parse_qs(p.query)
        if q.get("page")==[str(page_number+1)] and q.get("directType")==["film"] and "film" in q.get("type[]",[]):
            return url
    return None

def main():
    today=dt.datetime.now(zoneinfo.ZoneInfo("Europe/Warsaw")).date()
    threshold=today-dt.timedelta(days=6)
    url=source.SOURCE
    page_reports=[]
    recent_cards=0
    completed=False
    stop_reason="PAGE_LIMIT"
    previous_last=None
    seen_urls=set()
    seen_film_ids=set()
    for page in range(1,MAX_PAGES+1):
        if url in seen_urls:
            stop_reason="PAGINATION_LOOP";break
        seen_urls.add(url)
        html=fetch(url)
        cards=CardInspector();cards.feed(html)
        records=candidates_from_cards(cards.cards)
        if not records:
            stop_reason="EMPTY_OR_UNPARSEABLE_PAGE";break
        dates=[dt.date.fromisoformat(r["vodAddedAt"]) for r in records]
        monotonic=all(dates[i]>=dates[i+1] for i in range(len(dates)-1))
        boundary_ok=previous_last is None or previous_last>=dates[0]
        seen=set()
        for record in records:
            if threshold<=dt.date.fromisoformat(record["vodAddedAt"])<=today:
                recent_cards+=1
                for link in record["filmwebLinkCandidates"]:
                    seen_film_ids.add(link)
            seen.add(record["title"])
        page_reports.append({
            "page":page,"records":len(records),"uniqueTitles":len(seen),
            "firstDate":str(dates[0]),"lastDate":str(dates[-1]),
            "datesDescending":monotonic,"boundaryDescending":boundary_ok,
            "oldRecords":sum(x<threshold for x in dates),
            "futureDatedRecords":sum(x>today for x in dates),
        })
        if not monotonic or not boundary_ok:
            stop_reason="SORT_ORDER_UNVERIFIED";break
        if any(x>today for x in dates):
            stop_reason="FUTURE_DATED_RECORD";break
        previous_last=dates[-1]
        if previous_last<threshold:
            completed=True
            stop_reason="PAST_7_DAY_BOUNDARY";break
        upcoming=next_url(html,url,page)
        if not upcoming:
            completed=True
            stop_reason="NO_NEXT_PAGE";break
        url=upcoming
    result={
        "source":source.SOURCE,"pagesInspected":len(page_reports),
        "pageReports":page_reports,"last7DaysFrom":str(threshold),
        "last7DaysTo":str(today),"recentCardsSeen":recent_cards,
        "uniqueFilmwebLinksSeen":len(seen_film_ids),
        "weekRangeTraversed":completed,
        "stopReason":stop_reason,
        "productionReady":False,
        "note":"Coverage is only provisional: based on source listing order and dates, not independent validation."
    }
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
