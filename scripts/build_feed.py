
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
API = "https://api.themoviedb.org/3"

LIMIT = 20
MAX_PAGES = 8
WARSAW = ZoneInfo("Europe/Warsaw")


def request(path, params):
    if not TOKEN:
        raise RuntimeError("Brak sekretu TMDB_READ_TOKEN")

    query = urllib.parse.urlencode(params)
    url = API + path + "?" + query

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + TOKEN,
            "Accept": "application/json",
            "User-Agent": "FreeTV-VOD-Feed/1.0",
        },
    )

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


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


def collect(media_type, category):
    """Pobieranie produkcji z dostepnoscia VOD w Polsce."""

    found = []
    seen = set()

    is_movie = media_type == "movie"
    date_field = "primary_release_date" if is_movie else "first_air_date"
    api_date_field = "release_date" if is_movie else "first_air_date"

    for page in range(1, MAX_PAGES + 1):
        params = {
            "language": "pl-PL",
            "region": "PL",
            "watch_region": "PL",
            "with_watch_monetization_types": "flatrate|free|ads|rent|buy",
            "include_adult": "false",
            "sort_by": (
                date_field + ".desc"
                if category == "new"
                else "popularity.desc"
            ),
            "page": page,
        }

        if category == "new":
            params[date_field + ".gte"] = date_days_ago(29)
            params[date_field + ".lte"] = today_string()

        data = request("/discover/" + media_type, params)

        for item in data.get("results", []):
            tmdb_id = item.get("id")
            if not isinstance(tmdb_id, int) or tmdb_id in seen:
                continue

            seen.add(tmdb_id)

            original = (
                item.get("original_title")
                if is_movie
                else item.get("original_name")
            ) or ""

            title = (
                item.get("title")
                if is_movie
                else item.get("name")
            ) or original

            date_value = item.get(api_date_field) or ""
            premiered = safe_date(date_value)

            if category == "new":
                if premiered is None:
                    continue

                age = (
                    dt.datetime.now(WARSAW).date() - premiered
                ).days

                if not 0 <= age <= 29:
                    continue

            poster_path = item.get("poster_path")
            if not poster_path:
                continue

            details = request(
                "/" + media_type + "/" + str(tmdb_id),
                {
                    "language": "pl-PL",
                    "append_to_response": "watch/providers",
                },
            )

            providers_data = (
                details.get("watch/providers", {})
                .get("results", {})
                .get("PL", {})
            )

            providers = []
            provider_ids = set()

            for group in ("flatrate", "free", "ads", "rent", "buy"):
                for provider in providers_data.get(group, []):
                    provider_id = provider.get("provider_id")
                    name = provider.get("provider_name")

                    if provider_id in provider_ids or not name:
                        continue

                    provider_ids.add(provider_id)
                    providers.append(name)

            # Nie pokazujemy tytulow bez potwierdzonej
            # aktualnej dostepnosci VOD na TMDB dla Polski.
            if not providers:
                continue

            description = details.get("overview") or item.get(
                "overview"
            ) or ""

            result = {
                "kind": media_type,
                "tmdbId": tmdb_id,
                "title": title.strip(),
                "originalTitle": original.strip(),
                "description": description.strip(),
                "releaseDate": date_value,
                "year": date_value[:4] if date_value else "",
                "posterUrl": (
                    "https://image.tmdb.org/t/p/w500"
                    + poster_path
                ),
                "artworkUrl": (
                    "https://image.tmdb.org/t/p/w780"
                    + poster_path
                ),
                "rating": details.get("vote_average", 0),
                "ratingSource": "TMDB",
                "providers": providers,
                "availabilityRegion": "PL",
                "source": "TMDB",
                "url": (
                    "https://www.themoviedb.org/"
                    + media_type
                    + "/"
                    + str(tmdb_id)
                ),
            }

            if category == "new":
                result["newnessBasis"] = "production_release_date"
                result["vodAddedAt"] = None
                result["vodAdditionVerified"] = False

            found.append(result)

            if len(found) >= LIMIT:
                return found

        total_pages = data.get("total_pages", 1)
        if page >= total_pages:
            break

    return found


def remove_duplicates(new_items, popular_items):
    """Jeden tytul tylko w jednej sekcji tego samego typu."""

    new_ids = {item["tmdbId"] for item in new_items}

    popular = [
        item for item in popular_items
        if item["tmdbId"] not in new_ids
    ]

    return popular[:LIMIT]


def main():
    if not TOKEN:
        raise RuntimeError(
            "Nie ustawiono TMDB_READ_TOKEN w GitHub Actions"
        )

    print("Pobieranie nowosci filmowych...")
    new_movies = collect("movie", "new")

    print("Pobieranie popularnych filmow...")
    popular_movies = collect("movie", "popular")

    print("Pobieranie nowosci serialowych...")
    new_series = collect("tv", "new")

    print("Pobieranie popularnych seriali...")
    popular_series = collect("tv", "popular")

    popular_movies = remove_duplicates(
        new_movies, popular_movies
    )
    popular_series = remove_duplicates(
        new_series, popular_series
    )

    now = dt.datetime.now(dt.timezone.utc)

    feed = {
        "region": "PL",
        "generatedAt": now.replace(
            microsecond=0
        ).isoformat().replace("+00:00", "Z"),
        "source": "TMDB",
        "newnessPolicy": (
            "Recent releases from the last 30 calendar days "
            "currently listed as available on Polish VOD. "
            "VOD addition dates are not verified."
        ),
        "filmwebVerified": False,
        "newMovies": new_movies,
        "popularMovies": popular_movies,
        "newSeries": new_series,
        "popularSeries": popular_series,
        "movies": new_movies + popular_movies,
        "series": new_series + popular_series,
    }

    # Nie nadpisuj ostatniego katalogu, gdy API
    # nie zwrocilo zadnych pozycji.
    if not any((
        new_movies,
        popular_movies,
        new_series,
        popular_series,
    )):
        raise RuntimeError(
            "TMDB nie zwrocilo zadnych pozycji. "
            "Poprzedni katalog pozostaje bez zmian."
        )

    OUTPUT.write_text(
        json.dumps(feed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "Zapisano: "
        f"{len(new_movies)} nowych filmow, "
        f"{len(popular_movies)} popularnych filmow, "
        f"{len(new_series)} nowych seriali, "
        f"{len(popular_series)} popularnych seriali."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("BLAD:", error, file=sys.stderr)
        sys.exit(1)
