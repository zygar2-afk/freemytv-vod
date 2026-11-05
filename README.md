# FreeTV — katalog nowości VOD w Polsce

Repozytorium publikuje `vod_recommendations.json` dla launchera FreeTV VOD Preview. Generator automatycznie pobiera dane z TMDB, z polskimi opisami i dostępnością dla regionu PL.

## Zakres katalogu

Uwzględniane są abonamenty Netflix, HBO Max, Disney+, Prime Video, Apple TV+ i SkyShowtime. Wypożyczenia, zakup w sklepie i pozostałe platformy nie są zaliczane do tych sekcji.

Nowości obejmują ostatnie 30 dni kalendarzowych: premiery filmów i premiery sezonów seriali. Sam nowy odcinek starszego sezonu nie wystarcza. Tytuły są deduplikowane w obrębie kategorii i sortowane od najnowszej daty. Nie ma sekcji popularności.

TMDB nie udostępnia tutaj zweryfikowanej daty dodania tytułu do VOD. `vodAddedAt` pozostaje `null`, a `vodAdditionVerified` ma wartość `false`. Data premiery produkcji lub sezonu nie jest przedstawiana jako data dodania na platformę.

Oceny pochodzą z TMDB (`rating`, `voteCount`, `ratingSource`), nie z Filmweb. Aplikacja pokazuje ocenę z jedną cyfrą po przecinku przy co najmniej 10 głosach; w pozostałych przypadkach wyświetla „Brak ocen”.

## Aktualizacja i odporność na błędy

Workflow sprawdza slot 6:00 w strefie `Europe/Warsaw`. Dwa terminy UTC obejmują czas letni i zimowy, a kontrola lokalnej daty zapobiega podwójnej publikacji. GitHub Actions może opóźnić wykonanie; nie gwarantuje dokładnej minuty.

Generator używa istniejących sekretów Actions: `TMDB_API_KEY` lub `TMDB_READ_TOKEN`. Nie zapisuje kluczy w publicznym pliku JSON. Nieprawidłowy lub pusty wynik nie zastępuje ostatniego poprawnego katalogu.

Pull request uruchamia testy, generuje rzeczywisty katalog i waliduje daty, platformy, oceny oraz brak duplikatów. Wynik jest artefaktem `vod-preview`. Publikacja JSON działa wyłącznie na gałęzi `main`.

## Sprawdzenie lokalne

```sh
python -m unittest -v test_feed.py
```

Po ustawieniu własnej konfiguracji dostępu do TMDB można wygenerować i sprawdzić katalog:

```sh
python scripts/build_feed.py
python scripts/validate_feed.py
```

Wymagany jest Python 3.12 ze strefami czasowymi IANA. Dane filmowe i oceny: [TMDB](https://www.themoviedb.org/). Dane dostępności platform w TMDB są dostarczane przez JustWatch; aplikacja zawiera informację o źródłach w menu „O danych VOD”.
