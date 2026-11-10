using System.IO;
using System.Text.Json;

namespace Whisper.Preview;

/// <summary>Número ou regra-chave exibido na faixa de leitura rápida (ex.: "Dados" → "perícia + atributo").</summary>
internal sealed record CardFact(string Label, string Value)
{
    public string LabelUpper => Label.ToUpperInvariant();
}

/// <summary>Bloco de detalhes do cartão. Kind: "steps" (numerado), "bullets" ou "text".</summary>
internal sealed record CardSection(string Heading, string Kind, string[] Items);

/// <summary>Cartão padronizado de um tópico: situação de uso, números-chave e detalhes em ordem fixa.</summary>
internal sealed record Card(string? Group, string? When, CardFact[] Quick, CardSection[] Sections)
{
    public string SearchText => string.Join(' ', new[] { When ?? "" }
        .Concat(Quick.Select(fact => $"{fact.Label} {fact.Value}"))
        .Concat(Sections.SelectMany(section => section.Items)));

    public ReferenceText.Block[] ToBlocks()
    {
        var blocks = new List<ReferenceText.Block>();
        foreach (var section in Sections)
        {
            blocks.Add(new ReferenceText.Block(ReferenceText.Kind.Heading, section.Heading));
            var kind = section.Kind switch
            {
                "steps" => ReferenceText.Kind.Step,
                "bullets" => ReferenceText.Kind.Bullet,
                _ => ReferenceText.Kind.Paragraph,
            };
            blocks.AddRange(section.Items.Select(item => new ReferenceText.Block(kind, item)));
        }
        return blocks.ToArray();
    }
}

internal static class CardLibrary
{
    /// <summary>Guia escrito à mão (vaesen-guide.json): procedimentos, com grupos de navegação.</summary>
    public static (Dictionary<string, Card> Cards, string[] Groups) ReadGuide(string path)
    {
        var cards = new Dictionary<string, Card>();
        try
        {
            using FileStream file = File.OpenRead(path);
            using JsonDocument document = JsonDocument.Parse(file);
            JsonElement root = document.RootElement;
            var titles = new Dictionary<string, string>();
            var order = new List<string>();
            foreach (JsonElement group in root.GetProperty("groups").EnumerateArray().OrderBy(item => item.GetProperty("order").GetInt32()))
            {
                string title = Text(group, "title") ?? "";
                titles[Text(group, "id") ?? title] = title;
                order.Add(title);
            }
            foreach (JsonProperty item in root.GetProperty("cards").EnumerateObject())
            {
                JsonElement value = item.Value;
                var sections = new List<CardSection>();
                string[] steps = Strings(value, "steps");
                string[] watch = Strings(value, "watch");
                string[] related = Strings(value, "related");
                if (steps.Length > 0) sections.Add(new CardSection("Como fazer", "steps", steps));
                if (watch.Length > 0) sections.Add(new CardSection("Atenção", "bullets", watch));
                if (related.Length > 0) sections.Add(new CardSection("Veja também", "text", [string.Join("  ·  ", related)]));
                string? groupId = Text(value, "group");
                string? group = groupId is not null && titles.TryGetValue(groupId, out string? found) ? found : null;
                cards[item.Name] = new Card(group, Text(value, "when"), Facts(value), sections.ToArray());
            }
            return (cards, order.ToArray());
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or JsonException or
            KeyNotFoundException or InvalidOperationException)
        {
            return (new Dictionary<string, Card>(), Array.Empty<string>());
        }
    }

    /// <summary>Fichas estruturadas pelo script build_vaesen_cards.py a partir dos PDFs locais (opcional).</summary>
    public static Dictionary<string, Card> ReadGenerated(string path)
    {
        var cards = new Dictionary<string, Card>();
        try
        {
            using FileStream file = File.Open(path, FileMode.Open, FileAccess.Read, FileShare.Read | FileShare.Delete);
            using JsonDocument document = JsonDocument.Parse(file);
            foreach (JsonProperty item in document.RootElement.GetProperty("cards").EnumerateObject())
            {
                JsonElement value = item.Value;
                var sections = new List<CardSection>();
                if (value.TryGetProperty("sections", out JsonElement list) && list.ValueKind == JsonValueKind.Array)
                {
                    foreach (JsonElement section in list.EnumerateArray())
                    {
                        string[] items = Strings(section, "items");
                        if (items.Length > 0)
                        {
                            sections.Add(new CardSection(Text(section, "heading") ?? "", Text(section, "kind") ?? "text", items));
                        }
                    }
                }
                cards[item.Name] = new Card(null, Text(value, "when"), Facts(value), sections.ToArray());
            }
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or JsonException or
            KeyNotFoundException or InvalidOperationException)
        {
            cards.Clear();
        }
        return cards;
    }

    private static string? Text(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String ? value.GetString() : null;

    private static string[] Strings(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.Array
            ? value.EnumerateArray().Select(item => item.GetString() ?? "").Where(text => text.Length > 0).ToArray()
            : [];

    private static CardFact[] Facts(JsonElement element) =>
        element.TryGetProperty("quick", out JsonElement value) && value.ValueKind == JsonValueKind.Array
            ? value.EnumerateArray()
                .Where(pair => pair.ValueKind == JsonValueKind.Array && pair.GetArrayLength() >= 2)
                .Select(pair => new CardFact(pair[0].GetString() ?? "", pair[1].GetString() ?? ""))
                .Where(fact => fact.Label.Length > 0 && fact.Value.Length > 0).ToArray()
            : [];
}
