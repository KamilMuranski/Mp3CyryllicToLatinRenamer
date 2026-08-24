# CyryllicToLatinRenamer - specyfikacja techniczna dla agenta

Ten plik jest krótkim startem dla agenta. Pełny opis działania aplikacji z perspektywy
użytkownika jest w `Dokumentacja.md`. Czytaj go, gdy zadanie dotyczy zachowania programu,
reguł nazewnictwa albo trzeba zweryfikować format nazw wejściowych/wyjściowych.

## Najważniejsze zasady pracy

- Pracuj wyłącznie na obecnym kodzie. Nie rób commitów i nie przełączaj brancha.
- Jeżeli prompt nie pasuje do projektu CyryllicToLatinRenamer, powiedz o tym przed dalszą pracą.
- Zmieniaj tylko pliki konieczne do zadania. Preferuj małe, lokalne zmiany.
- Kod i stringi aplikacji pisz po angielsku (poza polskimi komunikatami konsoli, które już
  tam są). Rozmowę prowadź po polsku.
- Nie dodawaj mechanizmów naprawy plików/folderów zepsutych przez starą wersję programu
  (podwójne dopiski typu `... (Compilation) (Cyrylica (Compilation))`) do
  `CyryllicToLatinRenamer.py`. Naprawa danych to osobne narzędzie:
  `CyryllicToLatinRenamerRevert.py` (patrz niżej).
- Program działa na realnych plikach pod katalogiem, w którym leży. Do testów manualnych
  używaj kopii danych, nigdy jedynej kopii kolekcji użytkownika.
- Nie twórz cache ani artefaktów testowych w tym folderze.

## Terminal i Windows

- System autora: Windows 11 64 bit.
- Nie uruchamiaj destrukcyjnych komend typu `git reset --hard`, `git clean`, kasowanie
  katalogów poza własnymi katalogami testowymi.

## Stack projektu

- Aplikacja konsolowa, jeden plik `CyryllicToLatinRenamer.py`, czysta biblioteka
  standardowa Pythona (3.9+). Zero zależności, zero budowania - uruchamiana dwuklikiem
  (Windows odpala ją zarejestrowanym `py.exe`).
- Obok leży niezależne narzędzie naprawcze `CyryllicToLatinRenamerRevert.py` (te same
  założenia: jeden plik, stdlib, dwuklik, katalog pliku `.py` jako korzeń). Nie importuje
  programu głównego i nie jest przez niego importowane - kopia potrzebnych wzorców jest
  świadoma, żeby oba pliki dały się kopiować pojedynczo.
