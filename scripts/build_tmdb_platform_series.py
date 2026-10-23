#!/usr/bin/env python3
"""Top 30 TMDB popularity among TV series available via PL subscriptions.
Not an official Netflix/Max/SkyShowtime viewing chart.
"""
import datetime as dt
import json
import pathlib
import zoneinfo
from build_tmdb_series import request

OUT = pathlib.Path("out/tmdb_series_platform_top10_pl.json")
PLATFORMS = {"Netflix", "SkyShowtime", "HBO Max", "Apple TV+"}
def normalize_provider(name, provider_id=None):
    if provider_id == 350: return "Apple TV+"
    s = (name or "").casefold().replace(" ", "")
    if "netflix" in s: return "Netflix"
    if "skyshowtime" in s: return "SkyShowtime"
    if s in ("hbomax", "max"): return "HBO Max"
    if s in ("appletvplus", "appletv+"): return "Apple TV+"
    return None

def build(today, getter=request):
    candidates = {}
    for path, args in [
        ("/trending/tv/week", {"language":"pl-PL"}),
        *[("/tv/popular",{"language":"pl-PL","page":i}) for i in range(1,7)],
        ("/tv/on_the_air",{"language":"pl-PL","page":1}),
    ]:
        for show in getter(path,args).get("results",[]):
            key=show.get("id")
            if key and (key not in candidates or
                    float(show.get("popularity") or 0)>float(candidates[key].get("popularity") or 0)):
                candidates[key]=show
    results=[]
    for id,show in candidates.items():
        first_air = show.get('first_air_date') or ''
        try:
            if dt.date.fromisoformat(first_air).year < 2025: continue
        except ValueError:
            continue
        pl=getter(f"/tv/{id}/watch/providers").get("results",{}).get("PL",{})
        providers=sorted({mapped for p in pl.get("flatrate",[])
                  if (mapped:=normalize_provider(p.get("provider_name"), p.get("provider_id")))})
        if not providers: continue
        title=(show.get("name") or show.get("original_name") or "").strip()
        if not title: continue
        results.append({"tmdbId":id,"title":title, "firstAirDate":first_air, "providersPL":providers,
            "posterPath":show.get("backdrop_path") or show.get("poster_path"),
            "genreIds":show.get("genre_ids") or [],
            "rating":float(show.get("vote_average") or 0),
            "popularityTMDB":float(show.get("popularity") or 0),
            "tmdbUrl":f"https://www.themoviedb.org/tv/{id}",
            "availabilityScope":"series-level subscription listing in Poland",
            "status":"POPULAR_NOW_NOT_OFFICIAL_VIEWS"})
    results.sort(key=lambda x:(x["popularityTMDB"],x["rating"]), reverse=True)
    return {"region":"PL","source":"TMDB","category":"platform_series_popular_now",
        "platforms":["Netflix","SkyShowtime","HBO Max","Apple TV+"], "rankingMetric":"TMDB popularity; not platform viewing figures",
        "datePL":today.isoformat(),"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "series":results[:30],"candidateCount":len(results)}

def main():
    today=dt.datetime.now(zoneinfo.ZoneInfo("Europe/Warsaw")).date()
    data=build(today)
    if not data["series"]: raise SystemExit("No series; keeping prior published feed")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PL PLATFORM SERIES:",len(data["series"]),"candidates:",data["candidateCount"])

if __name__=="__main__": main()
