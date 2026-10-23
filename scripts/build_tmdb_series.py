#!/usr/bin/env python3
"""Experimental TOP recent TV premieres from TMDB. No credentials in outputs."""
import datetime as dt
import json
import os
import pathlib
import urllib.parse
import urllib.request
import zoneinfo

DAYS = 21
OUTPUT = pathlib.Path("out/tmdb_series_21d.json")
API = "https://api.themoviedb.org/3"

def within(value, today):
    try:
        diff = (today - dt.date.fromisoformat(value)).days
        return 0 <= diff < DAYS
    except (ValueError, TypeError):
        return False

def new_season(series, today):
    """A season's first scheduled date, not a newly uploaded old episode."""
    matches = []
    for season in series.get("seasons", []):
        number = season.get("season_number")
        if not isinstance(number, int) or number < 1:
            continue
        date = season.get("air_date")
        if within(date, today):
            matches.append((date, number))
    return max(matches) if matches else None

def classify(series, today):
    premiere = new_season(series, today)
    if premiere is None:
        return None
    date, number = premiere
    return {"event": "new_series_premiere" if number == 1 else "new_season_premiere",
            "seasonNumber": number, "premiereDate": date}

def providers_pl(data):
    pl = data.get("results", {}).get("PL", {})
    names = sorted({p.get("provider_name") for p in pl.get("flatrate", []) if p.get("provider_name")})
    return names, pl.get("link")

def request(path, params=None):
    token = os.getenv("TMDB_READ_TOKEN", "").strip()
    key = os.getenv("TMDB_API_KEY", "").strip()
    if not token and not key:
        raise RuntimeError("TMDB_READ_TOKEN or TMDB_API_KEY GitHub Actions secret is required")
    query = dict(params or {})
    if not token:
        query["api_key"] = key
    url = API + path + "?" + urllib.parse.urlencode(query)
    headers = {"Accept": "application/json", "User-Agent": "CinemaEditionExperiment/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as r:
        return json.load(r)

def build(today, getter=request):
    # Discover candidates from both trending and recent on-the-air listings.
    ids = {}
    for path, params in (
        ("/trending/tv/week", {"language":"pl-PL"}),
        ("/tv/on_the_air", {"language":"pl-PL", "page":1}),
        ("/tv/on_the_air", {"language":"pl-PL", "page":2}),
        ("/tv/on_the_air", {"language":"pl-PL", "page":3}),
    ):
        for entry in getter(path, params).get("results", []):
            if entry.get("id"):
                ids[entry["id"]] = entry
    result = []
    for identifier, brief in ids.items():
        show = getter(f"/tv/{identifier}", {"language":"pl-PL"})
        evidence = classify(show, today)
        if evidence is None:
            continue
        names, link = providers_pl(getter(f"/tv/{identifier}/watch/providers"))
        if not names:
            continue
        result.append({
            "tmdbId":identifier, "title":show.get("name") or brief.get("name"),
            "season":evidence["seasonNumber"], "premiereDate":evidence["premiereDate"],
            "premiereType":evidence["event"], "providersPL":names,
            "providerInfoUrl":link, "tmdbUrl":f"https://www.themoviedb.org/tv/{identifier}",
            "posterPath":show.get("poster_path"),
            "popularityTMDB":float(brief.get("popularity") or show.get("popularity") or 0),
            "status":"TMDB_SEASON_DATE_AND_SERIES_PROVIDER_MATCH",
            "caveat":"Polish provider match is series-level; season-specific PL availability is unverified"
        })
    result.sort(key=lambda x:(x["popularityTMDB"],x["premiereDate"]),reverse=True)
    return {"region":"PL", "windowDays":DAYS,"generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
            "source":"TMDB", "rankingMetric":"TMDB popularity, not streaming views",
            "seasonSpecificPolishAvailabilityVerified":False,
            "series":result[:10], "candidateCount":len(result)}

def main():
    today = dt.datetime.now(zoneinfo.ZoneInfo("Europe/Warsaw")).date()
    data = build(today)
    OUTPUT.parent.mkdir(exist_ok=True, parents=True)
    OUTPUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("TMDB SERIES:",len(data["series"]),"candidates:",data["candidateCount"])
    if not data["series"]:
        raise SystemExit("No verified season-date + series-level PL-provider candidates; do not overwrite feed")

if __name__ == "__main__":
    main()
