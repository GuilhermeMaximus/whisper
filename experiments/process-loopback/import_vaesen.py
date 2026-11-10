"""Build a private, offline reference index from the three supplied editions."""

import argparse
import hashlib
import json
from pathlib import Path
import re


PACK = Path(__file__).resolve().parent / "local-rules" / "vaesen.json"
BOOKS = (
    {
        "id": "core",
        "title": "Vaesen · Livro de Regras (PT-BR)",
        "offset": 3,
        "sha256": "c2f1cadc879805a94b210ced67f1341a5944d44b7c97bdc3b4f7fe882c5f59f4",
        "sections": (
            (1, "Preliminares"), (8, "Introdução e resumo"), (20, "Criação de personagem"),
            (29, "Arquétipos"), (40, "Perícias e testes"), (52, "Talentos"),
            (60, "Combate, condições e ferimentos"), (76, "Recursos, equipamento e armas"),
            (82, "Sociedade, base e campanha"), (100, "Norte lendário e Upsala"),
            (114, "Vaesen, magia, poderes e rituais"), (169, "PNJs, animais e criação de Vaesen"),
            (174, "Estrutura e criação de mistérios"), (199, "A Dança dos Sonhos"),
            (217, "Fichas"), (219, "Caminhos da Vida e tabelas de histórico"), (235, "Índice remissivo"),
        ),
        "optional": {
            28: "Criação alternativa · Caminhos da Vida",
            121: "Regra excepcional · personagens jogadoras usando magia",
            **dict.fromkeys(range(219, 235), "Criação alternativa · tabelas de histórico"),
        },
    },
    {
        "id": "britain",
        "title": "Mythic Britain & Ireland",
        "offset": 4,
        "sha256": "39f375dffb2099d11ef2aee1f6a359f1e9c4d51532139124afe0d185eb43a5a8",
        "sections": (
            (1, "Preliminares"), (9, "Cenário e classe social"),
            (30, "PNJs e perfis de jogo"), (37, "Locais e mundos paralelos"),
            (45, "Sociedade e Rose House"), (50, "Arquétipos, esportes e talentos"),
            (55, "Criaturas, poderes, fichas, rituais e variantes"),
            (88, "Old Meg"), (110, "The Llantywyll Incident"), (130, "The Hampstead Group"),
            (150, "Material de mesa"), (154, "Tabelas de histórico expandidas"), (158, "Bibliografia"),
        ),
        "optional": {
            14: "Regra opcional geral · classe social",
            93: "Regra opcional de Old Meg · dialeto e forasteiros",
            94: "Opção de Old Meg · sinais e presságios",
            131: "Variante de The Hampstead Group · conflito adicional",
            **dict.fromkeys(range(154, 158), "Criação alternativa · tabelas de histórico expandidas"),
        },
    },
    {
        "id": "carpathia",
        "title": "Mythic Carpathia (beta)",
        "offset": 2,
        "sha256": "84010a9ced8a7bb4b9e78ba5a59eca240d1f8d3f9d88af2a465d031bbac763bb",
        "sections": (
            (1, "Preliminares"), (7, "Cenário, folclore e vida cotidiana"),
            (25, "Pravda e Powder Gate"), (30, "Melhorias e ameaças da base"),
            (35, "Arquétipo Vampire Hunter"), (37, "Criaturas, poderes, fichas e rituais"),
            (76, "A Treaty of Blood"), (101, "The Gathering Storm"),
            (116, "The Secret of the Maharal"), (129, "Material de mesa"),
        ),
        "optional": {13: "Opção de personagem · origem social e relações com PNJs"},
    },
)

OPTIONAL_MARKER = re.compile(
    r"(?im)^\s*(?:optional(?: rules?)?|regras? opciona(?:l|is)|varia[nm]ts?|variantes)\b"
)


def import_book(source, book, pdf):
    with source.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != book["sha256"]:
        raise ValueError(f"Edição diferente da mapeada para {book['title']}: {source}")

    pages = []
    sections = iter(book["sections"])
    start, section = next(sections)
    upcoming = next(sections, None)
    with pdf.PdfDocument(source) as document:
        for index in range(len(document)):
            number = index + 1
            if upcoming and number == upcoming[0]:
                start, section = upcoming
                upcoming = next(sections, None)
            page = document[index]
            try:
                text_page = page.get_textpage()
                try:
                    content = text_page.get_text_bounded().replace("\r\n", "\n").strip()
                finally:
                    text_page.close()
            finally:
                page.close()
            label = book["optional"].get(number)
            if label is None and OPTIONAL_MARKER.search(content):
                label = "Variante ou opção identificada no texto"
            pages.append({
                "number": number,
                "printed": number - book["offset"] if number > book["offset"] else None,
                "section": section,
                "sectionStart": start,
                "optional": label,
                "text": content,
            })
    print(f"{book['title']}: {len(pages)} páginas, {sum(bool(p['text']) for p in pages)} com texto")
    return {
        "id": book["id"], "title": book["title"], "path": str(source),
        "sha256": digest, "pages": pages,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--britain", required=True, type=Path)
    parser.add_argument("--carpathia", required=True, type=Path)
    args = parser.parse_args()
    try:
        import pypdfium2 as pdf
    except ImportError:
        parser.error("Use um Python com pypdfium2 para importar os PDFs.")
    try:
        books = [import_book(getattr(args, book["id"]).resolve(), book, pdf) for book in BOOKS]
    except (OSError, ValueError, pdf.PdfiumError) as error:
        parser.error(str(error))
    PACK.parent.mkdir(parents=True, exist_ok=True)
    temporary = PACK.with_suffix(".tmp")
    temporary.write_text(json.dumps({"version": 1, "books": books}, ensure_ascii=False), encoding="utf-8")
    temporary.replace(PACK)
    print(PACK)


if __name__ == "__main__":
    main()
