from collections import deque
import json
from pathlib import Path
import re
import sys
import unicodedata


INTENT = r"(?:eu )?(?:quero|vou|tento|vou tentar)"
NUMBER_DAMAGE = r"(?:(?:\d+|um|dois|tres|quatro|cinco|seis|sete|oito|nove|dez) pontos? de )?dano"
CONCENTRATING = r"(?:estou mantendo|mantenho) (?:a )?concentracao"
TOOK_DAMAGE = rf"(?:tomei|sofri|recebi) {NUMBER_DAMAGE}"

RULES = (
    (
        rf"{INTENT} (?:saltar|pular) (?:de um telhado (?:para o|pro) outro"
        r"|do telhado (?:para o|pro) outro|entre (?:os )?telhados)",
        {
            "id": "long-jump",
            "title": "Salto horizontal",
            "body": (
                "Com pelo menos 10 pés de movimento imediatamente antes do salto, o alcance em pés "
                "vai até o valor de Força. No salto parado, use metade. A distância gasta movimento."
            ),
            "section": "Long Jump",
            "page": 184,
        },
    ),
    (
        rf"{INTENT} agarrar (?:o|a|um|uma) (?:inimig[oa]|criatura|goblin|orc|bandido|guarda)",
        {
            "id": "grapple",
            "title": "Agarrar",
            "body": (
                "Ao usar a opção Agarrar de um ataque desarmado, confira se há uma mão livre e se o "
                "alvo é no máximo uma categoria de tamanho maior que você. O alvo escolhe entre uma salvaguarda de "
                "Força ou Destreza. A CD é 8 + modificador de Força + bônus de proficiência."
            ),
            "section": "Unarmed Strike · Grapple",
            "page": 190,
        },
    ),
    (
        rf"(?:eu )?(?:{CONCENTRATING} e {TOOK_DAMAGE}|{TOOK_DAMAGE} (?:enquanto|e) {CONCENTRATING})",
        {
            "id": "concentration",
            "title": "Concentração após dano",
            "body": (
                "Se a concentração ainda estava ativa quando você sofreu dano, faça uma salvaguarda de "
                "Constituição para mantê-la. A CD é 10 ou metade do dano arredondada para baixo, "
                "o que for maior, até o máximo de 30."
            ),
            "section": "Concentration · Damage",
            "page": 179,
        },
    ),
)


