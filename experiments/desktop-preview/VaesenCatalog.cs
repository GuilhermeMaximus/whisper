using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Whisper.Preview;

internal sealed class VaesenCatalog
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
    private readonly IReadOnlyList<Entry> entries;
    public IReadOnlyList<LocalBook> Books { get; }
    public IReadOnlyList<string> Categories { get; }

    public VaesenCatalog(string packPath)
    {
        using FileStream file = File.OpenRead(packPath);
        var pack = JsonSerializer.Deserialize<Pack>(file, JsonOptions);
        if (pack is null || pack.Version != 1 || pack.Books.Count == 0)
        {
            throw new InvalidDataException("O índice de Vaesen precisa ser importado novamente.");
        }
        Books = pack.Books;
        var translations = ReadTranslations(Path.ChangeExtension(packPath, null) + "-pt-br.json");
        var pagesByLocation = Books.SelectMany(book =>
        {
            var translation = translations?.GetValueOrDefault(book.Id);
            var pages = book.IsEnglish && book.Sha256 is not null && translation?.Sha256 == book.Sha256
                ? translation.Pages : null;
            return book.Pages.Select(page => new IndexedPage(book, page, pages?.GetValueOrDefault(page.Number)));
        }).ToDictionary(item => (item.Book.Id, item.Page.Number));
        var topics = ReadTopics("vaesen-topics.json").Concat(ReadTopics("vaesen-entries.json")).ToArray();
        if (topics.Select(topic => Normalize(topic.Title)).Distinct().Count() != topics.Length)
        {
            throw new InvalidDataException("O catálogo de Vaesen contém títulos repetidos.");
        }
        entries = topics.Select(topic =>
        {
            var sources = Enumerable.Range(topic.Page, (topic.ThroughPage ?? topic.Page) - topic.Page + 1)
                .Select(number => pagesByLocation.TryGetValue((topic.Book, number), out var source) ? source :
                    throw new InvalidDataException($"Página ausente no índice de Vaesen para {topic.Title}."))
                .ToArray();
            var original = TechnicalReference.Select(topic, sources.Select(source => source.Page.Text));
            var portuguese = sources[0].Book.IsEnglish && (topic.Category != "Arquétipos" || topic.Summary is null)
                ? TechnicalReference.Select(topic, sources.Select(source => source.Portuguese ?? "")) : [];
            return new Entry(topic, sources[0], original, portuguese);
        })
            .ToArray();
        Categories = entries.Select(item => item.Topic.BrowseCategory).Distinct().ToArray();
    }

    private static Dictionary<string, TranslationBook>? ReadTranslations(string path)
    {
        try
        {
            using FileStream file = File.Open(path, FileMode.Open, FileAccess.Read, FileShare.Read | FileShare.Delete);
            var pack = JsonSerializer.Deserialize<TranslationPack>(file, JsonOptions);
            return pack?.Version == 3 ? pack.Books : null;
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or JsonException)
        {
            return null;
        }
    }

    private static Topic[] ReadTopics(string name)
    {
        using FileStream topicFile = File.OpenRead(Path.Combine(AppContext.BaseDirectory, name));
        return JsonSerializer.Deserialize<Topic[]>(topicFile, JsonOptions) ?? [];
    }

    public Entry[] FindExact(string query)
    {
        string normalized = Normalize(query);
        var matches = entries.Where(item => item.Topic.SearchNames.Contains(normalized)).ToArray();
        return matches.FirstOrDefault(item => item.Topic.TitleKey == normalized) is { } titled ? [titled] : matches;
    }

    public Entry[] Search(string query, string? book = null, bool optionalOnly = false, string? category = null)
    {
        string normalized = Normalize(query);
        string[] terms = normalized.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        var results = entries.Where(item => (book is null || item.Page.Book.Id == book) &&
                (!optionalOnly || item.Topic.IsOptional) && (category is null || item.Topic.BrowseCategory == category))
            .Select(item => (Item: item, Rank: item.Match(normalized, terms)))
            .Where(result => result.Rank > 0).ToArray();
        int threshold = results.Any(result => result.Rank >= 3) ? 3 : 1;
        return results.Where(result => result.Rank >= threshold)
            .OrderByDescending(result => result.Rank)
            .ThenBy(result => result.Item.Title, StringComparer.CurrentCultureIgnoreCase)
            .Select(result => result.Item)
            .ToArray();
    }

    internal static string Normalize(string text)
    {
        text = Regex.Replace(text, @"(?<=\p{L})[-\u00ad][ \t]*\r?\n[ \t]*(?=\p{L})", "");
        var result = new StringBuilder();
        foreach (char character in text.ToLowerInvariant().Normalize(NormalizationForm.FormD))
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark)
            {
                result.Append(char.IsLetterOrDigit(character) ? character : ' ');
            }
        }
        return string.Join(" ", result.ToString().Split(' ', StringSplitOptions.RemoveEmptyEntries));
    }

    private sealed record Pack(int Version, IReadOnlyList<LocalBook> Books);
    private sealed record TranslationPack(int Version, Dictionary<string, TranslationBook> Books);
    private sealed record TranslationBook(string Sha256, Dictionary<int, string> Pages);
    internal sealed record LocalBook(string Id, string Title, string Path, string? Sha256, IReadOnlyList<LocalPage> Pages)
    {
        public bool IsEnglish => Id is "britain" or "carpathia";
    }
    internal sealed record LocalPage(int Number, int? Printed, string Section, string Text);
    internal sealed record Topic(string Title, string[] Aliases, string Book, int Page, string? Kind, string? Summary,
        string? Category, string[]? Sections, int? ThroughPage, bool TablePages, string[]? SourceNames)
    {
        public string TitleKey { get; } = Normalize(Title);
        public string[] SearchNames { get; } = Aliases.Prepend(Title).Select(Normalize).ToArray();
        public string[] HeadingNames => SourceNames is null ? SearchNames : SearchNames.Concat(SourceNames.Select(Normalize)).ToArray();
        public string BrowseCategory => Category ?? "Procedimentos";
        public bool IsOptional => Kind is "Regra opcional" or "Criação alternativa" or "Regra excepcional" or
            "Opção de aventura" or "Opção de personagem" or "Variante regional";
    }

    internal sealed record Entry(Topic Topic, IndexedPage Page, ReferenceText.Block[] Original, ReferenceText.Block[] Portuguese)
    {
        public string Title => Topic.Title;
        public string ShortSource => Page.Book.Id switch
        {
            "core" => "Livro de Regras",
            "britain" => "Britain & Ireland",
            "carpathia" => "Mythic Carpathia · beta",
            _ => Page.Book.Title,
        };
        public string PageLabel => Page.Page.Printed is int printed ? $"p. {printed}" : $"PDF {Page.Page.Number}";
        public string? Note => Topic.Kind;
        public string AccessibleName => $"{Title} · {ShortSource} · {PageLabel}";
        private string SearchText { get; } = $" {Normalize($"{Topic.Summary} {string.Join(' ', Original.Concat(Portuguese).Select(block => block.Text))}")} ";

        public int Match(string normalized, string[] terms)
        {
            if (terms.Length == 0) return 1;
            if (Topic.TitleKey == normalized) return 4;
            if (Topic.SearchNames.Contains(normalized)) return 3;
            if (Topic.SearchNames.Any(name => terms.All(term => name.Contains(term, StringComparison.Ordinal)))) return 2;
            return terms.All(term => SearchText.Contains($" {term} ", StringComparison.Ordinal) ||
                SearchText.Contains($" {term}s ", StringComparison.Ordinal)) ? 1 : 0;
        }
    }

    internal sealed record IndexedPage(LocalBook Book, LocalPage Page, string? Portuguese);
}
