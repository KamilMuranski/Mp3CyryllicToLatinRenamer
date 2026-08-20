#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CyryllicToLatinRenamer - krok 3 pipeline'u porządkowania muzyki.

Rekurencyjnie przechodzi drzewo katalogów POD KATALOGIEM, W KTÓRYM LEŻY TEN PLIK,
i nadaje folderom oraz plikom zapisanym cyrylicą postać "Łacinka (Cyrylica)".
Sam katalog skryptu nigdy nie jest zmieniany.

Uruchomienie: dwuklik na pliku (albo `python "CyryllicToLatinRenamer.py"`).
Pełny opis zachowania: Dokumentacja.md.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# --- Wzorce nazw --------------------------------------------------------------

ALBUM_PATTERN = re.compile(r"^(\d{4})\s-\s(.+)$")
TRACK_PATTERN = re.compile(r"^(\d{2})\s-\s(.+)$")

# Rozpoznawane dopiski na końcu nazwy albumu (ta sama lista co w PrepareFoldersAndFilesNames)
ALBUM_SUFFIXES = ("Compilation", "Single", "Live", "Split", "2CD", "3CD", "4CD", "5CD")
TRAILING_SUFFIX_PATTERN = re.compile(
    r"^(?P<base>.*)\((?P<suffix>" + "|".join(ALBUM_SUFFIXES) + r")\)\s*$",
    re.IGNORECASE,
)

# Kształt "Łacinka (Cyrylica)" - ochrona przed powtórnym przetworzeniem nazwy
ALREADY_TRANSLATED_PATTERN = re.compile(r"^(?P<lat>.+?)\s\((?P<cyr>.+)\)$")

# Końcowy dopisek "(coś cover)" wewnątrz tytułu cyrylickiego
INNER_COVER_PATTERN = re.compile(
    r"^(?P<base>.*?)(\s*\((?P<inner_cover>[^()]*cover[^()]*)\))\s*$",
    re.IGNORECASE,
)

# Kształt "Lat (CoverLat) (Cyr (CoverCyr))" budowany przez build_cover_title dla
# coveru z wykonawcą zapisanym cyrylicą - ochrona przed powtórnym przetworzeniem
# (bez niej drugie uruchomienie rozdymywało nazwę w nieskończoność, patrz Dokumentacja.md)
COVER_ALREADY_TRANSLATED_PATTERN = re.compile(
    r"^(?P<lat>.+?)\s\((?P<cover_lat>[^()]*cover[^()]*)\)\s\((?P<cyr>.+?)\s\((?P<cover_cyr>[^()]*cover[^()]*)\)\)$",
    re.IGNORECASE,
)

# Tekst za ostatnim domykającym nawiasem najwyższego poziomu (np. "... (Ария cover) сложный"
# -> "сложный") - bez wychwycenia go osobno ginąłby bezpowrotnie przy budowaniu tytułu covera.
TRAILING_AFTER_PARENS_PATTERN = re.compile(r"\)(?P<after>[^()]*)$")

# Odpowiednik .NET-owego \p{IsCyrillic} (blok Cyrillic + Cyrillic Supplement)
CYRILLIC_PATTERN = re.compile(r"[Ѐ-ӿԀ-ԯ]")

SUPPORTED_EXTENSIONS = (".mp3", ".jpg", ".jpeg", ".png")

# --- Transliteracja ----------------------------------------------------------

CYRILLIC_MAP = {
    # wielkie
    "А": "A",
    "Б": "B",
    "В": "V",
    "Г": "G",
    "Д": "D",
    "Е": "E",
    "Ё": "Yo",
    "Ж": "Zh",
    "З": "Z",
    "И": "I",
    "Й": "I",
    "К": "K",
    "Л": "L",
    "М": "M",
    "Н": "N",
    "О": "O",
    "П": "P",
    "Р": "R",
    "С": "S",
    "Т": "T",
    "У": "U",
    "Ф": "F",
    "Х": "Kh",
    "Ц": "Ts",
    "Ч": "Ch",
    "Ш": "Sh",
    "Щ": "Shch",
    "Ъ": "",
    "Ы": "Y",
    "Ь": "’",
    "Э": "E",
    "Ю": "Yu",
    "Я": "Ya",
    # małe
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "i",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "’",
    "э": "e",
    "ю": "yu",
    "я": "ya",
    # ukraińskie
    "І": "I",
    "Ї": "Yi",
    "Є": "Ye",
    "Ґ": "G",
    "і": "i",
    "ї": "yi",
    "є": "ye",
    "ґ": "g",
    # białoruskie
    "Ў": "U",
    "ў": "u",
}