- Katalogiem roboczym jest folder, w którym leży uruchomiony plik `.py`
  (`Path(__file__).resolve().parent`) - nie bieżący katalog terminala. Nazwę pliku można
  dowolnie zmieniać (np. dopisać prefiks numeru kroku pipeline'u).
- Do testów manualnych kopiuj `CyryllicToLatinRenamer.py` razem z danymi testowymi do
  osobnego katalogu i uruchamiaj stamtąd (`python CyryllicToLatinRenamer.py`).

## Pozycja w pipeline użytkownika

Ten program to krok 3 z 4 w pipeline porządkowania pobranej muzyki (patrz `Dokumentacja.md`
w tym repo po pełny opis pipeline'u). Krok ten jest **często pomijany** przez użytkownika,
gdy w kolekcji nie ma nic zapisanego cyrylicą. Krok 4 (`Mp3TagsSetter`) bierze nazwy
folderów/plików TAKIE, JAKIE SĄ po tym kroku i wpisuje je wprost do tagów ID3 (m.in. artysta
= nazwa folderu zespołu, album = nazwa folderu albumu bez roku i bez tagu na końcu) — jeśli
ten krok przetłumaczy folder zespołu na `Zespół (Кириллица)`, dokładnie taki string trafi do
tagu Artist/AlbumArtist. To nie jest tu naprawiane (nie było proszone) — jeśli użytkownik
zgłosi, że tagi ID3 zawierają cyrylicę w nawiasie, to świadomy kompromis tego programu, a
nie bug w nim samym.

## Mapa modułów

- `main` - ustawia UTF-8 konsoli, uruchamia `process_directory` od katalogu, w którym
  leży plik `.py`; wywołuje `wait_for_key` (czeka na dowolny klawisz) tylko, jeśli
  `report_error` ustawiło `_had_errors` - inaczej okno zamyka się od razu.
- `report_error` - jedyne miejsce wypisujące błędy na stderr; ustawia globalny
  `_had_errors`, na podstawie którego `main` decyduje, czy okno ma czekać na klawisz.
- `process_directory` - rekurencyjny przechód "od góry do dołu": najpierw zmienia nazwę
  bieżącego katalogu (`rename_directory_if_needed`), dopiero potem wchodzi do podkatalogów
  (żeby ścieżki dzieci odpowiadały już zmienionej nazwie rodzica), na końcu zmienia nazwy
  plików w tym katalogu (`rename_files_in_directory` - tylko bieżący katalog, podkatalogi
  obsłuży rekurencja).
- `rename_directory_if_needed` - dla folderów `YYYY - Tytuł` (dopasowanych do
  `ALBUM_PATTERN`) stosuje logikę roku + dopisku; dla pozostałych (np. folder zespołu,
  folder gatunku) tłumaczy całą nazwę wprost przez `build_translated_title`.
- `extract_trailing_suffix` - wycina jeden końcowy dopisek z `ALBUM_SUFFIXES` (patrz niżej)
  PRZED transliteracją tytułu albumu, żeby nie trafił do części cyrylickiej w nawiasie.
- `build_translated_title` / `is_already_translated` - budują `Łacinka (Cyrylica)` i chronią
  przed ponownym przetworzeniem już przetłumaczonej nazwy (patrz inwarianty niżej).
- `rename_files_in_directory` - pliki `.mp3`/`.jpg`/`.jpeg`/`.png` w jednym katalogu (nie
  rekurencyjnie). Dla `NN - Tytuł.mp3` najpierw próbuje `build_cover_title` (specjalny
  przypadek "cover"), inaczej `build_translated_title` na tytule. Dla pozostałych plików
  (okładki) tłumaczy całą nazwę bez rozszerzenia.
- `build_cover_title` / `extract_top_level_parentheses` - specjalna logika dla utworów z
  dopiskiem zawierającym słowo "cover" w nawiasie. `TRAILING_AFTER_PARENS_PATTERN` chwyta
  tekst za ostatnim domykającym nawiasem i dokleja go do tytułu przed transliteracją, żeby
  nie zginął (np. "сложный" w `Песня (Ария cover) сложный`).
- `is_already_translated_cover_title` - wywoływana na starcie `build_cover_title`, chroni
  przed powtórnym przetworzeniem coveru z wykonawcą cyrylicą (patrz inwarianty niżej).
- `transliterate_cyrillic` - transliteracja znak-po-znaku (dict `char -> string`), pokrywa
  cyrylicę rosyjską, ukraińską (`І, Ї, Є, Ґ`) i białoruską (`Ў`). Mapa celuje w popularną
  konwencję (metal-archives/Wikipedia), nie naukową: `ь`/`ъ` → `""`, `ё` → `e`, `й` → `y`
  (nie `i`, żeby np. `Толстой` dało `Tolstoy`, nie `Tolstoi`).

## Nieoczywiste inwarianty

- `ALBUM_SUFFIXES` (`Compilation, Single, Live, Split, 2CD, 3CD, 4CD, 5CD`) musi pozostawać
  zgodny z listą tagów w `PrepareFoldersAndFilesNames` (`folderNameKeepTagsRegex`, krok 2
  pipeline'u). Jeśli tam ktoś doda nowy tag, dodaj go też tutaj — inaczej wraca stary bug
  (dopisek trafia do części cyrylickiej i dubluje się na końcu nazwy).
- `extract_trailing_suffix` musi działać na tytule PRZED wywołaniem `transliterate_cyrillic`.
  Kolejność `strip suffix -> transliterate base -> doklej suffix na końcu` jest tu kluczowa.
- `is_already_translated` rozpoznaje kształt `Lat (Cyr)`, gdzie `Lat` nie ma cyrylicy, a
  transliteracja `Cyr` dokładnie odtwarza `Lat` — to jedyna ochrona przed powtórnym
  przetworzeniem przy ponownym uruchomieniu dla zwykłych nazw. Nie naprawia nazw już
  zepsutych przez starą wersję programu (zagnieżdżone/zdublowane dopiski) — te trzeba
  poprawić ręcznie.
- Rename katalogów idzie od najgłębszych rodziców do dzieci (`process_directory`
  rekurencyjnie renameuje rodzica, potem woła się na już zaktualizowanej ścieżce) —
  odwrotna kolejność unieważniłaby ścieżki dzieci.
- Każdy błąd zgłaszany do użytkownika musi iść przez `report_error`, nigdy przez gołe
  `print(..., file=sys.stderr)` — inaczej `main` nie ustawi `_had_errors` i okno zamknie
  się od razu, mimo że wystąpił błąd do przeczytania.
- Katalog główny (folder ze skryptem) nigdy nie jest zmieniany (`is_root=True` pomija
  rename).
- `build_cover_title` jest wywoływana tylko, gdy tytuł utworu zawiera słowo "cover" - w
  innym wypadku standardowa ścieżka `build_translated_title`.
- `is_already_translated_cover_title` rozpoznaje kształt `Lat (CoverLat) (Cyr (CoverCyr))`
  (cover z wykonawcą cyrylicą) - ogólna `is_already_translated` go nie widzi, bo
  `extract_top_level_parentheses` gubi domykający nawias przy zagnieżdżeniu. Bez tej
  osobnej ochrony powtórne uruchomienie rozdymywało nazwę w nieskończoność.

## Narzędzie naprawcze `CyryllicToLatinRenamerRevert.py`

Odwraca nazwy `Łacinka (Cyrylica)` do samego oryginału z nawiasu, żeby dało się puścić
aktualny program główny na kolekcji ponazywanej jego starszą wersją. Zachowanie od strony
użytkownika opisuje `Dokumentacja.md`.

- `revert_title` - serce narzędzia. Oryginałem jest OSTATNI nawias najwyższego poziomu
  zawierający cyrylicę; nawiasy za nim (dopisek albumu, dopisek covera) są doklejane z
  powrotem. Zwraca status `REVERTED` / `SKIP` / `UNMATCHED`.
- `split_top_level_parentheses` - odpowiednik `extract_top_level_parentheses` z programu
  głównego, ale BEZ jego buga: zachowuje domykający nawias zagnieżdżony i zwraca też tekst
  za ostatnim nawiasem. Nazwa z niezbalansowanymi nawiasami wraca bez grup (nie ruszamy jej).
- `latin_matches_cyrillic` + `TRANSLITERATION_VARIANTS` - jedyne zabezpieczenie przed
  skasowaniem sensownej nazwy: część łacińska musi być dopuszczalną transliteracją nawiasu.
  Mapa wariantów jest celowo szersza niż `CYRILLIC_MAP` programu głównego (apostrof za
  `ь`/`ъ`, `yo` za `ё`, `i` za `й`, `h` za `х`...), bo ma rozpoznawać też zapisy starszych
  wersji. Dopasowanie idzie zbiorem osiągalnych pozycji (jeden znak cyrylicy = różna liczba
  liter łacińskich), nie znak po znaku. Poszerzając mapę pamiętaj, że każdy nowy wariant
  podnosi ryzyko fałszywego trafienia - np. `01 - Song (Ария cover).mp3` MUSI zostać
  nietknięty.
- `UNMATCHED` idzie przez `report_warning` (osobny `_had_warnings`), nie `report_error` -
  to nie błąd, ale okno musi zostać otwarte, bo taka nazwa wymaga oka użytkownika.
- `rename_to` nigdy nie nadpisuje istniejącej nazwy (sprawdza `new_path.exists()` przed
  `os.rename`) - kolizja to `report_error` i pominięcie, nigdy utrata pliku.
- Przechód drzewa (`process_directory`, `is_root`, kolejność rodzic-przed-dziećmi) jest
  taki sam jak w programie głównym.

## Aktualizacja dokumentów

Aktualizuj dokumenty tylko w zakresie zmiany. Pisz o aktualnym stanie, bez historii typu
„wcześniej było X”.

- Zmiana zachowania programu, reguł nazewnictwa albo sposobu użycia: aktualizuj `Dokumentacja.md`.
- Nowa zasada pracy agenta, zmiana mapy kodu albo inwariantu technicznego:
  aktualizuj ten plik.
