# CyryllicToLatinRenamer - dokumentacja produktu

Ten plik opisuje aktualne zachowanie aplikacji z perspektywy użytkownika. Krótka
specyfikacja techniczna dla agentów jest w `AGENTS.md`.

## Zakres aplikacji

CyryllicToLatinRenamer to konsolowe narzędzie, które rekurencyjnie przechodzi przez
strukturę folderów z muzyką i nadaje folderom oraz plikom zapisanym cyrylicą postać
`Łacinka (Cyrylica)` — czyli transliterowaną nazwę łacinką, a obok, w nawiasie, oryginał
zapisany cyrylicą (do wglądu/wyszukiwania). Program działa na katalogu, w którym leży
uruchomiony plik programu, i rekurencyjnie przetwarza jego podfoldery. Sam ten katalog nigdy
nie jest zmieniany.

## Pozycja w pipeline

To krok 3 z 4 w typowym przebiegu porządkowania pobranej muzyki:

1. `MusicRenamer` - ujednolica prefiks numeru ścieżki w nazwach plików `.mp3`.
2. `PrepareFoldersAndFilesNames` - poprawia wielkość liter w nazwach folderów/plików,
   usuwa `(bonus track)`, nadaje nazwę okładce.
3. **CyryllicToLatinRenamer** (ten program) - tłumaczy nazwy zapisane cyrylicą.
4. `Mp3TagsSetter` - wpisuje tagi ID3 na podstawie nazw folderów i plików.

Krok 3 jest sensowny tylko wtedy, gdy w kolekcji faktycznie jest coś zapisane cyrylicą —
dla folderów/plików bez cyrylicy program niczego nie zmienia. Można go pominąć bez wpływu
na resztę kolekcji.

## Oczekiwana struktura folderów

```
<folder z programem>/
  Gatunek/                          np. "Folk metal" — zwykle bez cyrylicy, zostaje bez zmian
    Zespół (cyrylica)/              zostaje przetłumaczony na "ZespółŁac (ZespółCyr)"
      YYYY - Tytuł albumu/          zostaje przetłumaczony wg zasad opisanych niżej
        NN - Tytuł utworu.mp3
        Okładka.jpg
```

Program obsługuje dowolną głębokość zagnieżdżenia i przetwarza katalogi **od góry do
dołu** — najpierw zmienia nazwę folderu nadrzędnego, dopiero potem wchodzi do środka.

## Reguły zmiany nazw

### Foldery zespołu i inne foldery bez wzorca roku

Dowolny folder, którego nazwa nie pasuje do wzorca albumu (`YYYY - Tytuł`), jest
tłumaczony wprost: `NazwaŁac (NazwaCyr)`. Jeśli nazwa nie zawiera znaków cyrylicy (np.
nazwa gatunku „Folk metal”), pozostaje bez zmian.

### Foldery albumów: `YYYY - Tytuł`

Tytuł jest tłumaczony jak wyżej (`TytułŁac (TytułCyr)`). Dodatkowo, jeśli na samym końcu
tytułu występuje jeden z rozpoznawanych dopisków:

`(Compilation)`, `(Single)`, `(Live)`, `(Split)`, `(2CD)`, `(3CD)`, `(4CD)`, `(5CD)`

(bez rozróżniania wielkości liter — ta sama lista, co w `PrepareFoldersAndFilesNames`),
to dopisek jest wycinany przed transliteracją i doklejany dokładnie raz, na samym końcu
nowej nazwy:

```
2003 - Ведовством Фрагментов (Compilation)
  ->
2003 - Vedovstvom Fragmentov (Ведовством Фрагментов) (Compilation)
```

Bez tego wycięcia dopisek trafiał do części cyrylickiej w nawiasie i był doklejany drugi
raz osobno, dając np. `... (Compilation) (Ведовством Фрагментов (Compilation))`.

### Pliki utworów: `NN - Tytuł.mp3`

Tytuł tłumaczony jak w folderach: `NN - TytułŁac (TytułCyr).mp3`.

Wyjątek: jeśli tytuł zawiera słowo „cover” w nawiasie, uruchamiana jest specjalna logika
budująca nazwę w stylu `NN - TytułŁac (Zespół cover) (TytułCyr (ZespółCyr cover))`. Tekst
stojący za nawiasem z coverem (np. „сложный” w `Песня (Ария cover) сложный`) jest doklejany
do tytułu przed transliteracją, żeby nie zginął.

### Pozostałe pliki (okładki: jpg/png/jpeg)

Cała nazwa (bez rozszerzenia) traktowana jest jak tytuł i tłumaczona:
`NazwaŁac (NazwaCyr).jpg`.

## Bezpieczeństwo wielokrotnego uruchomienia

