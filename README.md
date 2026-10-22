# Free My TV — Polish VOD verified catalog

This repository **publishes** an Android-compatible JSON feed on a daily GitHub Actions schedule.
It currently **does not automatically discover releases or fetch Filmweb scores**; unverified titles are intentionally excluded.

## Data policy

- `data/verified_titles.json` — manually supplied source records with direct evidence for date added to a Polish VOD platform and Filmweb rating/editorial distinction. Starts empty.
- `scripts/build_feed.py` — verifies essential fields, keeps films added on the latest 7 calendar dates (Poland), excludes unsupported ratings/editorial claims, de-duplicates, emits `vod_recommendations.json`.
- `.github/workflows/update-vod.yml` — runs each day at 07:17 UTC (09:17 Warsaw in summer, 08:17 in winter) and can also be started manually.
- `vod_recommendations.json` — **public output for TCL**, not the source of truth.

## Run

1. Upload all files, preserving folders, to `zygar2-afk/freemytv-vod` on its `main` branch.
2. Go to **Actions → Publish verified VOD catalog → Run workflow**. Confirm a green run.
3. Output URL: `https://raw.githubusercontent.com/zygar2-afk/freemytv-vod/main/vod_recommendations.json`.
4. **To connect the TV**: put exactly that URL (one line, no quotes) into the TV project's `app/assets/vod_feed_url.txt`, rebuild `FreeMyTV.apk`, push and install it. Files in an installed APK do not change when a GitHub repo is created.

### One example SOURCE record (illustrative ONLY — never publish as an actual movie)

```json
[
  {
    "kind": "movie",
    "title": "Verified film title",
    "tmdbId": 123,
    "vodAddedAt": "2026-10-21",
    "vodSource": "https://example.org/dated-polish-vod-premiere",
    "providers": [{"name": "Netflix", "access": "subscription"}],
    "filmweb": {
      "userRating": 7.8,
      "votes": 12500,
      "ratingSource": "https://www.filmweb.pl/film/example",
      "editorialRecommended": false,
      "editorialSource": null
    },
    "artworkUrl": "https://image.tmdb.org/t/p/w780/example.jpg"
  }
]
```

`editorialRecommended: true` requires an actual Filmweb editorial recommendation URL in `editorialSource`; a highly rated film alone is not such a recommendation. No unofficial Filmweb API, page scraping, or invented scoring is included. Manual records require evidence: **URL format validation is not proof that the content is accurate**. Do not paste example data into production.

### Maintenance

When the source list is empty, the published feed has `movies: []`, and the cinema card is hidden, without disturbing the launcher. GitHub scheduled workflows may be delayed or temporarily disabled in inactive public repositories; check the Actions tab periodically.

You may need to allow workflows via Settings → Actions → General, subject to account policies. GitHub workflow sets `permissions: contents: write` to allow committing the generated JSON. No personal token is needed.
