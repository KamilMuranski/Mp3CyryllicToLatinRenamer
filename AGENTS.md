# CyryllicToLatinRenamer

Konsolowa aplikacja .NET 9, która rekurencyjnie przechodzi przez strukturę folderów
z muzyką i zmienia nazwy folderów oraz plików zapisane cyrylicą tak, by miały postać
`Łacinka (Cyrylica)`. Uruchamiana bezpośrednio z folderu z EXE (np.
`bin\Debug\net9.0`), który traktowany jest jako korzeń przeszukiwania — sam nie jest
zmieniany.

## Oczekiwana struktura folderów

```
<folder z EXE>/
  Gatunek/                          np. "Folk metal" — nie jest zmieniany, jeśli nie ma cyrylicy
    Zespół (cyrylica)/              zostaje przetłumaczony na "ZespółŁac (ZespółCyr)"
      YYYY - Tytuł albumu/          zostaje przetłumaczony wg zasad opisanych niżej
        NN - Tytuł utworu.mp3
        Okładka.jpg
```

Program obsługuje dowolną głębokość zagnieżdżenia i przetwarza katalogi **od góry do
dołu** — najpierw zmienia nazwę folderu nadrzędnego, dopiero potem wchodzi do środka
(bo ścieżki dzieci muszą odpowiadać już zmienionej nazwie rodzica).

## Zasady zmiany nazw

### Foldery zespołu (i inne foldery bez wzorca roku)

Dowolny folder, którego nazwa nie pasuje do wzorca albumu (`YYYY - Tytuł`), jest
tłumaczony wprost: `NazwaŁac (NazwaCyr)`. Jeśli nazwa nie zawiera żadnych znaków
cyrylicy (np. nazwa gatunku „Folk metal”), pozostaje bez zmian.

### Foldery albumów: `YYYY - Tytuł`

Rozpoznawane wzorcem `^(\d{4})\s-\s(.+)$`. Tytuł jest tłumaczony jak wyżej
(`TytułŁac (TytułCyr)`), ale najpierw program sprawdza, czy na samym końcu tytułu
występuje jeden z trzech rozpoznawanych dopisków: `(Live)`, `(Compilation)`,
`(Split)` (bez rozróżniania wielkości liter). Jeśli tak — dopisek jest **wycinany
przed transliteracją** i doklejany dokładnie raz, na samym końcu nowej nazwy:

```
2003 - Ведовством Фрагментов (Compilation)
  ->
2003 - Vedovstvom Fragmentov (Ведовством Фрагментов) (Compilation)
```

Wcześniejszy błąd polegał na tym, że dopisek nie był wycinany przed transliteracją,
więc trafiał do części cyrylickiej w nawiasie i był doklejany drugi raz osobno,
dając np. `... (Compilation) (Ведовством Фрагментов (Compilation))`.

### Pliki utworów: `NN - Tytuł.mp3`

Rozpoznawane wzorcem `^(\d{2})\s-\s(.+)$`. Tytuł tłumaczony jak w folderach:
`NN - TytułŁac (TytułCyr).mp3`.

Wyjątek: jeśli tytuł zawiera słowo „cover” w nawiasie, uruchamiana jest specjalna
logika (`BuildCoverTitle`) budująca nazwę w stylu
`NN - TytułŁac (Zespół cover) (TytułCyr (ZespółCyr cover))`.

### Pozostałe pliki (okładki: jpg/png/jpeg)

Cała nazwa (bez rozszerzenia) traktowana jest jak tytuł i tłumaczona:
`NazwaŁac (NazwaCyr).jpg`.

## Bezpieczeństwo wielokrotnego uruchomienia (idempotencja)

Program rozpoznaje, że nazwa jest **już przetłumaczona** (ma postać `Lat (Cyr)`,
gdzie `Lat` nie zawiera cyrylicy, a transliteracja `Cyr` dokładnie odtwarza `Lat`) i
wtedy niczego nie zmienia. Dzięki temu ponowne uruchomienie na już przetworzonym
folderze jest bezpieczne i nie tworzy zagnieżdżonych, zdublowanych nazw.

Uwaga: ta ochrona działa tylko dla nazw utworzonych przez tę wersję programu.
Nazwy uszkodzone przez starą, wadliwą wersję (podwójne dopiski typu
`... (Compilation) (Cyrylica (Compilation))`) nie zostaną automatycznie naprawione
— wymagałoby to osobnej, jednorazowej logiki naprawczej.

## Transliteracja

Prosta transliteracja znak-po-znaku (`TransliterateCyrillic`) — słownik `char -> string`
obejmujący cyrylicę rosyjską, ukraińską (`І, Ї, Є, Ґ`) i białoruską (`Ў`). Znaki
spoza mapy (litery łacińskie, cyfry, spacje, nawiasy) przechodzą bez zmian.

## Znane ograniczenia / możliwe rozszerzenia na przyszłość

- Rozpoznawane dopiski albumów są zaszyte na sztywno w `AlbumSuffixes`
  (`Live`, `Compilation`, `Split`). Dodanie kolejnego wymaga edycji tej tablicy.
- Jeśli w bibliotece pojawią się już wcześniej uszkodzone nazwy (sprzed tej
  poprawki), trzeba je poprawić ręcznie albo napisać jednorazowy skrypt naprawczy
  — program celowo ich nie rusza, żeby nie zgadywać błędnie na krzywych danych.
