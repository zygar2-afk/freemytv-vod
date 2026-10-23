import datetime as dt
import unittest
from build_tmdb_platform_series import build, normalize_provider
class Tests(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(normalize_provider("Max"),"HBO Max")
        self.assertEqual(normalize_provider("SkyShowtime"),"SkyShowtime")
        self.assertIsNone(normalize_provider("Disney Plus"))
    def test_only_polish_subscription_and_sort(self):
        def get(path,args=None):
            if path.startswith("/tv/") and path.endswith("/watch/providers"):
                id=int(path.split("/")[2])
                if id==1:return {"results":{"PL":{"flatrate":[{"provider_name":"Netflix"}]}}}
                if id==2:return {"results":{"PL":{"flatrate":[{"provider_name":"SkyShowtime"}]}}}
                return {"results":{"US":{"flatrate":[{"provider_name":"Max"}]}}}
            return {"results":[{"id":1,"name":"A","first_air_date":"2025-02-02","popularity":2,"genre_ids":[18]},
                               {"id":2,"name":"B","first_air_date":"2026-01-01","popularity":5,"genre_ids":[35]},
                               {"id":3,"name":"C","first_air_date":"2024-01-01","popularity":99}]}
        d=build(dt.date(2026,10,23),get)
        self.assertEqual([x["title"] for x in d["series"]],["A","B"])
        self.assertEqual(d["series"][0]["providersPL"],["Netflix"])
        self.assertEqual(d["rankingMetric"],"TMDB popularity; not platform viewing figures")
if __name__=="__main__":unittest.main()
