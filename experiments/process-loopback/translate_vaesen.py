"""Build a Brazilian Portuguese reading layer for the imported English PDFs."""

import argparse
import json
from pathlib import Path
import re


NUMBER = re.compile(r"(?<!\w)(?:[+−±-]?(?:\d+(?:[.,–-]\d+)?(?:/\d+)?(?:[Dd]\d+)?)|[Dd]\d+)(?!\w)")
NUMBER_DASHES = str.maketrans("−–", "--")
DICE_ROW = re.compile(r"^(?:\d{1,2}(?:[–-]\d{1,2})?|—)\s+\S")
TABLE_TERMS = re.compile(r"\b(?:D66|D6|DAMAGE|RANGE|RESOURCES|EFFECT|AVAILABILITY|PROFESSION|WORKER)\b")
STATS = re.compile(r"^(?:MIGHT|BODY CONTROL|MAGIC|MANIPULATION|FEAR)\s+(?:\d|[–—-])", re.I)
CONTENTS_ROW = re.compile(r"(.+?)\s*\ufffd{2,}\s*(\d+)")
SENTENCE = re.compile(r"(?<!\bMr)(?<!\bMs)(?<!\bDr)(?<!\bSt)(?<!\bMrs)(?<!\bp)"
                      r"(?<=[.!?])\s+(?=[“\"‘']?[A-Z])")
GLOSSARY = {
    "SOCIAL CLASS (OPTIONAL)": "CLASSE SOCIAL (OPCIONAL)",
    "VAMPIRE HUNTER": "CAÇADOR DE VAMPIROS",
    "CITY LIFE": "VIDA URBANA",
    "CHARACTERISTICS": "CARACTERÍSTICAS",
    "MAGICAL POWERS": "PODERES MÁGICOS",
    "CONDITIONS": "CONDIÇÕES",
    "COMBAT": "COMBATE",
    "RITUAL": "RITUAL",
    "VARIANTS": "VARIANTES",
    "EXAMPLES OF CONFLICTS": "EXEMPLOS DE CONFLITOS",
    "UPGRADES": "MELHORIAS",
    "FACILITIES": "INSTALAÇÕES",
    "CONTACTS": "CONTATOS",
    "PERSONNEL": "PESSOAL",
    "MIGHT": "PODER",
    "BODY CONTROL": "CONTROLE CORPORAL",
    "MAGIC": "MAGIA",
    "MANIPULATION": "MANIPULAÇÃO",
    "FEAR": "MEDO",
    "CLOSE COMBAT": "COMBATE CORPO A CORPO",
    "RANGED COMBAT": "COMBATE À DISTÂNCIA",
    "INSPIRATION": "INSPIRAÇÃO",
    "EMPATHY": "EMPATIA",
    "LEARNING": "APRENDIZADO",
    "INVESTIGATION": "INVESTIGAÇÃO",
    "OBSERVATION": "OBSERVAÇÃO",
    "VIGILANCE": "VIGILÂNCIA",
    "STEALTH": "FURTIVIDADE",
    "AGILITY": "AGILIDADE",
    "FORCE": "FORÇA",
    "MEDICINE": "MEDICINA",
    "ATTACK": "ATAQUE",
    "DAMAGE": "DANO",
    "RANGE": "ALCANCE",
    "RESOURCES": "RECURSOS",
    "EFFECT": "EFEITO",
    "AVAILABILITY": "DISPONIBILIDADE",
    "PROFESSION": "PROFISSÃO",
    "POOR": "POBRE",
    "WORKER": "TRABALHADOR",
    "BURGHER": "BURGUÊS",
    "ARISTOCRAT": "ARISTOCRATA",
    "SEE TABLE": "VEJA A TABELA",
}
TERMS = re.compile(r"\b(?:" + "|".join(map(re.escape, sorted(GLOSSARY, key=len, reverse=True))) + r")\b")


def is_heading(line):
    return len(line) <= 90 and line.isupper()


