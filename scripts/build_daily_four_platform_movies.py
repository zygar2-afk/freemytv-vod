#!/usr/bin/env python3
"""Four TVHUB Poland daily film top tens; third-party rankings, TMDB artwork."""
import datetime as dt
import html
import json
import pathlib
import re
import urllib.request
from zoneinfo import ZoneInfo
from build_tmdb_series import request

OUTPUT=pathlib.Path("out/netflix_hbomax_sky_prime_daily_movies_pl.json")
PLATFORMS=(("netflix","Netflix"),("hbo-max","HBO Max"),("skyshowtime","SkyShowtime"),("amazon-prime","Prime Video"))

def clean(value):
    return html.unescape(re.sub(r"<[^>]+>","",value)).strip()

def extract(html_page, today):
    match=re.search(r'<section class="tvhub-fp".*?<time datetime="(\d{4}-\d\d-\d\d)"',html_page,re.S)
    if not match:raise ValueError("No dated Polish streaming ranking")
    date=dt.date.fromisoformat(match.group(1))
    if (today-date).days not in (0,1,2,3):
        raise ValueError(f"Ranking outside current window: {date}")
    start=re.search(r'<div[^>]*data-fp-type-panel="movie"[^>]*>',html_page[match.end():])
    if not start:raise ValueError("Movies panel missing")
    begin=match.end()+start.start()
    end=html_page.find('</section>',begin)
    panel=html_page[begin:end if end>begin else None]
    rankings={}
    for slug, platform in PLATFORMS:
        section=re.search(r'<article[^>]*class="[^"]*tvhub-fp__card--'+slug+r'[^"]*"[^>]*>(.*?)</article>',panel,re.S)
        if not section:raise ValueError(f"{platform}: card missing")
        rows=re.findall(r'<span class="tvhub-fp__title">(.*?)</span>',section.group(1),re.S)
        if len(rows)!=10:raise ValueError(f"{platform}: {len(rows)} entries instead of 10")
        titles=[]
        for row in rows:
            original_match=re.search(r'<small>(.*?)</small>',row,re.S)
            title=clean(re.sub(r'<small>.*?</small>','',row,flags=re.S))
            original=clean(original_match.group(1)) if original_match else title
            if not title:raise ValueError(f"{platform}: empty title")
            titles.append((title,original))
        rankings[platform]=titles
    return date.isoformat(),rankings

def fetch_page():
    req=urllib.request.Request("https://tvhub.pl/",headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=25) as response:
        return response.read(800000).decode("utf-8","replace")

def build(today, page_loader=fetch_page, tmdb=request):
    date,rankings=extract(page_loader(),today)
    movies=[]
    for slug,platform in PLATFORMS:
        for rank,(title,original) in enumerate(rankings[platform],1):
            results=tmdb("/search/movie",{"query":original,"language":"en-US"}).get("results",[])
            matched=next((r for r in results if (r.get("original_title") or "").casefold()==original.casefold()),None)
            if matched is None:matched=results[0] if results else {}
            movies.append({"rank":rank,"title":title,"originalTitle":original,
                           "platform":platform,"tmdbId":matched.get("id") or 0,
                           "posterPath":matched.get("backdrop_path") or matched.get("poster_path") or "",
                           "genreIds":matched.get("genre_ids") or [],
                           "rating":matched.get("vote_average") or 0,
                           "providersPL":[platform],
                           "tmdbUrl":f"https://www.themoviedb.org/movie/{matched['id']}" if matched.get("id") else ""})
    if len(movies)!=40:raise ValueError("Incomplete chart")
    return {"region":"PL","category":"netflix_hbomax_sky_prime_daily_movies_pl",
            "source":"TVHUB","sourceUrl":"https://tvhub.pl/","datePL":date,
            "generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
            "perPlatformCounts":{name:10 for _,name in PLATFORMS},
            "movies":movies,
            "note":"Unofficial Polish daily ranking; published date may lag up to three days"}

def main():
    data=build(dt.datetime.now(ZoneInfo("Europe/Warsaw")).date())
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("DAILY TOP40 FILMS:",data["datePL"],len(data["movies"]))
if __name__=="__main__":main()
