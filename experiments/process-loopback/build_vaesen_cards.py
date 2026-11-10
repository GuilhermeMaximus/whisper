"""Estrutura as fichas de Vaesen (criaturas, rituais, talentos, melhorias e arquétipos) em cartões padronizados.

Lê o índice local importado dos seus PDFs (local-rules/vaesen.json e, se existir, a tradução vaesen-pt-br.json)
e grava local-rules/vaesen-cards.json. O resultado deriva dos livros e, por isso, fica fora do Git.

Uso: python experiments/process-loopback/build_vaesen_cards.py [--report]
"""

import argparse
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parent
RULES = ROOT / "local-rules"
ENTRIES = ROOT.parent / "desktop-preview" / "vaesen-entries.json"
OUTPUT = RULES / "vaesen-cards.json"

BULLET = re.compile(r"^(?:[·••-]|[^\w\s(\"“'—–])\s*")
ATTRIBUTES = ("PODER", "CONTROLE CORPORAL", "MAGIA", "MANIPULAÇÃO", "MEDO")
ATTR_PATTERN = re.compile(r"(PODER|CONTROLE CORPORAL|MAGIA|MANIPULA[ÇC][ÃA]O|MEDO)\.?\s*([0-9]+(?:/[0-9]+)?|[—–-])", re.IGNORECASE)


def fold(text):
    text = unicodedata.normalize("NFD", text.lower())
    return " ".join("".join(c if c.isalnum() else " " for c in text if unicodedata.category(c) != "Mn").split())


def clean(text):
    # Em alguns blocos o marcador de lista é U+0085, que splitlines() trataria como quebra de linha.
    text = text.replace("\x85", "· ")
    text = re.sub(r"(?m)^[ \t]*\u0002\s*", "· ", text)
    text = re.sub(r"[\u0002\u00ad]", "", text)
    return re.sub(r"(?<=\w)-\n(?=\w)", "", text)


COLUMN_WORDS = {"ATAQUE", "DANO", "DANOS", "ALCANCE", "ATTACK", "DAMAGE", "RANGE", "DE", "RESISTENCIA", "RESISTÊNCIA"}


def is_heading(line):
    words = set(re.findall(r"[A-ZÀ-Ý]+", line))
    return (2 < len(line) <= 90 and any(c.isalpha() for c in line) and line == line.upper()
            and not BULLET.match(line) and not re.fullmatch(r"[\W\d_]*", line)
            and not ATTR_PATTERN.match(line) and not (words and words <= COLUMN_WORDS))


def split_sections(text):
    """Divide a página em seções por títulos em maiúsculas. Cada seção é (título, [linhas])."""
    sections = [("", [])]
    for raw in clean(text).splitlines():
        line = raw.strip()
        if not line or re.fullmatch(r"·.*·", line):
            continue
        if is_heading(line):
            sections.append((line, []))
        else:
            sections[-1][1].append(line)
    return sections


def paragraphs(lines):
    """Junta linhas quebradas em itens: cada marcador de lista começa um item; o resto vira parágrafos."""
    items, current = [], None
    for line in lines:
        starts = BULLET.match(line)
        if starts:
            if current is not None:
                items.append(current)
            current = line[starts.end():].strip()
        elif current is None:
            current = line
        else:
            current += " " + line
    if current is not None:
        items.append(current)
    return items


def find(sections, *names):
    wanted = {fold(n) for n in names}
    return [lines for heading, lines in sections if fold(heading) in wanted]


class Source:
    def __init__(self):
        books = json.loads((RULES / "vaesen.json").read_text(encoding="utf-8"))["books"]
        self.pages = {(b["id"], p["number"]): p["text"] for b in books for p in b["pages"]}
        self.hashes = {b["id"]: b.get("sha256") for b in books}
        self.translation = {}
        path = RULES / "vaesen-pt-br.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            for book, item in data.get("books", {}).items():
                if item.get("sha256") == self.hashes.get(book):
                    self.translation[book] = item["pages"]

    def text(self, book, page):
        translated = self.translation.get(book, {}).get(str(page))
        return translated or self.pages[(book, page)]