def transliterate_cyrillic(text: str) -> str:
    """Prosta transliteracja cyrylica -> łacinka, znak po znaku."""
    if not text:
        return text
    return "".join(CYRILLIC_MAP.get(ch, ch) for ch in text)


def has_cyrillic(text: str) -> bool:
    """Czy ciąg zawiera jakikolwiek znak cyrylicy."""
    return bool(text) and CYRILLIC_PATTERN.search(text) is not None


# --- Budowanie nazw ----------------------------------------------------------


def extract_trailing_suffix(title: str) -> tuple[str | None, str]:
    """
    Wykrywa i usuwa jeden końcowy dopisek "(Live)"/"(Compilation)"/"(2CD)"...

    Zwraca (kanoniczną nazwę dopisku albo None, tytuł bez dopisku). Dopisek musi
    być odcięty PRZED transliteracją, żeby nie trafił do części cyrylickiej.
    """
    m = TRAILING_SUFFIX_PATTERN.match(title)
    if not m:
        return None, title

    matched = m.group("suffix")
    suffix = next(s for s in ALBUM_SUFFIXES if s.lower() == matched.lower())
    return suffix, m.group("base").rstrip()


def is_already_translated(title: str) -> bool:
    """
    Sprawdza, czy tytuł ma już postać "Lat (Cyr)", gdzie część łacińska jest
    dokładnie transliteracją części cyrylickiej - wtedy nie ma czego zmieniać.
    """
    m = ALREADY_TRANSLATED_PATTERN.match(title)
    if not m:
        return False

    lat = m.group("lat")
    cyr = m.group("cyr")

    return not has_cyrillic(lat) and has_cyrillic(cyr) and transliterate_cyrillic(cyr) == lat


def build_translated_title(title: str) -> str:
    """
    Buduje "TytułŁacinką (TytułCyrylicą)" dla dowolnego tytułu (zespół, album,
    utwór, plik). Nie rusza tytułów bez cyrylicy ani takich, które są już w tym
    formacie (bezpieczne dla wielokrotnego uruchomienia).
    """
    if not has_cyrillic(title):
        return title

    if is_already_translated(title):
        return title

    lat = transliterate_cyrillic(title)
    if lat == title:
        return title

    return f"{lat} ({title})"


def extract_top_level_parentheses(text: str) -> tuple[list[str], str]:
    """
    Wyciąga zawartość nawiasów najwyższego poziomu oraz tekst przed pierwszym
    nawiasem. Np. "A (B) (C(D))" -> (["B", "C(D)"], "A").
    """
    result: list[str] = []
    outside: list[str] = []
    current: list[str] = []
    depth = 0
    before = ""

    for ch in text:
        if ch == "(":
            if depth == 0:
                before = "".join(outside).rstrip()
                current.clear()
            depth += 1
            if depth == 1:
                continue  # nie dodajemy '(' do zawartości
        elif ch == ")":
            if depth == 1:
                result.append("".join(current).strip())
                depth -= 1
                current.clear()
                continue  # nie dodajemy ')'
            if depth > 1:
                depth -= 1
                continue

        if depth == 0:
            outside.append(ch)
        else:
            current.append(ch)

    if not before:
        before = "".join(outside).rstrip()

    return result, before