VAESEN_RULES = (
    (rf"(?:\b{INTENT} forcar (?:a |essa |esta )?(?:jogada|rolagem)\b|"
     r"\bfalhei (?:no teste|na rolagem)\b.{0,50}\b(?:vou|quero) (?:rolar (?:os dados )?de novo|rerrolar)\b)",
     "forcar", "Forçar a jogada", 42, "Forçando a jogada",
     "Force imediatamente, uma vez por ação. Escolha uma Condição física para Físico ou Precisão, "
     "ou mental para Lógica ou Empatia. Mantenha os 6 e rerrole os outros dados. A nova Condição "
     "só entra em efeito depois da rerrolagem."),
    (r"\b(?:vamos|precisamos) (?:sacar|sortear|tirar) (?:as )?cartas de iniciativa\b",
     "iniciativa", "Iniciativa", 61, "Iniciativa e rodadas",
     "Embaralhe as cartas numeradas de 1 a 10. Cada participante saca uma. O menor número age "
     "primeiro. A Mestre pode usar uma só carta para um grupo de oponentes idênticos."),
    (rf"{INTENT} (?:esquivar|me esquivar) (?:do tiro|do ataque a distancia)",
     "esquiva", "Esquivar de um ataque à distância", 65, "Esquivando e aparando",
     "Gaste uma ação rápida e declare a esquiva antes de saber se o ataque acertou. Role Agilidade. "
     "Cada sucesso seu cancela um sucesso do ataque."),
    (rf"{INTENT} aparar (?:o golpe|o ataque corpo a corpo)",
     "aparar", "Aparar em combate corpo a corpo", 65, "Esquivando e aparando",
     "Gaste uma ação rápida antes de saber se o ataque acertou. Use Combate Corpo a Corpo se estiver "
     "armada, ou Força se estiver desarmada. Cada sucesso seu cancela um sucesso do ataque."),
    (rf"{INTENT} (?:agarrar|imobilizar) (?:o|a|um|uma) (?:inimig[oa]|oponente|bandido|guarda)",
     "imobilizar", "Agarrar e imobilizar", 65, "Segurar e imobilizar",
     "Role Força. A outra personagem pode reagir com Força para se libertar. Enquanto estiver contida, "
     "ela só pode tentar se soltar ou gritar."),
    (r"(?:\b(?:faca|facam|vou fazer|vamos fazer) (?:um )?teste de medo\b|"
     r"\b(?:um |o )?vaesen (?:apareceu|surgiu)\b.{0,55}\b(?:assustad[oa]|apavorad[oa]|aterrorizad[oa])\b)",
     "medo", "Teste de Medo", 71, "Medo",
     "Escolha Lógica ou Empatia. O valor de Medo indica os sucessos necessários. Some até três dados "
     "pelas personagens jogadoras presentes, sem contar as Arrasadas ou Aterrorizadas. Em combate, conte apenas na sua zona."),
    (rf"{INTENT} (?:curar|tratar) (?:as|minhas) condicoes fisicas",
     "curar-fisico", "Tratar Condições físicas", 75, "Curando Condições",
     "Reserve um dia inteiro em local seguro com comida, bebida e descanso. Role Medicina. "
     "Um sucesso cura três Condições no total, distribuídas entre as pacientes. Cada sucesso extra cura outras três."),
    (rf"{INTENT} (?:curar|tratar) as condicoes mentais (?:do grupo|dos outros|das outras)",
     "curar-mental", "Tratar Condições mentais", 75, "Curando Condições",
     "Reserve um dia inteiro em local seguro com comida e bebida. Use Inspiração com pessoas dispostas "
     "ao diálogo. Um sucesso cura três Condições no total. Cada sucesso extra cura outras três."),
)


def normalize_speech(text):
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(normalized.split())


def vaesen_lookup(text):
    sentence = normalize_speech(text).rstrip(".?!").removesuffix(" por favor").rstrip(",")
    match = re.fullmatch(
        r"(?:whisper[, ]+)?(?:"
        r"(?:eu )?quero consultar |consultar |consulte |"
        r"(?:a )?regra (?:opcional )?(?:para|pra|pro|de|do|da|sobre) |"
        r"como funciona (?:a )?regra (?:opcional )?(?:de|do|da) |"
        r"qual (?:e )?a regra (?:opcional )?(?:de|do|da) "
        r")([\w -]{3,80})",
        sentence,
    )
    if match and 1 <= len(match[1].split()) <= 8:
        query = re.sub(r"^(?:a )?regra (?:opcional )?(?:de|do|da) ", "", match[1]).strip()
        if len(query) >= 3 and re.search(r"[a-z]", query):
            return query
    return None