ATTACK_ROW = re.compile(r"([A-Za-zÀ-ÿ][\wÀ-ÿ' ./-]*?)\s+(\d+[†*‡]*|[—–])\s+(\d+(?:[–-]\d+)?[†*‡]*|[—–])(?=\s+[A-ZÀ-Ý]|\s*$)")


def attack_rows(items):
    """Transforma 'ATAQUE DANO ALCANCE Garras 2 0 ...' em uma linha legível por ataque."""
    if not items:
        return items
    head = re.sub(r"^(?:ATAQUE\s+DANO\s+ALCANCE|ATTACK\s+DAMAGE\s+RANGE|RANGE DE DANOS DE ATAQUE)\s*", "", items[0], flags=re.IGNORECASE)
    rows = [f"{name.strip()} — dano {damage}, alcance {reach}" for name, damage, reach in ATTACK_ROW.findall(head)]
    return rows + items[1:] if rows else items


def creature(entry, sections):
    heads = [fold(h) for h, _ in sections]
    if heads.count("caracteristicas") != 1:
        return None
    card = {"quick": [], "sections": []}
    for lines in find(sections, "CARACTERÍSTICAS"):
        found = {}
        for name, value in ATTR_PATTERN.findall(" ".join(lines)):
            found.setdefault(fold(name), value)
        for attribute in ATTRIBUTES:
            value = found.get(fold(attribute))
            if value:
                card["quick"].append([attribute.capitalize() if attribute != "CONTROLE CORPORAL" else "Controle Corporal", value])
    if not card["quick"]:
        return None
    for heading, names in (("Poderes mágicos", ("PODERES MÁGICOS",)), ("Combate", ("COMBATE",)),
                           ("Condições", ("CONDIÇÕES",)), ("Ritual", ("RITUAL",))):
        for lines in find(sections, *names)[:1]:
            items = paragraphs(lines)
            if heading == "Combate":
                items = attack_rows(items)
            if items:
                card["sections"].append({"heading": heading, "kind": "bullets" if heading in ("Poderes mágicos", "Combate", "Condições") else "text",
                                         "items": items})
    card["when"] = "Ficha de criatura: use atributos, poderes e ritual na mesa."
    return card


def ritual(entry, sections):
    lines = find(sections, "RITUAL")
    if not lines:
        return None
    items = paragraphs(lines[0])
    if not items:
        return None
    creature_name = re.sub(r"^Ritual\s*[·:-]\s*", "", entry["title"]).strip()
    return {"when": f"O grupo quer expulsar, prender ou matar: {creature_name}.",
            "quick": [["Dados", "nenhum: as jogadoras descrevem o ritual"], ["Criatura", creature_name]],
            "sections": [{"heading": "Como banir", "kind": "text", "items": items}]}


UPGRADE_FIELDS = (
    ("Pré-requisito", r"pr[ée]-?requisito"), ("Custo", r"custo|pontos de desenvolvimento"),
    ("Função", r"fun[çc][ãa]o"), ("Ativo", r"ativo"), ("Descoberta", r"descoberta"),
)


def upgrade(entry, sections):
    names = {fold(entry["title"])} | {fold(a) for a in entry["aliases"]} | {fold(n) for n in entry.get("sourceNames", [])}
    names |= {fold(re.sub(r"^melhoria\s+", "", a, flags=re.IGNORECASE)) for a in entry["aliases"]}
    for heading, lines in sections:
        if fold(heading) not in names:
            continue
        text = " ".join(lines)
        pattern = "|".join(f"(?P<f{i}>{p})" for i, (_, p) in enumerate(UPGRADE_FIELDS))
        marks = [(m.start(), m.end(), next(i for i in range(len(UPGRADE_FIELDS)) if m.group(f"f{i}")))
                 for m in re.finditer(rf"(?:^|(?<=\s))(?:{pattern})\s*:", text, re.IGNORECASE)]
        if not marks:
            continue
        values = {}
        for n, (start, end, index) in enumerate(marks):
            stop = marks[n + 1][0] if n + 1 < len(marks) else len(text)
            values.setdefault(UPGRADE_FIELDS[index][0], text[end:stop].strip(" ·"))
        quick = [[label, values[label]] for label in ("Pré-requisito", "Custo") if label in values]
        body = []
        for label in ("Função", "Ativo", "Descoberta"):
            if label in values:
                body.append(f"{label}: {values[label]}")
        if not body:
            continue
        return {"when": "Comprar ou usar esta melhoria da base.", "quick": quick,
                "sections": [{"heading": "O que faz", "kind": "bullets", "items": body}]}
    return None


