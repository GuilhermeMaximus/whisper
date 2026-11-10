using System.Text;
using System.Text.RegularExpressions;

namespace Whisper.Preview;

internal static class ReferenceText
{
    private static readonly Regex PageDecoration = new(
        @"^\s*·\s*.+\s*·\s*$", RegexOptions.CultureInvariant);
    private static readonly Regex Columns = new(
        @"\b(?:D66|D6|ATAQUE|ATTACK|DANOS?|DAMAGE|ALCANCE|RANGE|RECURSOS|RESOURCES|EFEITO|EFFECT|DISPONIBILIDADE|AVAILABILITY|PROFISSÃO|PROFESSION)\b",
        RegexOptions.CultureInvariant);
    private static readonly Regex DiceRow = new(@"^(?:\d{1,2}(?:[–-]\d{1,2})?|—)\s+\S", RegexOptions.CultureInvariant);
    private static readonly Regex AttributeLine = new(
        @"^(?:PODER|MIGHT|CONTROLE CORPORAL|BODY CONTROL|MAGIA|MAGIC|MANIPULAÇÃO|MANIPULATION|MEDO|FEAR)\s+(?:\d|[–—-])",
        RegexOptions.CultureInvariant);
    private static readonly Regex ColumnContinuation = new(
        @"^(?:LIMITE DE|TEMPO EFEITO|COMBATE À DISTÂNCIA|COMBATE CORPO A CORPO|CLOSE COMBAT|RANGED COMBAT|FORÇA|FORCE)$",
        RegexOptions.CultureInvariant);

    internal enum Kind { Paragraph, Heading, Bullet, Values, Step }
    internal sealed record Block(Kind Type, string Text);

    public static IEnumerable<Block> Format(string text)
    {
        string[] lines = text.ReplaceLineEndings("\n").Split('\n');
        int first = 0;
        while (first < lines.Length && (string.IsNullOrWhiteSpace(lines[first]) || PageDecoration.IsMatch(lines[first])))
        {
            first++;
        }

        bool hasDiceTable = lines.Count(line => DiceRow.IsMatch(line.TrimStart())) >= 4;
        Kind current = Kind.Paragraph;
        var buffer = new StringBuilder();
        bool wrapped = false;
        bool joinsWord = false;

        for (int index = first; index < lines.Length; index++)
        {
            string raw = lines[index];
            string line = raw.Trim().Replace("\u0002", "").Replace("\u00ad", "");
            if (line.Length == 0)
            {
                if (buffer.Length > 0)
                {
                    yield return new Block(current, buffer.ToString());
                    buffer.Clear();
                }
                current = Kind.Paragraph;
                continue;
            }

            bool bullet = line.StartsWith("· ") || line.StartsWith("• ");
            bool heading = !bullet && IsHeading(line) &&
                !(buffer.Length > 0 && wrapped && EndsSentence(line) && !EndsSentence(buffer.ToString()));
            bool columns = heading && (Columns.Matches(line).Count >= 2 ||
                (hasDiceTable && line.StartsWith("D66 ", StringComparison.Ordinal)));
            bool values = columns || AttributeLine.IsMatch(line) || (hasDiceTable && DiceRow.IsMatch(line));

            if (values || (current == Kind.Values && !bullet && (!heading || ColumnContinuation.IsMatch(line))))
            {
                if (buffer.Length > 0 && current != Kind.Values)
                {
                    yield return new Block(current, buffer.ToString());
                    buffer.Clear();
                }
                current = Kind.Values;
                if (buffer.Length > 0)
                {
                    buffer.Append('\n');
                }
                buffer.Append(line);
                continue;
            }

            if (buffer.Length > 0 && (heading || bullet || current == Kind.Values || !wrapped))
            {
                yield return new Block(current, buffer.ToString());
                buffer.Clear();
            }
            if (heading)
            {
                yield return new Block(Kind.Heading, line);
                current = Kind.Paragraph;
                continue;
            }

            if (buffer.Length == 0)
            {
                current = bullet ? Kind.Bullet : Kind.Paragraph;
            }
            else if (!joinsWord)
            {
                buffer.Append(' ');
            }
            buffer.Append(bullet ? line[2..] : line);
            char end = raw.TrimEnd()[^1];
            joinsWord = end is '\u0002' or '\u00ad' or '-';
            wrapped = joinsWord || char.IsWhiteSpace(raw[^1]) || !EndsSentence(line);
        }
        if (buffer.Length > 0)
        {
            yield return new Block(current, buffer.ToString());
        }
    }

    private static bool IsHeading(string line)
    {
        return line.Length <= 90 && line.Any(char.IsLetter) &&
            line.All(character => !char.IsLetter(character) || char.IsUpper(character));
    }

    private static bool EndsSentence(string line) => line.TrimEnd('”', '’', '"', ')').LastOrDefault() is '.' or '?' or '!';

}
