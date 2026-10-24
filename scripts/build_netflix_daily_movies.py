#!/usr/bin/env python3
"""Daily Poland Netflix movie chart via FlixPatrol (unofficial third-party chart).
Do not publish stale/partial rankings; TMDB only enriches artwork and genres.
"""
import datetime as dt
import json
import os
import pathlib
import re
import urllib.request
from html.parser import HTMLParser
from zoneinfo import ZoneInfo
from build_tmdb_series import request

OUT=pathlib.Path("out/netflix_daily_movies_pl.json")

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_a=False;self.href="";self.text="";self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self.href=dict(attrs).get("href","");self.in_a=True;self.text=""
    def handle_data(self,data):
        if self.in_a:self.text+=data
    def handle_endtag(self,tag):
        if tag=="a" and self.in_a:
            self.links.append((self.href,self.text.strip()))
            self.in_a=False

def extract_movies(html):
    # Limit the extraction to the Movies section, excluding TV and navigation.
    start=re.search(r"TOP 10 Movies",html,re.I)
    end=re.search(r"TOP 10 TV Shows",html[start.end():] if start else "",re.I)
    if not start or not end:raise ValueError("Missing movies/TV section markers")
    section=html[start.end():start.end()+end.start()]
    p=Links();p.feed(section)
    titles=[]
    for href,title in p.links:
        if re.search(r"/title/|/streaming-services/",href) and title and title not in titles:
            titles.append(title)
    if len(titles)!=10:raise ValueError(f"Expected 10 movie titles, got {len(titles)}")
    return titles

def fetch_chart(today):
    url=f"https://flixpatrol.com/top10/netflix/poland/{today.isoformat()}/"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=25) as r:
        html=r.read(1000000).decode("utf-8","replace")
    if today.strftime("%B") not in html and today.isoformat() not in html:
        raise ValueError("Ranking date cannot be verified; refusing publication")
    return extract_movies(html),url

def build(today,chart=fetch_chart,tmdb=request):
    titles,url=chart(today)
    films=[]
    for rank,title in enumerate(titles,1):
        search=tmdb("/search/movie",{"query":title,"language":"pl-PL"})
        rows=search.get("results",[])
        match=next((m for m in rows if m.get("title","").casefold()==title.casefold() or m.get("original_title","").casefold()==title.casefold()),None)
        if match is None: match=rows[0] if rows else {}
        films.append({"rank":rank,"title":title,"tmdbId":match.get("id",0),
         "posterPath":match.get("backdrop_path") or match.get("poster_path") or "",
         "genreIds":match.get("genre_ids") or [],"rating":match.get("vote_average") or 0,
         "providersPL":["Netflix"],"tmdbUrl":f"https://www.themoviedb.org/movie/{match['id']}" if match.get("id") else ""})
    return {"region":"PL","category":"netflix_daily_movies_pl","source":"FlixPatrol",
     "sourceUrl":url,"datePL":today.isoformat(),"movies":films,
     "generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
     "note":"Third-party daily ranking; not Netflix's official weekly chart"}

def main():
    today=dt.datetime.now(ZoneInfo("Europe/Warsaw")).date()
    data=build(today)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("NETFLIX DAILY MOVIES:",len(data["movies"]),data["datePL"])
if __name__=="__main__":main()
