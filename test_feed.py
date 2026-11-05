import importlib.util
import pathlib
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('feed', 'scripts/build_feed.py')
feed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feed)

class FeedTests(unittest.TestCase):
    def test_subscription_only(self):
        details = {'watch/providers': {'results': {'PL': {
            'rent': [{'provider_name': 'Apple TV Store'}],
            'flatrate': [{'provider_name': 'Netflix'}, {'provider_name': 'HBO Max'},
                         {'provider_name': 'Apple TV Store'}]}}}}
        self.assertEqual(feed.providers(details), ['Netflix', 'HBO Max'])

    def test_new_season_does_not_use_episode_date(self):
        today = feed.today_string()
        self.assertEqual(feed.newness({'first_air_date': '2000-01-01', 'last_air_date': today}, 'tv'), ('', ''))
        self.assertEqual(feed.newness({'first_air_date': '2000-01-01',
            'seasons': [{'season_number': 3, 'air_date': today}]}, 'tv'), (today, 'season_release_date'))

    def test_special_is_not_new_season(self):
        self.assertEqual(feed.newness({'first_air_date': '2000-01-01',
            'seasons': [{'season_number': 0, 'air_date': feed.today_string()}]}, 'tv'), ('', ''))

    def test_empty_feed_keeps_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'feed.json'
            path.write_text('previous')
            with patch.object(feed, 'OUTPUT', path), patch.object(feed, 'TOKEN', 'test'), patch.object(feed, 'collect', return_value=[]):
                with self.assertRaises(RuntimeError): feed.main()
            self.assertEqual(path.read_text(), 'previous')

    def test_collect_rating_and_duplicates(self):
        def request(path, params):
            if path.startswith('/watch/providers/'):
                return {'results': [{'provider_id': 8, 'provider_name': 'Netflix'}]}
            if path.startswith('/discover/'):
                return {'results': [{'id': 1}, {'id': 1}], 'total_pages': 1}
            return {'title': 'Film', 'release_date': feed.today_string(), 'poster_path': '/a.jpg',
                'vote_average': 7.5, 'vote_count': 123,
                'watch/providers': {'results': {'PL': {'flatrate': [{'provider_name': 'Netflix'}]}}}}
        with patch.object(feed, 'request', side_effect=request), patch.object(feed, 'trailer_key', return_value=''):
            result = feed.collect('movie')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['voteCount'], 123)
        self.assertFalse(result[0]['vodAdditionVerified'])
        self.assertIsNone(result[0]['vodAddedAt'])

if __name__ == '__main__': unittest.main()