def page_units(text):
    lines = text.replace("\r\n", "\n").split("\n")
    dice_table = sum(bool(DICE_ROW.match(line.strip())) for line in lines) >= 4
    units = []
    paragraph = ""
    wrapped = False
    join_word = False
    table = False

    def flush():
        nonlocal paragraph
        if paragraph:
            units.append(("prose", paragraph))
            paragraph = ""

    for raw in lines:
        line = raw.strip().replace("\u0002", "").replace("\u00ad", "").replace("\xa0", " ")
        if contents := CONTENTS_ROW.fullmatch(line):
            flush()
            units.append(("values", f"{contents[1]}  {contents[2]}"))
            continue
        line = line.replace("\ufffd", " ").strip()
        if not line:
            flush()
            table = False
            continue
        heading = is_heading(line)
        columns = heading and (len(TABLE_TERMS.findall(line)) >= 2 or (dice_table and line.startswith("D66 ")))
        if line.startswith("·") and line.endswith("·"):
            flush()
            continue
        if columns or STATS.match(line) or (dice_table and DICE_ROW.match(line)):
            flush()
            table = True
            units.append(("values", line))
            continue
        if table and not heading and not line.startswith(("· ", "• ")):
            units.append(("values", line))
            continue
        table = False
        if heading:
            flush()
            units.append(("heading", line))
            continue
        if line.startswith(("· ", "• ")) or not wrapped:
            flush()
        if paragraph and not join_word:
            paragraph += " "
        paragraph += line
        end = raw.rstrip()[-1]
        join_word = end in "\u0002\u00ad-"
        wrapped = join_word or raw[-1].isspace() or not line.rstrip('”’")').endswith((".", "?", "!"))
    flush()
    return units


