#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CyryllicToLatinRenamerRevert - narzędzie naprawcze do CyryllicToLatinRenamer.

Rekurencyjnie przechodzi drzewo katalogów POD KATALOGIEM, W KTÓRYM LEŻY TEN PLIK,
i przywraca folderom oraz plikom o nazwie "Łacinka (Cyrylica)" oryginalną nazwę
cyrylicą - tę z nawiasu. Sam katalog skryptu nigdy nie jest zmieniany.

Sens: po odwróceniu nazw można puścić aktualną wersję CyryllicToLatinRenamer.py i
dostać nazwy zgodne z jej regułami - także tam, gdzie stara wersja programu nazwała
pliki inaczej (inna mapa transliteracji, zdublowane dopiski typu
"(Compilation) (Cyrylica (Compilation))").

Uruchomienie: dwuklik na pliku (albo `python "CyryllicToLatinRenamerRevert.py"`).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# --- Wzorce nazw --------------------------------------------------------------

ALBUM_PATTERN = re.compile(r"^(\d{4})\s-\s(.+)$")
TRACK_PATTERN = re.compile(r"^(\d{2})\s-\s(.+)$")

# Odpowiednik \p{IsCyrillic} (blok Cyrillic + Cyrillic Supplement) - jak w programie głównym
CYRILLIC_PATTERN = re.compile(r"[Ѐ-ӿԀ-ԯ]")

SUPPORTED_EXTENSIONS = (".mp3", ".jpg", ".jpeg", ".png")

# Etykiety do komunikatow: (mianownik, dopelniacz, tag do logu)
DIR_KIND = ("folder", "folderu", "DIR")
FILE_KIND = ("plik", "pliku", "FILE")

# Wyniki analizy jednej nazwy
REVERTED = "reverted"    # rozpoznano "Łacinka (Cyrylica)" - zdejmujemy łacinkę
SKIP = "skip"            # nazwa nie wygląda na przetłumaczoną, nic do roboty
UNMATCHED = "unmatched"  # jest nawias z cyrylicą, ale łacinka do niego nie pasuje

_had_errors = False
_had_warnings = False


def report_error(message: str) -> None:
    """Wypisuje błąd na stderr i zapamiętuje, że wystąpił (patrz main())."""
    global _had_errors
    _had_errors = True
    print(message, file=sys.stderr)


def report_warning(message: str) -> None:
    """
    Zgłasza nazwę, której nie dało się bezpiecznie odwrócić. Też trzyma okno
    otwarte, bo taka nazwa wymaga oka użytkownika.
    """
    global _had_warnings
    _had_warnings = True
    print(message, file=sys.stderr)


# --- Dopuszczalne transliteracje ---------------------------------------------

# Klucze małymi literami (dopasowanie jest bez rozróżniania wielkości liter).
# Pierwszy wariant to zapis aktualnej wersji CyryllicToLatinRenamer, dalsze to
# zapisy spotykane w nazwach z jej starszych wersji i z ręcznego nazywania
# (apostrof za "ь"/"ъ", "yo" za "ё", "i" za "й", "h" za "х"...). Lista jest
# celowo szersza niż mapa programu głównego - inaczej nazwy zrobione starą
# wersją nie zostałyby rozpoznane jako "Łacinka (Cyrylica)".
TRANSLITERATION_VARIANTS = {
    "а": ("a",),
    "б": ("b",),
    "в": ("v", "w"),
    "г": ("g", "h"),
    "д": ("d",),
    "е": ("e", "ye", "je"),
    "ё": ("e", "yo", "jo", "ye", "o"),
    "ж": ("zh", "j"),
    "з": ("z",),
    "и": ("i", "y"),
    "й": ("y", "i", "j", ""),
    "к": ("k",),
    "л": ("l",),
    "м": ("m",),
    "н": ("n",),
    "о": ("o",),
    "п": ("p",),
    "р": ("r",),
    "с": ("s",),
    "т": ("t",),
    "у": ("u", "oo", "ou"),
    "ф": ("f",),
    "х": ("kh", "h", "ch", "x"),
    "ц": ("ts", "c", "tz"),
    "ч": ("ch", "tch"),
    "ш": ("sh", "sch"),
    "щ": ("shch", "sch", "shh", "sh"),
    "ъ": ("", "'", "’", '"'),
    "ы": ("y", "i", "ui"),
    "ь": ("", "'", "’", "j"),
    "э": ("e", "eh"),
    "ю": ("yu", "ju", "iu", "u"),
    "я": ("ya", "ja", "ia", "a"),
    # ukraińskie
    "і": ("i", "y"),
    "ї": ("yi", "i", "ji"),
    "є": ("ye", "e", "je"),
    "ґ": ("g", "h"),
    # białoruskie
    "ў": ("u", "w", "v"),
}


