#!/usr/bin/env python3
"""FreeTV: codzienny katalog filmow i seriali z TMDB."""

import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "vod_recommendations.json"

TOKEN = os.environ.get("TMDB_READ_TOKEN", "").strip()
API_KEY = os.environ.get("TMDB_API_KEY", "").strip()
API = "https://api.themoviedb.org/3"

LIMIT = 60
MAX_PAGES = 8
WARSAW = ZoneInfo("Europe/Warsaw")


def request(path, params):
    """Use the TMDB v3 key first, or fall back to a valid v4 read token.

    Never log or include credentials in error output.
    """
    if not TOKEN and not API_KEY:
        raise RuntimeError("Brak TMDB_API_KEY oraz TMDB_READ_TOKEN w GitHub Secrets")

    credentials = []
    if API_KEY:
        credentials.append(("TMDB_API_KEY", {"api_key": API_KEY}, {}))
    if TOKEN:
        credentials.append(("TMDB_READ_TOKEN", {}, {
            "Authorization": "Bearer " + TOKEN,
        }))

    for name, auth_query, auth_headers in credentials:
        query = urllib.parse.urlencode({**params, **auth_query})
        url = API + path + "?" + query
        req = urllib.request.Request(
            url,
            headers={
                **auth_headers,
                "Accept": "application/json",
                "User-Agent": "FreeTV-VOD-Feed/1.1",
            },
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=25) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if error.code in (401, 403):
                    print(
                        f"TMDB authentication rejected {name} (HTTP {error.code}); "
                        "trying another configured credential.",
                        file=sys.stderr,
                    )
                    break
                if error.code == 429 or 500 <= error.code < 600:
                    if attempt < 2:
                        time.sleep(2 * (attempt + 1))
                        continue
                raise RuntimeError(
                    f"TMDB HTTP {error.code} on {path}; credentials hidden"
                ) from None
            except (urllib.error.URLError, TimeoutError):
                if attempt == 2:
                    raise RuntimeError(
                        f"TMDB network error on {path}; credentials hidden"
                    ) from None
                time.sleep(2 * (attempt + 1))

    raise RuntimeError(
        "TMDB rejected every configured credential (401/403). "
        "Set a genuine TMDB v3 API key or v4 API Read Access Token "
        "in the repository Actions secrets."
    )


def select_trailer(videos):
    """Prefer official YouTube trailers; use teasers only as a fallback."""
    candidates = []
    for video in videos:
        if (video.get("site") != "YouTube" or not video.get("key")):
            continue
        if video.get("type") not in ("Trailer", "Teaser"):
            continue
        key = video["key"]
        if not isinstance(key, str) or len(key) != 11:
            continue
        candidates.append(video)
    if not candidates:
        return None
    candidates.sort(
        key=lambda v: (
            v.get("type") == "Trailer",
            v.get("official") is True,
            v.get("iso_639_1") == "pl",
            v.get("published_at", ""),
        ),
        reverse=True,
    )
    return candidates[0]["key"]


def trailer_key(media_type, tmdb_id, details):
    videos = details.get("videos", {}).get("results", [])
    key = select_trailer(videos)
    if key:
        return key
    english = request(
        f"/{media_type}/{tmdb_id}/videos", {"language": "en-US"}
    )
    return select_trailer(english.get("results", []))


def genre_names(details):
    """TMDB localized (pl-PL) genres. Limit cards to two."""
    genres = details.get("genres", [])
    names = []
    for genre in genres:
        name = genre.get("name", "").strip()
        if name and name not in names:
            names.append(name)
        if len(names) == 2:
            break
    return names


def date_days_ago(days):
    today = dt.datetime.now(WARSAW).date()
    return (today - dt.timedelta(days=days)).isoformat()


def today_string():
    return dt.datetime.now(WARSAW).date().isoformat()


def safe_date(value):
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


PLATFORMS = ("Netflix", "HBO Max", "Disney+", "Prime Video", "Apple TV+", "SkyShowtime")


def platform(name):
    return {"netflix": "Netflix", "hbo max": "HBO Max", "max": "HBO Max",
            "disney plus": "Disney+", "disney+": "Disney+",
            "amazon prime video": "Prime Video", "prime video": "Prime Video",
            "apple tv": "Apple TV+", "apple tv+": "Apple TV+",
            "apple tv amazon channel": "Apple TV+", "skyshowtime": "SkyShowtime"}.get(name.lower().strip())


def providers(details):
    # Only subscription availability; rental/store entries do not count.
    pl = details.get("watch/providers", {}).get("results", {}).get("PL", {})
    return sorted({platform(p.get("provider_name", "")) for p in pl.get("flatrate", [])
                   if platform(p.get("provider_name", ""))}, key=PLATFORMS.index)