def is_already_translated_cover_title(title: str) -> bool:
    """
    Sprawdza, czy tytuł ma już postać "Lat (CoverLat) (Cyr (CoverCyr))" zbudowaną
    przez build_cover_title dla coveru z wykonawcą zapisanym cyrylicą - wtedy nie
    ma czego zmieniać. Bez tej ochrony powtórne uruchomienie rozdymywało taką nazwę
    w nieskończoność (zagnieżdżone nawiasy gubią się w extract_top_level_parentheses,
    więc ogólna is_already_translated tego kształtu nie rozpoznaje).
    """
    m = COVER_ALREADY_TRANSLATED_PATTERN.match(title)
    if not m:
        return False

    lat = m.group("lat")
    cover_lat = m.group("cover_lat")
    cyr = m.group("cyr")
    cover_cyr = m.group("cover_cyr")

    return (
        not has_cyrillic(lat)
        and not has_cyrillic(cover_lat)
        and has_cyrillic(cyr)
        and has_cyrillic(cover_cyr)
        and transliterate_cyrillic(cyr) == lat
        and transliterate_cyrillic(cover_cyr) == cover_lat
    )


def build_cover_title(track_number: str, raw_title: str) -> str | None:
    """
    Specjalne budowanie tytułów z "cover".
    Zwraca nową nazwę bez rozszerzenia albo None, jeśli nie rozpoznano wzorca.
    """
    if not raw_title or not raw_title.strip():
        return None

    if "cover" not in raw_title.lower():
        return None

    if is_already_translated_cover_title(raw_title):
        return f"{track_number} - {raw_title}"

    # Tekst za ostatnim domykającym nawiasem najwyższego poziomu - inaczej ginie
    # bezpowrotnie, np. "Песня (Ария cover) сложный" -> "сложный" nigdzie by nie trafiło
    trailing_match = TRAILING_AFTER_PARENS_PATTERN.search(raw_title)
    trailing_text = trailing_match.group("after").strip() if trailing_match else ""

    # Rozbij tytuł na część przed nawiasami i nawiasy najwyższego poziomu
    groups, before = extract_top_level_parentheses(raw_title)
    if not groups:
        return None

    # Znajdź tekst covera - pierwszy nawias zawierający "cover"
    cover_text = next((g for g in groups if "cover" in g.lower()), None)

    # Znajdź tytuł cyrylicą: albo część przed nawiasami, albo któryś nawias
    if has_cyrillic(before):
        cyr_title_raw: str | None = before.strip()
    else:
        cyr_title_raw = next((g for g in groups if has_cyrillic(g)), None)

    if cyr_title_raw is None or cover_text is None:
        return None

    # Jeśli tytuł cyrylicą sam ma na końcu "(coś cover)" - odetnij to z tytułu
    cyr_title_base = cyr_title_raw
    inner = INNER_COVER_PATTERN.match(cyr_title_base)
    if inner:
        cyr_title_base = inner.group("base").rstrip()
        inner_cover = inner.group("inner_cover").strip()

        # jeśli z zewnątrz nie mieliśmy cover_text, użyj tego z wnętrza
        if not cover_text:
            cover_text = inner_cover

    if trailing_text:
        cyr_title_base = f"{cyr_title_base} {trailing_text}".strip()

    title_lat = transliterate_cyrillic(cyr_title_base)

    # jeśli transliteracja nic nie zmienia - nie ma sensu tu nic kombinować
    if title_lat == cyr_title_base:
        return None

    if not has_cyrillic(cover_text):
        # NN - TytułŁacinką (TytułCyrylicą) (Nazwa cover)
        return f"{track_number} - {title_lat} ({cyr_title_base}) ({cover_text})"

    cover_lat = transliterate_cyrillic(cover_text)
    # NN - TytułŁacinką (ZespółŁacinką cover) (TytułCyrylicą (ZespółCyrylicą cover))
    return f"{track_number} - {title_lat} ({cover_lat}) ({cyr_title_base} ({cover_text}))"


# --- Przechodzenie drzewa katalogów -------------------------------------------