class Translator:
    def __init__(self, model, threads):
        import ctranslate2
        import sentencepiece

        self.sp = sentencepiece.SentencePieceProcessor(model_file=str(model / "sentencepiece.model"))
        self.engine = ctranslate2.Translator(
            str(model / "model"), device="cpu", compute_type="int8",
            inter_threads=2, intra_threads=max(1, threads // 2),
        )

    def batch(self, texts, beam_size=3):
        if not texts:
            return []
        tokens = self.sp.encode(texts, out_type=str)
        results = self.engine.translate_batch(
            tokens, beam_size=beam_size, max_batch_size=1536, batch_type="tokens", max_decoding_length=400,
        )
        translated = self.sp.decode([result.hypotheses[0] for result in results])
        return [re.sub(r"\b(?:NPCs?|Games?master)\b", lambda match: {
                    "NPC": "PNJ", "NPCs": "PNJs",
                }.get(match[0], "Mestre"), line.replace("▁", " ")).strip() for line in translated]


def numeric_pieces(text):
    pieces = []
    start = 0
    for match in NUMBER.finditer(text):
        pieces.append((False, text[start:match.start()]))
        pieces.append((True, match[0]))
        start = match.end()
    pieces.append((False, text[start:]))
    return pieces


def restore_numbers(original, translated):
    numbers = NUMBER.findall(original)
    if [number.translate(NUMBER_DASHES) for number in numbers] != [
        number.translate(NUMBER_DASHES) for number in NUMBER.findall(translated)
    ]:
        return None
    values = iter(numbers)
    return NUMBER.sub(lambda match: next(values), translated)


def translate_pages(translator, pages):
    units = [page_units(page["text"]) for page in pages]
    records = []
    requests = []
    for page_units_list in units:
        for unit, (kind, text) in enumerate(page_units_list):
            bullet = "· " if text.startswith(("· ", "• ")) else ""
            content = text[2:] if bullet else text
            # Keep a paragraph within the model window while splitting at word boundaries.
            sentences = SENTENCE.split(content) if kind == "prose" else [content]
            pieces = [part for sentence in sentences for part in
                      re.findall(r".{1,650}(?:\s+|$)|\S+", sentence)]
            for index, part in enumerate(pieces):
                part = part.strip()
                if not part:
                    continue
                direct = GLOSSARY.get(part.upper())
                if direct is not None or not any(ch.isalpha() for ch in part):
                    records.append((unit, kind, bullet if index == 0 else "", part, None, direct or part))
                else:
                    records.append((unit, kind, bullet if index == 0 else "", part, len(requests), None))
                    requests.append(part)
        records.append((None, None, "", "", None, None))

    inputs = [NUMBER.sub(lambda match: match[0].translate(NUMBER_DASHES), text) for text in requests]
    translations = [restore_numbers(original, translated) for original, translated in
                    zip(requests, translator.batch(inputs), strict=True)]
    prose_retries = [request for _, kind, _, _, request, _ in records
                     if kind == "prose" and request is not None and not translations[request]]
    for request, result in zip(prose_retries, translator.batch([inputs[i] for i in prose_retries], beam_size=5), strict=True):
        translations[request] = restore_numbers(requests[request], result)
    replacements = {}
    retry = []
    for index, (_, kind, _, original, request, _) in enumerate(records):
        if request is None:
            continue
        numbers = NUMBER.findall(original)
        if kind == "values" and numbers:
            parts = []
            for number, piece in numeric_pieces(original):
                leading = piece[:len(piece) - len(piece.lstrip())]
                trailing = piece[len(piece.rstrip()):] if piece.strip() else ""
                core = piece.strip()
                glossary = GLOSSARY.get(core.upper()) or TERMS.sub(lambda match: GLOSSARY[match[0]], core)
                if number or not any(ch.isalpha() for ch in core) or glossary != core:
                    parts.append((None, leading + glossary + trailing, "", ""))
                else:
                    parts.append((len(retry), "", leading, trailing))
                    retry.append(core)
            replacements[index] = parts
    recovered = translator.batch(retry)

    translated_pages = []
    buffer = []
    previous_unit = None
    previous_kind = None
    for index, (unit, kind, bullet, original, request, direct) in enumerate(records):
        if kind is None:
            translated_pages.append("\n".join(buffer))
            buffer.clear()
            previous_unit = None
            previous_kind = None
            continue
        if index in replacements:
            result = "".join(
                literal if position is None else leading + recovered[position].strip() + trailing
                for position, literal, leading, trailing in replacements[index]
            )
            if NUMBER.findall(original) != NUMBER.findall(result):
                # Never substitute a table value or rule modifier with a model prediction.
                result = TERMS.sub(lambda match: GLOSSARY[match[0]], original)
        else:
            result = direct if request is None else translations[request]
        if not result:
            result = original
        result = result.replace("\ufffd", " ").strip()
        if kind == "heading":
            result = result.upper()
        if previous_unit == unit and kind == "prose":
            buffer[-1] += " " + result
        else:
            if buffer and (kind != "values" or previous_kind != "values"):
                buffer.append("")
            buffer.append(bullet + result)
        previous_unit = unit
        previous_kind = kind
    return translated_pages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--pack", type=Path, default=Path(__file__).parent / "local-rules" / "vaesen.json")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--first-pages", nargs="*", type=int, default=[])
    parser.add_argument("--preview", action="store_true", help="Translate only the pages named by --first-pages")
    args = parser.parse_args()
    pack = json.loads(args.pack.read_text(encoding="utf-8"))
    output = args.pack.with_name(f"{args.pack.stem}-pt-br.json")
    current = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    if current.get("version") != 3:
        current = {"version": 3, "books": {}}
    translator = Translator(args.model, args.threads)
    for book in pack["books"]:
        if book["id"] not in ("britain", "carpathia"):
            continue
        entry = current["books"].get(book["id"])
        if not entry or entry["sha256"] != book["sha256"]:
            entry = {"sha256": book["sha256"], "pages": {}}
            current["books"][book["id"]] = entry
        done = entry["pages"]
        all_pages = [page for page in book["pages"] if page["text"].strip()]
        todo = [page for page in all_pages if str(page["number"]) not in done and
                (not args.preview or page["number"] in args.first_pages)]
        todo.sort(key=lambda page: (page["number"] not in args.first_pages, page["number"]))
        for start in range(0, len(todo), 8):
            batch = todo[start:start + 8]
            for page, text in zip(batch, translate_pages(translator, batch), strict=True):
                done[str(page["number"])] = text
            temporary = output.with_suffix(".tmp")
            temporary.write_text(json.dumps(current, ensure_ascii=False), encoding="utf-8")
            temporary.replace(output)
            print(f"{book['id']}: {len(done)}/{len(all_pages)} pages", flush=True)


if __name__ == "__main__":
    main()
