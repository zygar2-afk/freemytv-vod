#!/usr/bin/env python3
"""Four dated Polish daily TV rankings, Netflix + HBO Max + SkyShowtime + Prime Video (TVHUB, unofficial).
TMDB enriches art only; never infer chart rankings from TMDB popularity.
"""
import datetime as dt
import html, json, pathlib, re, urllib.request
from zoneinfo import ZoneInfo
from build_tmdb_series import request

OUT=pathlib.Path("out/netflix_hbomax_sky_prime_daily_tv_pl.json")
URL="https://tvhub.pl/"
def clean(x):return html.unescape(re.sub(r"<[^>]*>","",x)).strip()
def parse_page(page,today):
    m=re.search(r'<section class="tvhub-fp".*?<time datetime="(\d{4}-\d\d-\d\d)"',page,re.S)
    if not m:raise ValueError("Missing dated TVHUB chart")
    date=dt.date.fromisoformat(m.group(1))
    if (today-date).days not in (0,1,2,3):raise ValueError("Chart stale or future")
    panel_match=re.search(r'<div[^>]*data-fp-type-panel="tv"[^>]*>',page[m.end():])
    if not panel_match:raise ValueError("TV content panel not found")
    begin=m.end()+panel_match.start()
    end=page.find('</section>',begin)
    panel=page[begin:end if end>begin else None]
    rankings={}
    for slug,name in (("netflix","Netflix"),("hbo-max","HBO Max"),("skyshowtime","SkyShowtime"),("amazon-prime","Prime Video")):
        card=re.search(r'<article class="tvhub-fp__card tvhub-fp__card--'+slug+r'"[^>]*>(.*?)</article>',panel,re.S)
        if not card:raise ValueError("Missing TV card for "+name+"; found "+repr(re.findall(r'tvhub-fp__card--([a-z0-9-]+)',panel)[:20]))
        titles=re.findall(r'<span class="tvhub-fp__title">(.*?)</span>',card.group(1),re.S)
        if len(titles)!=10:raise ValueError(f"{name}: expected 10, found {len(titles)}")
        out=[]
        for row in titles:
            alt=re.search(r'<small>(.*?)</small>',row,re.S)
            title=clean(re.sub(r"<small>.*?</small>","",row,flags=re.S))
            if not title:raise ValueError("Empty TV title")
            out.append((title,clean(alt.group(1)) if alt else title))
        rankings[name]=out
    return date.isoformat(),rankings
def fetch_page():
    req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=25) as resp:return resp.read(700000).decode("utf-8","replace")
def build(today,fetcher=fetch_page,tmdb=request):
    date,rankings=parse_page(fetcher(),today)
    entries=[]
    for provider,items in rankings.items():
        for rank,(title,original) in enumerate(items,1):
            rows=tmdb("/search/tv",{"query":original,"language":"en-US"}).get("results",[])
            match=next((r for r in rows if (r.get("original_name") or "").casefold()==original.casefold()),None)
            if match is None:match=rows[0] if rows else {}
            entries.append({"rank":rank,"title":title,"originalTitle":original,"platform":provider,
              "tmdbId":match.get("id") or 0,"posterPath":match.get("backdrop_path") or match.get("poster_path") or "",
              "genreIds":match.get("genre_ids") or [],"rating":match.get("vote_average") or 0,
              "providersPL":[provider],"tmdbUrl":f"https://www.themoviedb.org/tv/{match['id']}" if match.get("id") else ""})
    return {"region":"PL","category":"netflix_hbomax_sky_prime_daily_tv_pl","source":"TVHUB","sourceUrl":URL,
            "datePL":date,"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
            "series":entries,"perPlatformCounts":{"Netflix":10,"HBO Max":10,"SkyShowtime":10,"Prime Video":10},
            "note":"Unofficial third-party daily country TV charts; may lag up to 3 days"}
def main():
    today=dt.datetime.now(ZoneInfo("Europe/Warsaw")).date()
    data=build(today)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("NETFLIX/HBO/SKY/PRIME TV:",data["datePL"],len(data["series"]))
if __name__=="__main__":main()