Program rozpoznaje, że nazwa jest już przetłumaczona (ma postać `Lat (Cyr)`, gdzie `Lat`
nie zawiera cyrylicy, a transliteracja `Cyr` dokładnie odtwarza `Lat`) i wtedy niczego nie
zmienia. Ponowne uruchomienie na już przetworzonym folderze jest bezpieczne i nie tworzy
zagnieżdżonych, zdublowanych nazw.

Ta ochrona działa tylko dla nazw utworzonych przez aktualną wersję programu. Nazwy
uszkodzone przez starą, wadliwą wersję (podwójne dopiski typu
`... (Compilation) (Cyrylica (Compilation))`) nie zostaną automatycznie naprawione —
wymaga to osobnej, jednorazowej poprawki ręcznej.

**Utwory z coverem zespołu zapisanego cyrylicą** (`01 - Стенка (Кузьма cover).mp3`) mają
osobną ochronę (`is_already_translated_cover_title`) rozpoznającą kształt
`Lat (CoverLat) (Cyr (CoverCyr))`, bo ogólna reguła wyżej nie widzi tego przypadku
(zagnieżdżone nawiasy). Bez tej osobnej ochrony każde kolejne uruchomienie rozdymywało nazwę
w nieskończoność, aż Windows odrzucał zbyt długą nazwę — dotyczyło to tylko covera z
wykonawcą cyrylicą; cover pisany łacinką (`(Gorky Park cover)`) nigdy tego problemu nie miał.

## Transliteracja

Prosta transliteracja znak-po-znaku — mapa obejmuje cyrylicę rosyjską, ukraińską
(`І, Ї, Є, Ґ`) i białoruską (`Ў`). Znaki spoza mapy (litery łacińskie, cyfry, spacje,
nawiasy) przechodzą bez zmian, więc wielkość liter w wyniku zależy od wielkości liter w
oryginale cyrylickim (program nie poprawia kapitalizacji — tym zajmuje się krok 2,
`PrepareFoldersAndFilesNames`).

Mapa celuje w popularną ("dziennikarską") transliterację używaną m.in. przez metal-archives
i Wikipedię, nie w transliterację naukową/urzędową (ISO 9, GOST, BGN/PCGN) — stąd konkretne
wybory: `ь`/`ъ` → nic (pomijane, nie apostrof), `ё` → `e` (nie `yo`), `й` → `y` (nie `i`, np.
`Толстой` → `Tolstoy`). Te wybory są celowe: mają dawać wynik zgodny z tym, jak zespoły i
bazy danych po angielsku zapisują rosyjskie nazwy, żeby transliterowana nazwa była
wyszukiwalna.

## Znane ograniczenia

- Lista rozpoznawanych dopisków albumu jest zaszyta na sztywno w kodzie. Jeśli
  `PrepareFoldersAndFilesNames` zacznie rozpoznawać nowy tag, trzeba dodać go też tutaj.
- Nazwy uszkodzone przez starą wersję programu (sprzed poprawki dopisków) nie są
  naprawiane automatycznie.
- Foldery/pliki przetłumaczone starszą wersją mapy transliteracji (np. z apostrofem za
  `ь` albo `i` za `й`) nie zostaną rozpoznane jako już przetłumaczone - program spróbuje
  je przetłumaczyć ponownie, dublując nazwę. Wymaga to jednorazowej ręcznej poprawki nazw
  w już przetworzonej kolekcji.
- Tag ID3 nadawany później przez `Mp3TagsSetter` bierze nazwę folderu/pliku wprost - jeśli
  ten program przetłumaczył folder zespołu na `Zespół (Кириллица)`, dokładnie taki tekst
  trafi do pola Artist/AlbumArtist (podobnie Album weźmie tytuł łącznie z nawiasem
  cyrylickim). To świadomy kompromis, nie błąd tego programu.

## Uruchomienie

Program jest jednym plikiem `CyryllicToLatinRenamer.py`. Skopiuj go do folderu, od którego ma
zacząć (np. do katalogu z gatunkami albo do jednego gatunku) i kliknij dwukrotnie — Windows
uruchomi go zarejestrowanym `py.exe` i przetworzy drzewo. Jeśli nie wystąpił żaden błąd, okno
zamyka się sam po zakończeniu; jeśli któraś operacja się nie powiodła (błąd widoczny na
konsoli), okno zostaje otwarte i czeka na dowolny klawisz, żeby było czas na przeczytanie
komunikatu. Nie ma żadnego kroku budowania i nie trzeba nic instalować poza Pythonem (3.9+).

Katalogiem roboczym jest **folder, w którym leży plik `.py`**, a nie bieżąca ścieżka
terminala — nazwę pliku można dowolnie zmieniać (np. `3 - CyryllicToLatinRenamer.py`, żeby
trzymać kolejność kroków pipeline'u).

## Dokumentacja a specyfikacja agenta

Ten plik opisuje funkcje i zachowanie programu. Jeśli zmiana dotyczy technicznej mapy
kodu, reguł pracy agenta albo inwariantów implementacyjnych, aktualizuj `AGENTS.md`.
