import datetime as dt
import unittest
from build_tmdb_movies import build
class Tests(unittest.TestCase):
    def test_filters_polish_subscriptions_and_old_titles(self):
        def get(path,params=None):
            if path.startswith("/movie/") and path.endswith("/watch/providers"):
                return {"results":{"PL":{"flatrate":[{"provider_name":"Netflix"}]}}} if "/1/" in path else {"results":{"US":{"flatrate":[{"provider_name":"Netflix"}]}}}
            return {"results":[
                {"id":1,"title":"Film A","release_date":"2026-10-01","popularity":80},
                {"id":2,"title":"Film B","release_date":"2026-10-02","popularity":90}]}
        x=build(dt.date(2026,10,23),get)
        self.assertEqual(len(x["movies"]),1)
        self.assertEqual(x["movies"][0]["tmdbId"],1)
        self.assertEqual(x["movies"][0]["providersPL"],["Netflix"])
if __name__=="__main__": unittest.main()