QUESTION = re.compile(
    r"^(?:(?:whisper|gente|pera|ta|entao|e)[, ]+){0,3}(?:"
    r"(?:a )?regra(?: opcional)? (?:para|pra|pro|de|da|do|sobre)\b|"
    r"como (?:e que )?(?:(?:eu|a gente|se) )?(?:funciona|faz|faco|rola|rolo|calcula|usa|uso|resolvo|"
    r"tiro|removo|recupero|descubro|sei|vejo|decido|escolho|resisto|me defendo|me livro)\b|"
    r"(?:qual|quais|quanto|quantos|quanta|quantas|o que (?:muda|acontece|eu rolo))\b|"
    r"(?:(?:eu )?(?:posso|preciso|devo)|pode|precisa|devemos)\b|"
    r"(?:alguem (?:lembra|sabe)|me lembra|me explica|eu esqueci|esqueci|(?:eu )?nao lembro|fiquei na duvida)\b)"
)
QUESTION_INSIDE = re.compile(
    r"\b(?:da (?:pra|para)|sera que|tem como|como (?:eu |a gente )?(?:funciona|faco|faz|rola|rolo|calculo|decido)|"
    r"(?:qual|quais) (?:e|sao|o|a|os|as)|quant[oa]s? (?:dados|sucessos|rodadas|acoes)|"
    r"alguem (?:sabe|lembra)|me (?:lembra|explica)|isso (?:reduz|afeta|muda|conta|vale))\b"
)
SHORT_CONTEXT_QUESTION = re.compile(r"^(?:e|entao) (?:o|a|os|as) (?:bonus|penalidade|custo|ritual|ficha|atributos)\b")
REJECT_LOOKUP = re.compile(
    r"\b(?:nao (?:quero|preciso|vou) consultar|nao precisa consultar|e se eu consultar|"
    r"melhor deixar|so estava comentando|estava falando de outra coisa)\b"
)
REJECT_PASSIVE = re.compile(
    r"^(?:se|quando)\b|\b(?:nao|nunca|e se|se eu|se voce|se a gente|caso|talvez|melhor|em vez disso|"
    r"desisti|pensei|queria ter|ja (?:fiz|rolei|resolvi|passei|falhei))\b"
)
FOLLOW_UP = re.compile(
    r"\b(?:quant[oa]s? (?:dados|sucessos|rodadas|acoes)|(?:posso|pode|da pra|da para) (?:rolar|rerrolar|repetir)|"
    r"qual (?:e )?(?:o |a )?(?:meu |minha )?(?:custo|dificuldade|bonus|penalidade|vantagem)|"
    r"o que (?:eu |a gente )?(?:ganho|perco|rolo)|nesse caso|nessa situacao|e se|isso|de novo|tambem)\b"
    r"|^(?:e |entao )?(?:contra|com|sem|por)\b"
)
UPGRADE_CONTEXT = re.compile(r"\b(?:sede|melhorias?|instalacao|recrut\w*|contrat\w*|desenvolvimento|pre requisito)\b")
RITUAL_INTENT = re.compile(r"\b(?:ritual|banimento|banir|expulsar?|afastar?)\b")
SHEET_INTENT = re.compile(r"\b(?:ficha|atributos|estatisticas)\b")
TOPIC_MEMORY_SECONDS = 45
CONNECTORS = frozenset("a o as os de da do das dos em na no para pra pro".split())


def topic_words(text):
    return tuple(word for word in re.findall(r"[a-z0-9]+", normalize_speech(text)) if word not in CONNECTORS)


def read_vaesen_catalog():
    directory = Path(__file__).resolve().parents[1] / "desktop-preview"
    guide_path = directory / "vaesen-guide.json"
    guide = json.loads(guide_path.read_text(encoding="utf-8")) if guide_path.is_file() else {}
    cards = guide.get("cards", {})
    groups = {group["id"]: group["title"] for group in guide.get("groups", [])}
    catalog = []
    for name in ("vaesen-topics.json", "vaesen-entries.json"):
        for topic in json.loads((directory / name).read_text(encoding="utf-8")):
            card = cards.get(topic["title"])
            if card:
                # O guia traz a situação de uso ("when") em linguagem de mesa: ajuda a busca e o interpretador local.
                topic = {**topic, "when": card["when"], "group": groups.get(card["group"])}
            catalog.append(topic)
    return catalog