def rename_directory_if_needed(path: Path) -> Path:
    """
    Zmienia nazwę pojedynczego katalogu (zespół, album...) na podstawie samej
    jego nazwy. Foldery "YYYY - Tytuł" dostają specjalną obsługę roku i końcowego
    dopisku (Live/Compilation/Split); pozostałe (np. nazwa zespołu) są tłumaczone
    wprost. Zwraca ścieżkę po zmianie (albo oryginalną, jeśli nic nie zmieniono).
    """
    name = path.name

    m = ALBUM_PATTERN.match(name)
    if m:
        year = m.group(1)
        base_title = m.group(2)

        suffix, base_title = extract_trailing_suffix(base_title)
        final_title = build_translated_title(base_title)

        new_name = f"{year} - {final_title} ({suffix})" if suffix else f"{year} - {final_title}"
    else:
        new_name = build_translated_title(name)

    if new_name == name:
        return path

    new_path = path.parent / new_name
    try:
        os.rename(path, new_path)
    except OSError as ex:
        print(f"Błąd zmiany nazwy folderu '{path}' -> '{new_path}': {ex}", file=sys.stderr)
        return path  # kontynuuj z oryginalną ścieżką

    print(f"[DIR] {name} -> {new_name}")
    return new_path


def is_supported_file(path: Path) -> bool:
    return os.path.splitext(path.name)[1].lower() in SUPPORTED_EXTENSIONS


def rename_files_in_directory(directory: Path) -> None:
    """Zmienia nazwy plików mp3/jpg/jpeg/png w JEDNYM katalogu (bez rekurencji)."""
    try:
        files = sorted(
            (p for p in directory.iterdir() if p.is_file() and is_supported_file(p)),
            key=lambda p: p.name,
        )
    except OSError as ex:
        print(f"Błąd listowania plików w '{directory}': {ex}", file=sys.stderr)
        return

    for path in files:
        file_name = path.name
        name_no_ext, ext = os.path.splitext(file_name)

        t = TRACK_PATTERN.match(name_no_ext)
        if t:  # NN - Tytuł
            nn = t.group(1)
            raw_title = t.group(2)

            # Najpierw spróbuj specjalnej logiki dla "cover"
            special = build_cover_title(nn, raw_title)
            new_name_no_ext = special if special is not None else f"{nn} - {build_translated_title(raw_title)}"
        else:  # okładki/obrazy i inne pliki
            new_name_no_ext = build_translated_title(name_no_ext)

        new_file_name = new_name_no_ext + ext
        new_path = directory / new_file_name
        if str(path) == str(new_path):
            continue

        try:
            os.rename(path, new_path)
        except OSError as ex:
            print(f"Błąd zmiany nazwy pliku '{path}' -> '{new_path}': {ex}", file=sys.stderr)
            continue

        print(f"[FILE] {file_name} -> {new_file_name}")


def process_directory(directory: Path, is_root: bool) -> None:
    """
    Przechodzi drzewo "z góry na dół": najpierw zmienia nazwę bieżącego katalogu,
    dopiero potem wchodzi do podkatalogów (żeby ścieżki dzieci odpowiadały już
    zmienionej nazwie rodzica), a na końcu zmienia nazwy plików w tym katalogu.
    """
    current = directory if is_root else rename_directory_if_needed(directory)

    try:
        sub_dirs = sorted((p for p in current.iterdir() if p.is_dir()), key=lambda p: p.name)
    except OSError as ex:
        print(f"Błąd listowania katalogów w '{current}': {ex}", file=sys.stderr)
        return

    for sub in sub_dirs:
        process_directory(sub, is_root=False)

    rename_files_in_directory(current)


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
    Trzyma okno konsoli otwarte po dwukliku. Przy uruchomieniu z potoku albo ze
    skryptu (brak wejścia) kończy od razu - input() zgłasza wtedy EOFError.
    """
    try:
        input("Gotowe. Naciśnij Enter, aby zamknąć okno...")
    except (EOFError, KeyboardInterrupt):
        print()


def main() -> int:
    setup_console()

    # Skrypt stoi NA GÓRZE struktury - przetwarzamy katalog, w którym leży plik .py
    root = Path(__file__).resolve().parent

    try:
        process_directory(root, is_root=True)
    except Exception as ex:  # noqa: BLE001 - świadomy catch-all, jak w wersji C#
        print(f"Błąd ogólny: {ex}", file=sys.stderr)

    wait_for_key()
    return 0


if __name__ == "__main__":
    sys.exit(main())
