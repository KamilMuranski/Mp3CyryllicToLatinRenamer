using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;

namespace CyryllicToLatinRenamer
{
    class Program
    {
        // Wzorce nazw
        static readonly Regex AlbumPattern = new Regex(@"^(\d{4})\s-\s(.+)$", RegexOptions.Compiled);
        static readonly Regex TrackPattern = new Regex(@"^(\d{2})\s-\s(.+)$", RegexOptions.Compiled);

        // Rozpoznawane dopiski na końcu nazwy albumu (ta sama lista co w PrepareFoldersAndFilesNames)
        static readonly string[] AlbumSuffixes = { "Compilation", "Single", "Live", "Split", "2CD", "3CD", "4CD", "5CD" };
        static readonly Regex TrailingSuffixPattern = new Regex(
            @"^(?<base>.*)\((?<suffix>Compilation|Single|Live|Split|2CD|3CD|4CD|5CD)\)\s*$",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        static void Main()
        {
            // Wymuś UTF-8 w konsoli
            Console.OutputEncoding = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
            Console.InputEncoding = Encoding.UTF8;

            // EXE stoi NA GÓRZE struktury (u Ciebie: ...\bin\Debug\net9.0)
            string root = AppDomain.CurrentDomain.BaseDirectory;

            try
            {
                // Przechodzimy drzewo katalogów od góry: gatunek -> zespół -> "YYYY - Tytuł" -> pliki.
                // Każdy poziom może wymagać transliteracji (zespół i album), więc zmieniamy nazwy
                // "z góry na dół", żeby ścieżki dzieci zawsze odpowiadały już zmienionym rodzicom.
                ProcessDirectory(root, isRoot: true);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"Błąd ogólny: {ex.Message}");
            }

            Console.WriteLine("Gotowe. Naciśnij klawisz...");
            Console.ReadKey();
        }

        static void ProcessDirectory(string dir, bool isRoot)
        {
            string currentDir = isRoot ? dir : RenameDirectoryIfNeeded(dir);

            string[] subDirs;
            try
            {
                subDirs = Directory.GetDirectories(currentDir);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"Błąd listowania katalogów w '{currentDir}': {ex.Message}");
                return;
            }

            foreach (var sub in subDirs)
                ProcessDirectory(sub, isRoot: false);

            RenameFilesInDirectory(currentDir);
        }

