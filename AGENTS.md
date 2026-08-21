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
  (podwójne dopiski typu `... (Compilation) (Cyrylica (Compilation))`). To osobne zadanie
  naprawcze na danych, nie zmiana kodu.
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

## Aktualizacja dokumentów

Aktualizuj dokumenty tylko w zakresie zmiany. Pisz o aktualnym stanie, bez historii typu
„wcześniej było X”.

- Zmiana zachowania programu, reguł nazewnictwa albo sposobu użycia: aktualizuj `Dokumentacja.md`.
- Nowa zasada pracy agenta, zmiana mapy kodu albo inwariantu technicznego:
  aktualizuj ten plik.