def has_cyrillic(text: str) -> bool:
    """Czy ciąg zawiera jakikolwiek znak cyrylicy."""
    return bool(text) and CYRILLIC_PATTERN.search(text) is not None


def latin_matches_cyrillic(cyrillic: str, latin: str) -> bool:
    """
    Czy `latin` jest jakąkolwiek dopuszczalną transliteracją `cyrillic`.

    To jedyne zabezpieczenie przed skasowaniem sensownej nazwy: bez niego nazwa
    typu "01 - Song (Ария cover)" (nigdy nie tłumaczona, cyrylica tylko w dopisku
    covera) zostałaby "odwrócona" do "01 - Ария cover".

    Znaki cyrylicy dopasowywane są przez TRANSLITERATION_VARIANTS (jeden znak
    może odpowiadać kilku zapisom łacinką, także pustemu - "ь", "ъ"), pozostałe
    znaki (spacje, cyfry, nawiasy, łacinka) muszą się zgadzać dokładnie.
    Dopasowanie idzie zbiorem osiągalnych pozycji w `latin` - jeden znak
    cyrylicy może dać różną liczbę liter łacińskich, więc zwykłe porównanie
    znak po znaku nie wystarcza.
    """
    if not cyrillic:
        return not latin

    latin_lower = latin.lower()
    reachable = {0}

    for ch in cyrillic:
        lower = ch.lower()
        variants = TRANSLITERATION_VARIANTS.get(lower)
        next_reachable: set[int] = set()

        for position in reachable:
            if variants is None:
                if latin_lower.startswith(lower, position):
                    next_reachable.add(position + len(lower))
            else:
                for variant in variants:
                    if latin_lower.startswith(variant, position):
                        next_reachable.add(position + len(variant))

        if not next_reachable:
            return False
        reachable = next_reachable

    return len(latin_lower) in reachable


# --- Analiza nazwy -----------------------------------------------------------


def split_top_level_parentheses(text: str) -> tuple[str, list[str], str]:
    """
    Rozbija nazwę na (tekst przed pierwszym nawiasem, zawartości nawiasów
    najwyższego poziomu, tekst za ostatnim domykającym nawiasem).

    "A (B) (C (D)) E" -> ("A", ["B", "C (D)"], "E")

    Zagnieżdżone nawiasy zostają w zawartości grupy w całości (razem z
    domykającym) - bez tego kształt "Lat (CoverLat) (Cyr (CoverCyr))" byłby
    nieczytelny. Nazwa z niezbalansowanymi nawiasami wraca bez grup, czyli
    nie zostanie tknięta.
    """
    before: list[str] = []
    groups: list[str] = []
    trailing: list[str] = []
    current: list[str] = []
    depth = 0

    for ch in text:
        if ch == "(":
            if depth == 0:
                depth = 1
                continue  # nie dodajemy nawiasu najwyższego poziomu
            depth += 1
        elif ch == ")":
            if depth == 1:
                groups.append("".join(current).strip())
                current = []
                trailing = []  # tekst za nawiasem liczymy od nowa
                depth = 0
                continue
            if depth > 1:
                depth -= 1

        if depth > 0:
            current.append(ch)
        elif groups:
            trailing.append(ch)
        else:
            before.append(ch)

    if depth != 0:
        return text, [], ""

    return "".join(before).strip(), groups, "".join(trailing).strip()


