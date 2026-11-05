"""Validate the generated public feed without API access or credentials."""
import datetime as dt
import json
import pathlib
from collections import Counter
from zoneinfo import ZoneInfo

data = json.loads(pathlib.Path('vod_recommendations.json').read_text(encoding='utf-8'))
today = dt.datetime.fromisoformat(data['generatedAt'].replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Warsaw')).date()
platforms = {'Netflix', 'HBO Max', 'Disney+', 'Prime Video', 'Apple TV+', 'SkyShowtime'}
counts = Counter()
ratings = 0
assert data['region'] == 'PL' and data['schemaVersion'] == 2
assert not data['popularMovies'] and not data['popularSeries']
for field, kind in [('newMovies', 'movie'), ('newSeries', 'tv')]:
    items = data[field]
    assert items, 'Empty category: ' + field
    dates = [item['newnessDate'] for item in items]
    assert dates == sorted(dates, reverse=True), 'Nonchronological category'
    assert len({item['tmdbId'] for item in items}) == len(items), 'Duplicate title'
    for item in items:
        assert item['kind'] == kind and item['availabilityRegion'] == 'PL'
        assert item['providers'] and set(item['providers']) <= platforms
        assert 0 <= (today - dt.date.fromisoformat(item['newnessDate'])).days <= 29
        assert item['newnessBasis'] in ('production_release_date', 'season_release_date')
        assert item['vodAddedAt'] is None and item['vodAdditionVerified'] is False
        assert item['ratingSource'] == 'TMDB' and isinstance(item['voteCount'], int)
        assert 0 <= item['rating'] <= 10 and item['voteCount'] >= 0
        if item['newnessBasis'] == 'season_release_date':
            assert kind == 'tv' and item['seasonReleaseDate'] == item['newnessDate']
        counts.update(item['providers'])
        ratings += item['voteCount'] >= 10 and item['rating'] > 0
print('VALIDATED movies=', len(data['newMovies']), 'series=', len(data['newSeries']), 'rated=', ratings)
print('PLATFORM_COUNTS', dict(sorted(counts.items())))