ARCH_FIELDS = (("Atributo principal", r"atributo\s+(?:principal|chave)"), ("Perícia principal", r"per[ií]cia\s+(?:principal|chave)|habilidade\s+(?:principal|chave)"),
               ("Talentos", r"talentos"), ("Recursos", r"recursos"), ("Equipamento", r"equipamento(?:\s+pessoal)?"))


def labeled_bullets(raw):
    """Campos de arquétipo escritos como '· RÓTULO: valor', cujo valor quebra linhas com espaço final."""
    lines = clean(raw).splitlines()
    values = {}
    for index, line in enumerate(lines):
        match = BULLET.match(line.strip())
        body = line.strip()[match.end():] if match else ""
        for label, pattern in ARCH_FIELDS:
            found = re.match(rf"(?:{pattern})\s*:\s*(.*)$", body, re.IGNORECASE)
            if found and label not in values:
                value, cursor = found.group(1), index
                while cursor + 1 < len(lines) and lines[cursor].endswith((" ", "-")) and lines[cursor + 1].strip() \
                        and not BULLET.match(lines[cursor + 1].strip()):
                    cursor += 1
                    value += " " + lines[cursor].strip()
                values[label] = value.strip(" ·")
    return values


def archetype(entry, sections, raw=""):
    values = labeled_bullets(raw)
    if "Atributo principal" not in values or "Perícia principal" not in values:
        return None
    card = {"when": "Escolher este arquétipo na criação da personagem.",
            "quick": [[k, values[k]] for k in ("Atributo principal", "Perícia principal", "Recursos") if k in values], "sections": []}
    for label in ("Talentos", "Equipamento"):
        if label in values:
            card["sections"].append({"heading": label, "kind": "text", "items": [values[label]]})
    return card


def talent(entry, sections):
    names = {fold(entry["title"])} | {fold(re.sub(r"^talento\s+", "", a, flags=re.IGNORECASE)) for a in entry["aliases"]}
    for index, (heading, lines) in enumerate(sections):
        if fold(heading) in names and lines:
            group = sections[index - 1][0] if index and not sections[index - 1][1] else ""
            items = paragraphs(lines)
            quick = [["Arquétipo", group.title()]] if group else []
            return {"when": "Comprar ou usar este talento.", "quick": quick,
                    "sections": [{"heading": "Efeito", "kind": "text", "items": items}]}
    return None


PARSERS = {"Criaturas": creature, "Rituais": ritual, "Melhorias da sede": upgrade, "Arquétipos": archetype, "Talentos": talent}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true", help="lista as fichas que ficaram sem cartão")
    arguments = parser.parse_args()
    source = Source()
    entries = json.loads(ENTRIES.read_text(encoding="utf-8"))
    cards, skipped = {}, {}
    for entry in entries:
        sections = split_sections(source.text(entry["book"], entry["page"]))
        raw = source.text(entry["book"], entry["page"])
        card = PARSERS[entry["category"]](entry, sections, raw) if entry["category"] == "Arquétipos" else PARSERS[entry["category"]](entry, sections)
        if card:
            cards[entry["title"]] = card
        else:
            skipped.setdefault(entry["category"], []).append(entry["title"])
    OUTPUT.write_text(json.dumps({"version": 1, "cards": cards}, ensure_ascii=False, indent=1), encoding="utf-8")
    total = {}
    for entry in entries:
        total[entry["category"]] = total.get(entry["category"], 0) + 1
    for category, count in total.items():
        done = count - len(skipped.get(category, []))
        print(f"{category}: {done}/{count} com cartão")
        if arguments.report:
            for title in skipped.get(category, []):
                print("   sem cartão:", title)


if __name__ == "__main__":
    main()
