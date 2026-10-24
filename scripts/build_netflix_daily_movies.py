#!/usr/bin/env python3
"""Daily Netflix Poland movies from TVHUB (unofficial; source dated)."""
import datetime as dt, json, html, pathlib, re, urllib.request
from zoneinfo import ZoneInfo
from build_tmdb_series import request
OUT=pathlib.Path("out/netflix_daily_movies_pl.json")
def parse_chart(raw,today):
    m=re.search(r'<section class="tvhub-fp".*?<time datetime="(\d{4}-\d\d-\d\d)"',raw,re.S)
    if not m:raise ValueError("No dated chart")
    date=dt.date.fromisoformat(m.group(1))
    if (today-date).days not in (0,1,2,3):raise ValueError("Stale or future date")
    begin=raw.find('data-fp-type-panel="movie"',m.end())
    end=raw.find('data-fp-type-panel="tv"',begin)
    if begin<0 or end<begin:raise ValueError("Movie panel missing")
    block=re.search(r'<article class="tvhub-fp__card tvhub-fp__card--netflix"[^>]*>(.*?)</article>',raw[begin:end],re.S)
    if not block:raise ValueError("Netflix movie section missing")
    rows=re.findall(r'<span class="tvhub-fp__title">(.*?)</span>',block.group(1),re.S)
    if len(rows)!=10:raise ValueError(f"Expected 10 titles, got {len(rows)}")
    clean=lambda x:html.unescape(re.sub(r"<[^>]*>","",x)).strip()
    result=[]
    for row in rows:
        alt=re.search(r"<small>(.*?)</small>",row,re.S)
        title=clean(re.sub(r"<small>.*?</small>","",row,flags=re.S))
        if not title:raise ValueError("Empty title")
        result.append((title,clean(alt.group(1)) if alt else title))
    return date.isoformat(),result
def fetch_chart(today):
    req=urllib.request.Request("https://tvhub.pl/",headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=20) as resp: raw=resp.read(700000).decode("utf-8","replace")
    return parse_chart(raw,today)
def build(today,source=fetch_chart,tmdb=request):
    date,items=source(today)
    movies=[]
    for rank,(title,original) in enumerate(items,1):
        rows=tmdb("/search/movie",{"query":original,"language":"en-US"}).get("results",[])
        match=next((r for r in rows if r.get("original_title","").casefold()==original.casefold()),None)
        if match is None:match=rows[0] if rows else {}
        movies.append({"rank":rank,"title":title,"originalTitle":original,"tmdbId":match.get("id") or 0,
            "posterPath":match.get("backdrop_path") or match.get("poster_path") or "",
            "genreIds":match.get("genre_ids") or [],"rating":match.get("vote_average") or 0,
            "providersPL":["Netflix"],"tmdbUrl":f"https://www.themoviedb.org/movie/{match['id']}" if match.get("id") else ""})
    return {"region":"PL","category":"netflix_daily_movies_pl","source":"TVHUB","sourceUrl":"https://tvhub.pl/",
            "datePL":date,"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
            "movies":movies,"note":"Unofficial third-party daily chart, may lag up to 3 days"}
def main():
    today=dt.datetime.now(ZoneInfo("Europe/Warsaw")).date()
    data=build(today)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("NETFLIX PL DAILY:",data["datePL"],len(data["movies"]))
if __name__=="__main__":main()
