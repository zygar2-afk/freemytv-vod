#!/usr/bin/env python3
"""Read-only pagination/sorting diagnostics for NowosciVOD; no crawling next pages.

Only fetches the landing page after robots verification. Reports observed
pagination links and form controls rather than guessing a page URL pattern.
"""
from html.parser import HTMLParser
import json
from urllib.parse import urljoin, urlsplit, parse_qs
import urllib.request

import probe_vod_source as source

class Audit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.forms = []
        self.form = None
        self.selects = []
        self.scripts = []
        self.rel_next = []
    def handle_starttag(self, tag, attributes):
        a = dict(attributes)
        if tag == "form":
            self.form = {"action": a.get("action", ""), "method": a.get("method","get"), "controls":[]}
        elif tag in ("input","select","button") and self.form is not None:
            if a.get("name"):
                self.form["controls"].append({"tag":tag,"name":a["name"],"value":a.get("value","")[:65]})
        if tag == "select":
            self.selects.append({"name":a.get("name",""),"id":a.get("id","")})
        if tag == "a":
            href = a.get("href","")
            if href:
                self.links.append({"href":href[:250],"rel":a.get("rel",""),"class":a.get("class","")[:100]})
        if tag == "link" and "next" in a.get("rel",""):
            self.rel_next.append(a.get("href",""))
        if tag == "script" and a.get("src"):
            self.scripts.append(a["src"][:180])
    def handle_endtag(self,tag):
        if tag == "form" and self.form:
            self.forms.append(self.form)
            self.form=None

def main():
    source.probe()
    with urllib.request.urlopen(urllib.request.Request(
        source.SOURCE,headers={"User-Agent":source.USER_AGENT,"Accept":"text/html"}
    ),timeout=15) as r:
        body=r.read(source.MAX_BYTES+1)
    if len(body)>source.MAX_BYTES:
        raise RuntimeError("Exceeded size cap")
    p=Audit()
    p.feed(body.decode("utf-8","replace"))
    likely=[]
    for link in p.links:
        href=link["href"]
        parsed=urlsplit(urljoin(source.SOURCE,href))
        if parsed.hostname != "nowoscivod.pl":
            continue
        keys=set(parse_qs(parsed.query))
        if ("page" in keys or "strona" in keys or "pagination" in link["class"].lower()
                or "next" in link["rel"].lower() or "/strona/" in parsed.path):
            likely.append(link)
    print(json.dumps({
        "source":source.SOURCE,
        "landingPageOnly":True,
        "totalLinks":len(p.links),
        "paginationLinkCandidates":likely[:30],
        "relNextLinks":p.rel_next[:10],
        "forms":[{"action":f["action"],"method":f["method"],
                  "controlNames":[c["name"] for c in f["controls"][:100]]} for f in p.forms[:6]],
        "selectControls":p.selects[:20],
        "scriptPaths":p.scripts[:20],
        "weeklyCoverageVerified":False,
        "nextAction":"Confirm a real pagination or date-filter interface before requesting another page"
    },ensure_ascii=False,indent=2))

if __name__ == "__main__":
    main()
