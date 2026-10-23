#!/usr/bin/env python3
"""Popular recently released movies available via a PL subscription provider; TMDB is not view counts."""
import datetime as dt
import json
import pathlib
import zoneinfo
from build_tmdb_series import request

OUT=pathlib.Path("out/tmdb_movies_popular_pl.json")
def build(today,getter=request):
    found={}
    for path,params in [
       ("/trending/movie/week",{"language":"pl-PL"}),
       ("/movie/now_playing",{"language":"pl-PL","region":"PL","page":1}),
       ("/movie/popular",{"language":"pl-PL","page":1}),
       ("/movie/popular",{"language":"pl-PL","page":2}),
    ]:
        for m in getter(path,params).get("results",[]):
            if m.get("id"):
                found[m["id"]]=m
    movies=[]
    for id,m in found.items():
        date=m.get("release_date") or ""
        try: age=(today-dt.date.fromisoformat(date)).days
        except ValueError: continue
        # Up to a year old, NOT labeled as a new VOD premiere.
        if age<0 or age>365: continue
        pl=getter(f"/movie/{id}/watch/providers").get("results",{}).get("PL",{})
        names=sorted({p.get("provider_name") for p in pl.get("flatrate",[]) if p.get("provider_name")})
        if not names: continue
        movies.append({"tmdbId":id,"title":m.get("title") or m.get("original_title") or "",
          "releaseDate":date,"posterPath":m.get("backdrop_path") or m.get("poster_path"),
          "popularityTMDB":float(m.get("popularity") or 0),"rating":float(m.get("vote_average") or 0),
          "providersPL":names,"tmdbUrl":f"https://www.themoviedb.org/movie/{id}",
          "status":"POPULAR_NOW_SERIES_LEVEL_PROVIDER_MATCH",
          "caveat":"TMDB popularity is not viewing figures; provider availability may lag."})
    movies.sort(key=lambda x:(x["popularityTMDB"],x["releaseDate"]),reverse=True)
    return {"region":"PL","source":"TMDB","category":"popular_movies_now","movies":movies[:10],
            "candidateCount":len(movies),"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat()}
def main():
    today=dt.datetime.now(zoneinfo.ZoneInfo("Europe/Warsaw")).date()
    data=build(today)
    if not data["movies"]: raise SystemExit("No available film candidates; preserving previous feed")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("TMDB MOVIES:",len(data["movies"]),"candidates:",data["candidateCount"])
if __name__=="__main__": main()
