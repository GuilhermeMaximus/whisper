using System.Text.RegularExpressions;
using static Whisper.Preview.ReferenceText;

namespace Whisper.Preview;

internal static class TechnicalReference
{
    private static readonly string[] CreatureSections =
    ["caracteristicas", "characteristics", "poderes magicos", "magical powers", "condicoes", "conditions", "combate", "combat"];
    private static readonly string[] ArchetypeFields =
    ["atributo principal", "atributo chave", "main attribute", "key attribute", "pericia principal", "habilidade principal",
        "pericia chave", "habilidade chave", "main skill", "key skill", "talentos", "talents", "recursos", "resources",
        "equipamento", "equipment", "personal gear", "equipamento pessoal", "itens pessoais"];
    private static readonly Regex UpgradeField = new(
        @"\b(?:pré-?requisito|prerequisito|prerequisite|requisito|development points|pontos de desenvolvimento|custo|function|função|asset|ativo)\s*:",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

    public static Block[] Select(VaesenCatalog.Topic topic, IEnumerable<string> pages)
    {
        if (topic.Category == "Arquétipos")
        {
            return pages.SelectMany(Archetype).ToArray();
        }
        var blocks = pages.SelectMany(Format).ToArray();
        if (topic.TablePages)
        {
            return blocks;
        }
        string[] names = topic.Sections?.Select(VaesenCatalog.Normalize).ToArray() ?? [];
        if (names.Length > 0)
        {
            return Sections(blocks, names, includeHeadings: true);
        }

        return topic.Category switch
        {
            "Criaturas" when !topic.IsOptional => Sections(blocks, CreatureSections, includeHeadings: true),
            "Rituais" => Sections(blocks, ["ritual"], includeHeadings: false),
            "Talentos" => Talent(blocks, topic.HeadingNames),
            "Melhorias da sede" => Upgrade(blocks, topic.HeadingNames),
            _ => [],
        };
    }

    private static IEnumerable<Block> Archetype(string page)
    {
        var lines = page.ReplaceLineEndings("\n").Split('\n');
        for (int index = 0; index < lines.Length; index++)
        {
            string line = lines[index].TrimStart();
            if (!IsBullet(line) || !ArchetypeFields.Any(field => Key(line).StartsWith(field + " ", StringComparison.Ordinal)))
            {
                continue;
            }
            int end = index;
            while (end + 1 < lines.Length && lines[end].Length > 0 &&
                (char.IsWhiteSpace(lines[end][^1]) || lines[end][^1] is '\u0002' or '\u00ad') &&
                !string.IsNullOrWhiteSpace(lines[end + 1]) && !IsBullet(lines[end + 1].TrimStart()))
            {
                end++;
            }
            foreach (var block in Format(string.Join('\n', lines[index..(end + 1)])))
            {
                yield return block;
            }
            index = end;
        }
    }

    private static bool IsBullet(string line) => line.StartsWith("· ") || line.StartsWith("• ");

    private static Block[] Talent(Block[] blocks, string[] names)
    {
        var section = Sections(blocks, names, includeHeadings: false);
        if (section.Length > 0)
        {
            return section;
        }
        // Some talents are listed as a labeled bullet inside an archetype.
        return blocks.Where(block => block.Type == Kind.Bullet && block.Text.Contains(':') &&
            names.Contains(Key(block.Text.Split(':', 2)[0])))
            .Select(block => new Block(Kind.Paragraph, block.Text.Split(':', 2)[1].Trim())).ToArray();
    }

    private static Block[] Upgrade(Block[] blocks, string[] names)
    {
        var section = Sections(blocks, names, includeHeadings: false);
        return section.Select(block => (Block: block, Field: UpgradeField.Match(block.Text)))
            .Where(item => item.Field.Success)
            .Select(item => item.Block with { Text = item.Block.Text[item.Field.Index..] }).ToArray();
    }

    private static Block[] Sections(Block[] blocks, string[] names, bool includeHeadings)
    {
        var result = new List<Block>();
        for (int index = 0; index < blocks.Length; index++)
        {
            var heading = blocks[index];
            if (heading.Type != Kind.Heading)
            {
                continue;
            }
            string key = Key(heading.Text);
            if (!MatchesHeading(names, key) && index + 1 < blocks.Length && blocks[index + 1].Type == Kind.Heading &&
                MatchesHeading(names, Key($"{heading.Text} {blocks[index + 1].Text}")))
            {
                heading = heading with { Text = $"{heading.Text} {blocks[++index].Text}" };
                key = Key(heading.Text);
            }
            if (!MatchesHeading(names, key))
            {
                continue;
            }
            var body = blocks.Skip(index + 1).TakeWhile(block => block.Type != Kind.Heading && !IsDialogue(block.Text)).ToArray();
            if (body.Length > 0)
            {
                if (includeHeadings) result.Add(heading);
                result.AddRange(body);
            }
        }
        return result.ToArray();
    }

    private static string Key(string value) => VaesenCatalog.Normalize(value);

    private static bool IsDialogue(string value) => value.StartsWith("Jogador 1", StringComparison.OrdinalIgnoreCase) ||
        value.StartsWith("Jogadora 1", StringComparison.OrdinalIgnoreCase) ||
        value.StartsWith("Mestre do Jogo:", StringComparison.OrdinalIgnoreCase);

    private static bool MatchesHeading(string[] names, string key) => names.Contains(key) ||
        names.Any(name => key == name + " general talent" || key == name + " talento geral" || key == name + " talento general");
}
