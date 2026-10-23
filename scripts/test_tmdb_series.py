#!/usr/bin/env python3
import datetime as dt
import unittest
from build_tmdb_series import within, classify, providers_pl, build

TODAY = dt.date(2026,10,23)
class TestTMDBSeries(unittest.TestCase):
    def test_window_boundaries(self):
        self.assertTrue(within("2026-10-03", TODAY))
        self.assertFalse(within("2026-10-02", TODAY))
        self.assertFalse(within("2026-10-24", TODAY))
    def test_new_season_of_old_series(self):
        x={"seasons":[{"season_number":1,"air_date":"2018-01-01"},
                      {"season_number":3,"air_date":"2026-10-15"}]}
        self.assertEqual(classify(x,TODAY)["event"],"new_season_premiere")
        self.assertEqual(classify(x,TODAY)["seasonNumber"],3)
    def test_ignore_old_season_and_specials(self):
        self.assertIsNone(classify({"seasons":[{"season_number":0,"air_date":"2026-10-20"},
                                                  {"season_number":1,"air_date":"2022-01-01"}]},TODAY))
    def test_provider_region(self):
        self.assertEqual(providers_pl({"results":{"US":{"flatrate":[{"provider_name":"Netflix"}]}}})[0],[])
    def test_integration_with_mock_api(self):
        def mock(path,params=None):
            if path in ("/trending/tv/week","/tv/on_the_air"):
                return {"results":[{"id":2,"name":"New season","popularity":100},
                                   {"id":3,"name":"Old season","popularity":200}]}
            if path == "/tv/2":
                return {"name":"New season","seasons":[{"season_number":2,"air_date":"2026-10-10"}]}
            if path == "/tv/3":
                return {"name":"Old season","seasons":[{"season_number":2,"air_date":"2020-10-10"}]}
            if path == "/tv/2/watch/providers":
                return {"results":{"PL":{"flatrate":[{"provider_name":"Prime Video"}],"link":"https://example.com"}}}
            raise AssertionError(path)
        result=build(TODAY,mock)
        self.assertEqual(result["candidateCount"],1)
        self.assertEqual(result["series"][0]["season"],2)
        self.assertFalse(result["seasonSpecificPolishAvailabilityVerified"])
if __name__=="__main__":
    unittest.main()