def newness(details, kind):
    today = dt.datetime.now(WARSAW).date()
    release = details.get("release_date" if kind == "movie" else "first_air_date") or ""
    choices = [(release, "production_release_date")]
    if kind == "tv":
        choices += [(s.get("air_date") or "", "season_release_date")
                    for s in details.get("seasons", []) if s.get("season_number", 0) > 0]
    valid = [(date, basis) for date, basis in choices
             if safe_date(date) is not None and 0 <= (today-safe_date(date)).days <= 29]
    return max(valid, default=("", ""))


def collect(media_type):
    movie = media_type == "movie"
    date_field = "primary_release_date" if movie else "first_air_date"
    provider_data = request("/watch/providers/" + media_type, {"watch_region": "PL", "language": "pl-PL"})
    ids = [str(p["provider_id"]) for p in provider_data.get("results", [])
           if platform(p.get("provider_name", ""))]
    if not ids:
        raise RuntimeError("Brak identyfikatorow wymaganych platform dla Polski")
    found = {}
    # Also discover older series with recent episodes, then verify a NEW SEASON date.
    # A recent episode alone is never sufficient to label a series as new.
    for seasons in ([False] if movie else [False, True]):
        for page in range(1, MAX_PAGES + 1):
            params = {"language": "pl-PL", "region": "PL", "watch_region": "PL",
                      "with_watch_monetization_types": "flatrate", "with_watch_providers": "|".join(ids),
                      "include_adult": "false", "sort_by": date_field + ".desc", "page": page}
            if seasons:
                params.update({"air_date.gte": date_days_ago(29), "air_date.lte": today_string(),
                               "first_air_date.lte": date_days_ago(30)})
            else:
                params.update({date_field + ".gte": date_days_ago(29), date_field + ".lte": today_string()})
            data = request("/discover/" + media_type, params)
            for item in data.get("results", []):
                identity = item.get("id")
                if not isinstance(identity, int) or identity in found:
                    continue
                details = request(f"/{media_type}/{identity}",
                                  {"language": "pl-PL", "append_to_response": "watch/providers,videos"})
                supported = providers(details)
                date, basis = newness(details, media_type)
                poster = details.get("poster_path") or item.get("poster_path")
                title = details.get("title" if movie else "name") or ""
                if not supported or not date or not poster or not title:
                    continue
                trailer = trailer_key(media_type, identity, details)
                release = details.get("release_date" if movie else "first_air_date") or ""
                found[identity] = {"kind": media_type, "tmdbId": identity, "title": title,
                    "originalTitle": details.get("original_title" if movie else "original_name") or title,
                    "description": details.get("overview") or "", "releaseDate": release,
                    "seasonReleaseDate": date if basis == "season_release_date" else None,
                    "newnessDate": date, "newnessBasis": basis, "year": release[:4],
                    "posterUrl": "https://image.tmdb.org/t/p/w500" + poster,
                    "artworkUrl": "https://image.tmdb.org/t/p/w780" + poster,
                    "rating": details.get("vote_average", 0), "voteCount": details.get("vote_count", 0),
                    "ratingSource": "TMDB", "genres": genre_names(details), "trailerYoutubeKey": trailer,
                    "providers": supported, "availabilityRegion": "PL", "source": "TMDB",
                    "url": f"https://www.themoviedb.org/{media_type}/{identity}",
                    "vodAddedAt": None, "vodAdditionVerified": False}
            if page >= data.get("total_pages", 1):
                break
    return sorted(found.values(), key=lambda i: (i["newnessDate"], -i["tmdbId"]), reverse=True)[:LIMIT]


def main():
    if not TOKEN and not API_KEY:
        raise RuntimeError("Brak klucza TMDB w GitHub Secrets")
    movies, series = collect("movie"), collect("tv")
    if not movies and not series:
        raise RuntimeError("Pusty katalog; poprzedni plik pozostaje bez zmian")
    feed = {"schemaVersion": 2, "region": "PL", "generatedAt": dt.datetime.now(dt.timezone.utc)
            .replace(microsecond=0).isoformat().replace("+00:00", "Z"), "source": "TMDB",
            "newnessPolicy": "Last 30 calendar days: production or season premiere. VOD addition dates are not verified.",
            "newMovies": movies, "newSeries": series, "popularMovies": [], "popularSeries": [],
            "movies": movies, "series": series}
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    print(f"Zapisano {len(movies)} filmow i {len(series)} seriali")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("BLAD:", error, file=sys.stderr)
        sys.exit(1)