def revert_title(title: str) -> tuple[str, str]:
    """
    Zdejmuje z tytułu część łacińską, zostawiając oryginał cyrylicą z nawiasu.
    Zwraca (nowy tytuł, status: REVERTED / SKIP / UNMATCHED).

    Oryginałem jest OSTATNI nawias najwyższego poziomu zawierający cyrylicę -
    to, co przed nim, musi być jego transliteracją. Nawiasy stojące za nim
    (dopisek albumu "(Live)", "(Compilation)", dopisek covera "(Nazwa cover)")
    zostają doklejone z powrotem, bo należały do nazwy oryginalnej:

      Lat (Cyr)                          -> Cyr
      Lat (Cyr) (Live)                   -> Cyr (Live)
      Lat (Cyr) (Nazwa cover)            -> Cyr (Nazwa cover)
      Lat (CoverLat) (Cyr (CoverCyr))    -> Cyr (CoverCyr)
      Lat (Live) (Cyr (Live))            -> Cyr (Live)      (nazwa ze starej wersji)
    """
    before, groups, trailing = split_top_level_parentheses(title)

    if not groups:
        return title, SKIP

    # cyrylica przed nawiasami - nazwa jest już oryginalna
    if has_cyrillic(before):
        return title, SKIP

    index = next((i for i in reversed(range(len(groups))) if has_cyrillic(groups[i])), None)
    if index is None:
        return title, SKIP

    base = groups[index]

    # wszystko przed wybranym nawiasem musi być transliteracją jego zawartości
    prefix = before
    for group in groups[:index]:
        prefix = f"{prefix} ({group})".strip()

    if not latin_matches_cyrillic(base, prefix):
        return title, UNMATCHED

    new_title = base
    for group in groups[index + 1:]:
        new_title = f"{new_title} ({group})"
    if trailing:
        new_title = f"{new_title} {trailing}"

    new_title = new_title.strip()
    if not new_title or new_title == title:
        return title, SKIP

    return new_title, REVERTED


def revert_directory_name(name: str) -> tuple[str, str]:
    """Nowa nazwa folderu. Rok w folderach "YYYY - Tytuł" zostaje nietknięty."""
    m = ALBUM_PATTERN.match(name)
    if not m:
        return revert_title(name)

    new_title, status = revert_title(m.group(2))
    return f"{m.group(1)} - {new_title}", status


def revert_file_name(file_name: str) -> tuple[str, str]:
    """Nowa nazwa pliku. Numer utworu i rozszerzenie zostają nietknięte."""
    name_no_ext, ext = os.path.splitext(file_name)

    t = TRACK_PATTERN.match(name_no_ext)
    if t:
        new_title, status = revert_title(t.group(2))
        return f"{t.group(1)} - {new_title}{ext}", status

    new_name_no_ext, status = revert_title(name_no_ext)
    return f"{new_name_no_ext}{ext}", status


# --- Przechodzenie drzewa katalogów -------------------------------------------


def rename_to(path: Path, new_name: str, kind: tuple[str, str, str]) -> Path:
    """
    Zmienia nazwę pliku/folderu. Nigdy nie nadpisuje istniejącej nazwy - taki
    przypadek (np. w folderze leży już plik o nazwie oryginalnej) jest zgłaszany
    i pomijany. Zwraca ścieżkę po zmianie albo oryginalną, gdy się nie udało.
    """
    noun, genitive, tag = kind
    new_path = path.parent / new_name

    if new_path.exists():
        report_error(
            f"Pominięto {noun} '{path.name}' - nazwa '{new_name}' jest już zajęta w '{path.parent}'"
        )
        return path

    try:
        os.rename(path, new_path)
    except OSError as ex:
        # ex zawiera już obie ścieżki (src -> dst) - nie powtarzaj ich w treści komunikatu
        report_error(f"Błąd zmiany nazwy {genitive}: {ex}")
        return path

    print(f"[{tag}] {path.name} -> {new_name}")
    return new_path