class VaesenSpeech:
    """Resolve natural speech to the local catalog without sending the full transcript to the UI."""

    def __init__(self, catalog=None, use_semantic=False):
        if catalog is None:
            catalog = read_vaesen_catalog()
        self.names = {}
        self.upgrades = set()
        for topic in catalog:
            title = normalize_speech(topic["title"])
            if topic.get("category") == "Melhorias da sede":
                self.upgrades.add(title)
            for name in (topic["title"], *topic["aliases"]):
                words = topic_words(name)
                if words:
                    self.names.setdefault(words, {})[title] = normalize_speech(name)
        self.longest = max(map(len, self.names), default=0)
        self.recent = {}
        self.previous = {}
        self.semantic = None
        if use_semantic:
            from semantic import load_semantic_catalog
            try:
                self.semantic = load_semantic_catalog(catalog)
            except Exception as error:
                print(f"Local semantic search unavailable: {error}", file=sys.stderr, flush=True)

    def remember(self, topic, source, speech_end):
        self.recent[source] = (topic, speech_end)

    def creature_focus(self, title, sentence):
        words = topic_words(title)
        if not words or words[0] not in {"ficha", "ritual"}:
            return title
        scope = "ritual" if RITUAL_INTENT.search(sentence) else "ficha" if SHEET_INTENT.search(sentence) else words[0]
        matches = self.names.get((scope, *words[1:]), {})
        return next(iter(matches)) if len(matches) == 1 else title

    def named_topics(self, words, allow_short_upgrades):
        strongest = 0
        topics = {}
        for start in range(len(words)):
            for length in range(min(self.longest, len(words) - start), max(1, strongest) - 1, -1):
                matches = self.names.get(words[start:start + length])
                if matches and length == 1 and not allow_short_upgrades:
                    matches = {title: alias for title, alias in matches.items() if title not in self.upgrades}
                if matches:
                    if length > strongest:
                        topics.clear()
                        strongest = length
                    topics.update(matches)
                    break
        return topics

    def lookup(self, text, source, speech_end):
        sentence = normalize_speech(text)
        if not sentence or REJECT_LOOKUP.search(sentence):
            return None
        words = topic_words(sentence)
        explicit = vaesen_lookup(text)
        short_question = SHORT_CONTEXT_QUESTION.match(sentence)
        asking = bool(explicit or "?" in sentence or QUESTION.match(sentence) or QUESTION_INSIDE.search(sentence) or short_question)
        names = self.named_topics(words, bool(explicit or len(words) == 1 or UPGRADE_CONTEXT.search(sentence)))
        previous = self.previous.get(source)
        self.previous[source] = (text[-350:], speech_end)
        if len(names) == 1:
            (name,) = names
            if asking:
                name = self.creature_focus(name, sentence)
            if not REJECT_PASSIVE.search(sentence) or asking:
                self.remember(name, source, speech_end)
            return name if asking else None
        if not asking:
            return None
        if names:
            aliases = set(names.values())
            return next(iter(aliases)) if len(aliases) == 1 else None

        continuation = short_question or FOLLOW_UP.search(sentence) or RITUAL_INTENT.search(sentence) or SHEET_INTENT.search(sentence)
        recent = self.recent.get(source)
        if continuation and len(words) <= 7 and recent and 0 <= speech_end - recent[1] <= TOPIC_MEMORY_SECONDS:
            topic = self.creature_focus(recent[0], sentence)
            self.remember(topic, source, speech_end)
            return topic

        candidate = self.semantic.lookup(text) if self.semantic and len(words) >= 3 else None
        if not candidate and continuation and self.semantic and previous and 0 <= speech_end - previous[1] <= 12:
            candidate = self.semantic.lookup(f"{previous[0]} {text}")
        if candidate:
            self.remember(candidate, source, speech_end)
            return candidate
        return explicit


def match_rule(text, system="dnd"):
    normalized = normalize_speech(text).rstrip(".!")
    if system == "vaesen":
        if "?" in normalized or REJECT_PASSIVE.search(normalized):
            return None
        matches = [
            {"id": rule_id, "title": title, "page": page, "section": section, "body": body, "book": "core"}
            for pattern, rule_id, title, page, section, body in VAESEN_RULES
            if re.search(r"(?<!\w)(?:" + pattern + r")(?!\w)", normalized)
        ]
    else:
        matches = [card for pattern, card in RULES if re.fullmatch(pattern, normalized)]
    return matches[0] if len(matches) == 1 else None


class CardPolicy:
    def __init__(self, system="dnd"):
        self.system = system
        self.emitted = deque()

    def suggest(self, text, speech_end_seconds):
        while self.emitted and speech_end_seconds - self.emitted[0] >= 3600:
            self.emitted.popleft()
        if len(self.emitted) >= 4 or self.emitted and speech_end_seconds - self.emitted[-1] < 90:
            return None
        card = match_rule(text, self.system)
        if card is not None:
            self.emitted.append(speech_end_seconds)
        return card