        /// <summary>
        /// Zmienia nazwę pojedynczego katalogu (zespół, album...) na podstawie samej jego nazwy.
        /// Foldery "YYYY - Tytuł" dostają specjalną obsługę roku i końcowego dopisku
        /// (Live/Compilation/Split); pozostałe (np. nazwa zespołu) są tłumaczone wprost.
        /// </summary>
        static string RenameDirectoryIfNeeded(string path)
        {
            string parent = Path.GetDirectoryName(path) ?? "";
            string name = Path.GetFileName(path);

            string newName;

            var m = AlbumPattern.Match(name);
            if (m.Success)
            {
                string year = m.Groups[1].Value;
                string baseTitle = m.Groups[2].Value;

                string? suffix = ExtractTrailingSuffix(ref baseTitle);
                string finalTitle = BuildTranslatedTitle(baseTitle);

                newName = suffix != null
                    ? $"{year} - {finalTitle} ({suffix})"
                    : $"{year} - {finalTitle}";
            }
            else
            {
                newName = BuildTranslatedTitle(name);
            }

            if (string.Equals(newName, name, StringComparison.Ordinal))
                return path;

            string newPath = Path.Combine(parent, newName);
            try
            {
                Directory.Move(path, newPath);
                Console.WriteLine($"[DIR] {name} -> {newName}");
                return newPath;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"Błąd zmiany nazwy folderu '{path}' -> '{newPath}': {ex.Message}");
                return path; // kontynuuj z oryginalną ścieżką
            }
        }

        /// <summary>
        /// Wykrywa i usuwa jeden końcowy dopisek "(Live)"/"(Compilation)"/"(Split)".
        /// Zwraca skanoniczną nazwę dopisku (albo null, jeśli go nie ma) i przycina
        /// przekazany tytuł tak, by dopisek nie trafił do części transliterowanej.
        /// </summary>
        static string? ExtractTrailingSuffix(ref string title)
        {
            var m = TrailingSuffixPattern.Match(title);
            if (!m.Success) return null;

            string suffix = AlbumSuffixes.First(s =>
                string.Equals(s, m.Groups["suffix"].Value, StringComparison.OrdinalIgnoreCase));

            title = m.Groups["base"].Value.TrimEnd();
            return suffix;
        }

        /// <summary>
        /// Buduje "TytułŁacinką (TytułCyrylicą)" dla dowolnego tytułu (zespół, album, utwór, plik).
        /// Nie rusza tytułów bez cyrylicy ani takich, które są już w tym formacie (bezpieczne
        /// dla wielokrotnego uruchomienia).
        /// </summary>
        static string BuildTranslatedTitle(string title)
        {
            if (!HasCyrillic(title))
                return title;

            if (IsAlreadyTranslated(title))
                return title;

            string lat = TransliterateCyrillic(title);
            if (string.Equals(lat, title, StringComparison.Ordinal))
                return title;

            return $"{lat} ({title})";
        }

        /// <summary>
        /// Sprawdza, czy tytuł ma już postać "Lat (Cyr)", gdzie część łacińska jest
        /// dokładnie transliteracją części cyrylickiej – wtedy nie ma czego zmieniać.
        /// </summary>
        static bool IsAlreadyTranslated(string title)
        {
            var m = Regex.Match(title, @"^(?<lat>.+?)\s\((?<cyr>.+)\)$");
            if (!m.Success) return false;

            string lat = m.Groups["lat"].Value;
            string cyr = m.Groups["cyr"].Value;

            return !HasCyrillic(lat) && HasCyrillic(cyr) &&
                   string.Equals(TransliterateCyrillic(cyr), lat, StringComparison.Ordinal);
        }

        static void RenameFilesInDirectory(string dir)
        {
            IEnumerable<string> files;
            try
            {
                files = Directory.GetFiles(dir, "*.*", SearchOption.TopDirectoryOnly)
                                 .Where(IsSupportedFile)
                                 .ToList();
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"Błąd listowania plików w '{dir}': {ex.Message}");
                return;
            }

            foreach (var path in files)
            {
                string fileName = Path.GetFileName(path);
                string nameNoExt = Path.GetFileNameWithoutExtension(fileName);
                string ext = Path.GetExtension(fileName);

                string newNameNoExt;

                var t = TrackPattern.Match(nameNoExt);
                if (t.Success)        // NN - Tytuł
                {
                    string nn = t.Groups[1].Value;
                    string rawTitle = t.Groups[2].Value;

                    // Najpierw spróbuj specjalnej logiki dla "cover"
                    string? special = BuildCoverTitle(nn, rawTitle);
                    newNameNoExt = special ?? $"{nn} - {BuildTranslatedTitle(rawTitle)}";
                }
                else                   // okładki/obrazy i inne pliki
                {
                    newNameNoExt = BuildTranslatedTitle(nameNoExt);
                }

                string newFileName = newNameNoExt + ext;
                string newPath = Path.Combine(dir, newFileName);
                if (!string.Equals(path, newPath, StringComparison.Ordinal))
                {
                    try
                    {
                        File.Move(path, newPath);
                        Console.WriteLine($"[FILE] {fileName} -> {newFileName}");
                    }
                    catch (Exception ex)
                    {
                        Console.Error.WriteLine($"Błąd zmiany nazwy pliku '{path}' -> '{newPath}': {ex.Message}");
                    }
                }
            }
        }

        static bool IsSupportedFile(string path)
        {
            string ext = Path.GetExtension(path).ToLowerInvariant();
            return ext == ".mp3" || ext == ".jpg" || ext == ".jpeg" || ext == ".png";
        }

        /// <summary>
        /// Czy ciąg zawiera jakikolwiek znak cyrylicy.
        /// </summary>
        static bool HasCyrillic(string input) =>
            !string.IsNullOrEmpty(input) && Regex.IsMatch(input, @"\p{IsCyrillic}");

        /// <summary>
        /// Wyciąga zawartość nawiasów najwyższego poziomu oraz tekst przed pierwszym nawiasem.
        /// Np. "A (B) (C(D))" → before="A", list: ["B", "C(D)"]
        /// </summary>
        static List<string> ExtractTopLevelParentheses(string input, out string beforeParentheses)
        {
            var result = new List<string>();
            var outside = new StringBuilder();
            var current = new StringBuilder();
            int depth = 0;
            beforeParentheses = string.Empty;

            foreach (char ch in input)
            {
                if (ch == '(')
                {
                    if (depth == 0)
                    {
                        beforeParentheses = outside.ToString().TrimEnd();
                        current.Clear();
                    }
                    depth++;
                    if (depth == 1)
                        continue; // nie dodajemy '(' do zawartości
                }
                else if (ch == ')')
                {
                    if (depth == 1)
                    {
                        result.Add(current.ToString().Trim());
                        depth--;
                        current.Clear();
                        continue; // nie dodajemy ')'
                    }
                    if (depth > 1)
                    {
                        depth--;
                        continue;
                    }
                }

                if (depth == 0)
                    outside.Append(ch);
                else
                    current.Append(ch);
            }

            if (string.IsNullOrEmpty(beforeParentheses))
                beforeParentheses = outside.ToString().TrimEnd();

            return result;
        }

        /// <summary>
        /// Specjalne budowanie tytułów z "cover".
        /// Zwraca nową nazwę bez rozszerzenia albo null, jeśli nie rozpoznano wzorca.
        /// </summary>
        static string? BuildCoverTitle(string trackNumber, string rawTitle)
        {
            if (string.IsNullOrWhiteSpace(rawTitle))
                return null;

            if (!rawTitle.Contains("cover", StringComparison.OrdinalIgnoreCase))
                return null;

            // Rozbij tytuł na część przed nawiasami i nawiasy najwyższego poziomu
            string before;
            var groups = ExtractTopLevelParentheses(rawTitle, out before);

            if (groups.Count == 0)
                return null;

            // Znajdź tekst covera – pierwszy nawias zawierający "cover"
            string? coverText = groups.FirstOrDefault(g =>
                g.IndexOf("cover", StringComparison.OrdinalIgnoreCase) >= 0);

            // Znajdź tytuł cyrylicą: albo część przed nawiasami, albo któryś nawias
            string? cyrTitleRaw = null;
            if (HasCyrillic(before))
                cyrTitleRaw = before.Trim();
            else
                cyrTitleRaw = groups.FirstOrDefault(HasCyrillic);

            if (cyrTitleRaw == null || coverText == null)
                return null;

            // Jeśli tytuł cyrylicą sam ma na końcu "(coś cover)" – odetnij to z tytułu
            string cyrTitleBase = cyrTitleRaw;
            var innerMatch = Regex.Match(
                cyrTitleBase,
                @"^(?<base>.*?)(\s*\((?<innerCover>[^()]*cover[^()]*)\))\s*$",
                RegexOptions.IgnoreCase);
            if (innerMatch.Success)
            {
                cyrTitleBase = innerMatch.Groups["base"].Value.TrimEnd();
                var innerCover = innerMatch.Groups["innerCover"].Value.Trim();

                // jeśli z zewnątrz nie mieliśmy coverText, użyj tego z wnętrza
                if (string.IsNullOrEmpty(coverText))
                    coverText = innerCover;
            }

            string titleLat = TransliterateCyrillic(cyrTitleBase);

            // jeśli transliteracja nic nie zmienia – nie ma sensu tu nic kombinować
            if (string.Equals(titleLat, cyrTitleBase, StringComparison.Ordinal))
                return null;

            bool coverHasCyr = HasCyrillic(coverText);

            if (!coverHasCyr)
            {
                // NN - TytułŁacinką (TytułCyrylicą) (Nazwa cover)
                return $"{trackNumber} - {titleLat} ({cyrTitleBase}) ({coverText})";
            }
            else
            {
                string coverLat = TransliterateCyrillic(coverText);
                // NN - TytułŁacinką (ZespółŁacinką cover) (TytułCyrylicą (ZespółCyrylicą cover))
                return $"{trackNumber} - {titleLat} ({coverLat}) ({cyrTitleBase} ({coverText}))";
            }
        }

        /// <summary>
        /// Prosta transliteracja cyrylica → łacinka.
        /// </summary>
        static string TransliterateCyrillic(string input)
        {
            if (string.IsNullOrEmpty(input)) return input;

            var map = new Dictionary<char, string>
            {
                // wielkie
                ['А'] = "A",
                ['Б'] = "B",
                ['В'] = "V",
                ['Г'] = "G",
                ['Д'] = "D",
                ['Е'] = "E",
                ['Ё'] = "Yo",
                ['Ж'] = "Zh",
                ['З'] = "Z",
                ['И'] = "I",
                ['Й'] = "I",
                ['К'] = "K",
                ['Л'] = "L",
                ['М'] = "M",
                ['Н'] = "N",
                ['О'] = "O",
                ['П'] = "P",
                ['Р'] = "R",
                ['С'] = "S",
                ['Т'] = "T",
                ['У'] = "U",
                ['Ф'] = "F",
                ['Х'] = "Kh",
                ['Ц'] = "Ts",
                ['Ч'] = "Ch",
                ['Ш'] = "Sh",
                ['Щ'] = "Shch",
                ['Ъ'] = "",
                ['Ы'] = "Y",
                ['Ь'] = "’",
                ['Э'] = "E",
                ['Ю'] = "Yu",
                ['Я'] = "Ya",
                // małe
                ['а'] = "a",
                ['б'] = "b",
                ['в'] = "v",
                ['г'] = "g",
                ['д'] = "d",
                ['е'] = "e",
                ['ё'] = "yo",
                ['ж'] = "zh",
                ['з'] = "z",
                ['и'] = "i",
                ['й'] = "i",
                ['к'] = "k",
                ['л'] = "l",
                ['м'] = "m",
                ['н'] = "n",
                ['о'] = "o",
                ['п'] = "p",
                ['р'] = "r",
                ['с'] = "s",
                ['т'] = "t",
                ['у'] = "u",
                ['ф'] = "f",
                ['х'] = "kh",
                ['ц'] = "ts",
                ['ч'] = "ch",
                ['ш'] = "sh",
                ['щ'] = "shch",
                ['ъ'] = "",
                ['ы'] = "y",
                ['ь'] = "’",
                ['э'] = "e",
                ['ю'] = "yu",
                ['я'] = "ya",
                // ukraińskie
                ['І'] = "I",
                ['Ї'] = "Yi",
                ['Є'] = "Ye",
                ['Ґ'] = "G",
                ['і'] = "i",
                ['ї'] = "yi",
                ['є'] = "ye",
                ['ґ'] = "g",
                // białoruskie
                ['Ў'] = "U",
                ['ў'] = "u"
            };

            var sb = new StringBuilder(input.Length * 2);
            foreach (var ch in input)
                sb.Append(map.TryGetValue(ch, out var latin) ? latin : ch);
            return sb.ToString();
        }
    }
}