def revert_directory_if_needed(path: Path) -> Path:
    """Odwraca nazwę pojedynczego katalogu (zespół, album...)."""
    new_name, status = revert_directory_name(path.name)

    if status == UNMATCHED:
        report_warning(f"Nie rozpoznano folderu '{path.name}' w '{path.parent}' - sprawdź ręcznie")
        return path

    if status != REVERTED:
        return path

    return rename_to(path, new_name, DIR_KIND)


def is_supported_file(path: Path) -> bool:
    return os.path.splitext(path.name)[1].lower() in SUPPORTED_EXTENSIONS


def revert_files_in_directory(directory: Path) -> None:
    """Odwraca nazwy plików mp3/jpg/jpeg/png w JEDNYM katalogu (bez rekurencji)."""
    try:
        files = sorted(
            (p for p in directory.iterdir() if p.is_file() and is_supported_file(p)),
            key=lambda p: p.name,
        )
    except OSError as ex:
        report_error(f"Błąd listowania plików w '{directory}': {ex}")
        return

    for path in files:
        new_name, status = revert_file_name(path.name)

        if status == UNMATCHED:
            report_warning(f"Nie rozpoznano pliku '{path.name}' w '{directory}' - sprawdź ręcznie")
            continue

        if status != REVERTED:
            continue

        rename_to(path, new_name, FILE_KIND)


def process_directory(directory: Path, is_root: bool) -> None:
    """
    Przechodzi drzewo "z góry na dół": najpierw zmienia nazwę bieżącego katalogu,
    dopiero potem wchodzi do podkatalogów (żeby ścieżki dzieci odpowiadały już
    zmienionej nazwie rodzica), a na końcu zmienia nazwy plików w tym katalogu.
    """
    current = directory if is_root else revert_directory_if_needed(directory)

    try:
        sub_dirs = sorted((p for p in current.iterdir() if p.is_dir()), key=lambda p: p.name)
    except OSError as ex:
        report_error(f"Błąd listowania katalogów w '{current}': {ex}")
        return

    for sub in sub_dirs:
        process_directory(sub, is_root=False)

    revert_files_in_directory(current)


# --- Konsola i wejście -------------------------------------------------------


def setup_console() -> None:
    """Wymusza UTF-8 na wyjściu, żeby cyrylica nie wysypała konsoli Windows."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def wait_for_key() -> None:
    """
    Trzyma okno konsoli otwarte po dwukliku, żeby użytkownik zobaczył komunikaty -
    wywoływana z main() tylko, gdy coś się nie udało albo czegoś nie rozpoznano.
    Przy uruchomieniu z potoku albo ze skryptu (brak interaktywnego wejścia)
    kończy od razu, żeby nie zawiesić automatyzacji.
    """
    print("Naciśnij dowolny klawisz, aby zamknąć okno...")

    if not sys.stdin.isatty():
        return

    if sys.platform == "win32":
        try:
            import msvcrt

            msvcrt.getch()
            return
        except OSError:
            pass

    try:
        input()
    except (EOFError, KeyboardInterrupt):
        print()


def main() -> int:
    setup_console()

    # Skrypt stoi NA GÓRZE struktury - przetwarzamy katalog, w którym leży plik .py
    root = Path(__file__).resolve().parent

    try:
        process_directory(root, is_root=True)
    except Exception as ex:  # noqa: BLE001 - świadomy catch-all, jak w programie głównym
        report_error(f"Błąd ogólny: {ex}")

    if _had_errors:
        print("Wystąpiły błędy (patrz powyżej).")
    if _had_warnings:
        print("Część nazw nie została rozpoznana i pozostała bez zmian (patrz powyżej).")

    if _had_errors or _had_warnings:
        wait_for_key()
    else:
        print("Gotowe, bez błędów.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
