#!/usr/bin/env python3
"""Publish verified Polish VOD additions from a maintained input dataset.
This DOES NOT scrape Filmweb or discover VOD premieres itself.
"""
import datetime as dt
import json
import pathlib
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data' / 'verified_titles.json'
TARGET = ROOT / 'vod_recommendations.json'
WARSAW = dt.timezone(dt.timedelta(hours=1))  # publication timestamp UTC is sufficient; dates evaluated in Warsaw separately


def valid_filmweb_url(value):
    if not isinstance(value, str):
        return False
    url = urllib.parse.urlsplit(value)
    return url.scheme == 'https' and url.hostname in ('filmweb.pl', 'www.filmweb.pl') and bool(url.path.strip('/'))


def validate(row, today):
    if not isinstance(row, dict) or row.get('kind', 'movie') != 'movie':
        return None
    title = row.get('title', '')
    if not isinstance(title, str) or not title.strip():
        return None
    try:
        added = dt.date.fromisoformat(row['vodAddedAt'])
    except (ValueError, KeyError, TypeError):
        return None
    # Match 7 latest calendar dates, including today. Exclude tomorrow and older dates.
    if not 0 <= (today - added).days <= 6:
        return None
    providers = row.get('providers')
    if not isinstance(providers, list) or not providers or any(not isinstance(p, dict) or not isinstance(p.get('name'), str) or not p['name'].strip() for p in providers):
        return None
    # Explicit source for the actual POLISH VOD addition, not a cinema or general availability date.
    vod_source = row.get('vodSource')
    if not isinstance(vod_source, str) or not vod_source.startswith('https://'):
        return None
    fw = row.get('filmweb')
    if not isinstance(fw, dict):
        return None
    rating = fw.get('userRating')
    votes = fw.get('votes')
    rating_url = fw.get('ratingSource', '')
    editorial_url = fw.get('editorialSource', '')
    rated = (type(rating) in (float, int) and type(votes) is int and
             7 <= rating <= 10 and votes >= 100 and valid_filmweb_url(rating_url))
    editorial = fw.get('editorialRecommended') is True and valid_filmweb_url(editorial_url)
    if not rated and not editorial:
        return None
    # Refuse to transmit unsupported display claims, even when a manual record is malformed.
    result = dict(row)
    result['title'] = title.strip()
    result['filmweb'] = dict(fw)
    if not rated:
        result['filmweb']['userRating'] = None
        result['filmweb']['votes'] = 0
        result['filmweb']['ratingSource'] = None
    if not editorial:
        result['filmweb']['editorialRecommended'] = False
        result['filmweb']['editorialSource'] = None
    image = row.get('artworkUrl', '')
    image_url = urllib.parse.urlsplit(image) if isinstance(image, str) else None
    if not image_url or image_url.scheme != 'https' or image_url.hostname != 'image.tmdb.org' or not image_url.path.startswith('/t/p/'):
        result['artworkUrl'] = ''
    return result


def build():
    source = json.loads(SOURCE.read_text(encoding='utf-8'))
    if not isinstance(source, list):
        raise ValueError('data/verified_titles.json must contain a JSON array')
    today = dt.datetime.now(dt.timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('Europe/Warsaw')).date()
    movies = []
    seen = set()
    for row in source:
        valid = validate(row, today)
        if valid is None:
            continue
        key = (str(valid.get('tmdbId', '')), valid['title'].lower())
        if key in seen:
            continue
        seen.add(key)
        movies.append(valid)
    movies.sort(key=lambda film: (film['vodAddedAt'], film['title']), reverse=True)
    feed = {'region': 'PL', 'generatedAt': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'), 'movies': movies}
    TARGET.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Published {len(movies)} verified film(s) from {len(source)} source record(s)')
    if source and not movies:
        print('No source records met freshness/evidence requirements; publishing an empty list.')


if __name__ == '__main__':
    try:
        build()
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
