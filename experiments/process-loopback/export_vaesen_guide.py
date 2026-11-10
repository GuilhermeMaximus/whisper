"""Gera docs/VAESEN_GUIA_DO_MESTRE.md a partir de desktop-preview/vaesen-guide.json.

O JSON é a fonte única: o app (cartões da Biblioteca), o interpretador local (situação de uso) e este guia
impresso saem dele. Para alterar um texto, edite o JSON e rode este script.

Uso: python experiments/process-loopback/export_vaesen_guide.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "experiments" / "desktop-preview" / "vaesen-guide.json"
OUTPUT = ROOT / "docs" / "VAESEN_GUIA_DO_MESTRE.md"


def anchor(text):
    keep = "".join(c if c.isalnum() or c in " -" else "" for c in text.lower())
    return "-".join(keep.split())


def main():
    guide = json.loads(SOURCE.read_text(encoding="utf-8"))
    groups = sorted(guide["groups"], key=lambda group: group["order"])
    cards = guide["cards"]
    lines = [
        "# Vaesen — Guia rápido da Mestre",
        "",
        "Resumo próprio, em português, dos procedimentos de Vaesen para consulta durante a sessão. "
        "Cada tópico segue o mesmo padrão: **situação**, **números-chave**, **como fazer** e **atenção**. "
        "Os detalhes completos e as tabelas estão nos livros; use este guia para achar a regra e agir rápido.",
        "",
        "> Gerado de `experiments/desktop-preview/vaesen-guide.json` por `experiments/process-loopback/export_vaesen_guide.py`. "
        "Não edite este arquivo: altere o JSON e gere de novo.",
        "",
        "## Índice por situação",
        "",
        "| Situação | Tópico |",
        "| --- | --- |",
    ]
    for group in groups:
        for title, card in cards.items():
            if card["group"] == group["id"]:
                lines.append(f"| {card['when']} | [{title}](#{anchor(title)}) |")
    lines.append("")
    for group in groups:
        lines += [f"## {group['title']}", "", f"_{group['blurb']}_", ""]
        for title, card in cards.items():
            if card["group"] != group["id"]:
                continue
            lines += [f"### {title}", "", f"**Quando:** {card['when']}", ""]
            if card["quick"]:
                lines += ["| Regra-chave | Valor |", "| --- | --- |"]
                lines += [f"| {label} | {value} |" for label, value in card["quick"]]
                lines.append("")
            if card["steps"]:
                lines += ["**Como fazer**", ""]
                lines += [f"{number}. {step}" for number, step in enumerate(card["steps"], 1)]
                lines.append("")
            if card["watch"]:
                lines += ["**Atenção**", ""]
                lines += [f"- {item}" for item in card["watch"]]
                lines.append("")
            if card["related"]:
                lines += ["**Veja também:** " + " · ".join(f"[{name}](#{anchor(name)})" for name in card["related"]), ""]
    OUTPUT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"{len(cards)} tópicos em {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
