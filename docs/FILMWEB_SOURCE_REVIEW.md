# Filmweb as a premiere cross-check (research checkpoint)

Checked 2026-10-23. This is a source assessment, NOT permission to crawl
Filmweb and NOT evidence that a listing entry premiered this week.

## Direct pages

- Films added to VOD: https://www.filmweb.pl/vod/new/films
- Series added to VOD: https://www.filmweb.pl/vod/new/serials
- VOD overview with daily popularity lists: https://www.filmweb.pl/vod
- Terms of use: https://www.filmweb.pl/regulations

NOTE: the correct films path is **/vod/new/films**. Do not use
the previously suggested **/vod/new/movies** as a verified endpoint.

## Important meanings

- "Recently added to VOD" DOES NOT mean released as a new production.
- Ranking by Filmweb user vote count measures historical voting, not the
  number of viewers in the last seven days.
- Source pages group titles by platforms and can repeat the same production.
- Some series listings refer to seasons, not necessarily a new series.

## Source restrictions

Filmweb's terms include restrictions on bots generating requests to their
servers. Do not implement automatic Filmweb scraping or an unofficial API
client in the GitHub Actions workflow without explicit authorization.
Filmweb may be used as a HUMAN reference for verification, with factual
observations recorded as evidence. Never label an unchecked listing score
as a Filmweb-verified rating.

## Proposed verification record (manually reviewed or licensed feed)

For each candidate: title, kind (movie/series), Filmweb URL/id,
VOD platform, date added to the Polish platform, date/type of premiere
(original production vs latest season / first streaming availability),
date checked, verifiable source URL, rating, vote count, and status.

Publish only records with sufficient evidence. If there are fewer than
ten verified new premieres, show fewer than ten rather than including
old catalog additions. Do not use production year alone as proof of a
first premiere on VOD or of a premiere in the past seven days.

## Status

The automated nowoscivod.pl experiment is incomplete (bounded film pages
and a single series page). Its last strict year filter produced zero
results. The publication gate deliberately prevents updating the remote
feed with empty outputs, although an older empty file is already live.
No production TCL changes are authorized by this checkpoint.
