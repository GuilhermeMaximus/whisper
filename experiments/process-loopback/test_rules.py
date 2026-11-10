import unittest

from rules import CardPolicy, VaesenSpeech, match_rule, vaesen_lookup
from semantic import MODEL_DIR


class RuleTests(unittest.TestCase):
    def test_vaesen_lookup_requires_an_explicit_request(self):
        for text, expected in (
            ("Consultar a regra opcional de classe social.", "classe social"),
            ("Como funciona a regra opcional de classe social?", "classe social"),
            ("Whisper, quero consultar Caminhos da Vida, por favor.", "caminhos da vida"),
            ("Quero consultar Caminhos da Vida por favor.", "caminhos da vida"),
            ("Qual é a regra de veneno?", "veneno"),
            ("Não quero consultar a regra de classe social.", None),
            ("Como funciona esse personagem?", None),
            ("E se eu consultar a regra de classe social?", None),
            ("Consultar ---", None),
        ):
            with self.subTest(text=text):
                self.assertEqual(vaesen_lookup(text), expected)

    def test_explicit_evidence(self):
        examples = {
            "Eu quero saltar de um telhado para o outro.": "long-jump",
            "Vou tentar pular entre os telhados.": "long-jump",
            "Vou agarrar o goblin!": "grapple",
            "Estou mantendo a concentração e tomei oito pontos de dano.": "concentration",
            "Recebi 8 pontos de dano enquanto mantenho a concentração.": "concentration",
        }
        for text, expected in examples.items():
            with self.subTest(text=text):
                self.assertEqual(match_rule(text)["id"], expected)

    def test_natural_questions_resolve_catalog_topics(self):
        assistant = VaesenSpeech()
        for text, expected in (
            ("Regra pra classe social.", "classe social"),
            ("Regra pra forçar jogada.", "forcar a jogada"),
            ("Gente, como é que funciona a classe social mesmo?", "classe social"),
            ("Posso forçar a jogada?", "forcar a jogada"),
            ("Alguém lembra o ritual da Banshee?", "ritual · banshee"),
            ("Não lembro como funciona forçar o teste.", "forcar a jogada"),
            ("Já vimos a regra de classe social na outra mesa.", None),
            ("Não quero consultar a regra de classe social.", None),
            ("Estou lendo sobre classe social e talentos.", None),
            ("Como está o guarda hoje?", None),
        ):
            with self.subTest(text=text):
                self.assertEqual(assistant.lookup(text, "microphone", 1), expected)

    def test_follow_up_uses_recent_topic_from_the_same_source(self):
        assistant = VaesenSpeech()
        self.assertIsNone(assistant.lookup("Vamos fazer um teste de Medo.", "microphone", 20))
        self.assertEqual(assistant.lookup("E quantos sucessos mesmo?", "microphone", 27), "teste de medo")
        self.assertIsNone(assistant.lookup("E quantos sucessos mesmo?", "discord", 28))
        self.assertEqual(assistant.lookup("E quantos sucessos mesmo?", "microphone", 46), "teste de medo")
        self.assertIsNone(assistant.lookup("E quantos sucessos mesmo?", "microphone", 92))

    def test_remembers_a_creature_and_switches_between_ritual_and_sheet(self):
        assistant = VaesenSpeech()
        self.assertIsNone(assistant.lookup("A Banshee apareceu do outro lado do rio.", "microphone", 0))
        self.assertEqual(assistant.lookup("Qual é o ritual?", "microphone", 3), "ritual · banshee")
        self.assertEqual(assistant.lookup("E a ficha?", "microphone", 5), "ficha de banshee")
        self.assertEqual(assistant.lookup("A Banshee apareceu, alguém lembra do ritual?", "discord", 7), "ritual · banshee")
        self.assertIsNone(assistant.lookup("Qual é o prato favorito do guarda?", "microphone", 9))

    @unittest.skipUnless((MODEL_DIR / "model_quantized.onnx").is_file(), "optional local semantic model unavailable")
    def test_local_semantic_retrieval_handles_rephrased_questions(self):
        assistant = VaesenSpeech(use_semantic=True)
        self.assertIsNotNone(assistant.semantic)
        for index, (text, expected) in enumerate((
            ("Se o teste deu errado, dá para jogar os dados outra vez?", "Forçar a jogada"),
            ("Se o teste deu errado, dá para jogar os dados outra vez.", "Forçar a jogada"),
            ("Meu personagem é nobre. Como funciona se eu conversar com alguém mais pobre?", "Classe social"),
            ("Como eu tiro os estados negativos da minha ficha.", "Tratar Condições"),
            ("Se eu me esconder atrás da porta, isso reduz o estrago de um tiro.", "Armadura e cobertura"),
            ("Qual a previsão do tempo para amanhã?", None),
            ("Quanto custa uma passagem de avião?", None),
            ("Qual é o prato favorito do guarda?", None),
        )):
            with self.subTest(text=text):
                self.assertEqual(assistant.lookup(text, f"test-{index}", 0), expected)

    def test_vaesen_can_infer_rules_from_play(self):
        self.assertEqual(match_rule("Eu falhei no teste, mas vou rolar os dados de novo.", "vaesen")["id"], "forcar")
        self.assertEqual(match_rule("Um vaesen surgiu e eu estou apavorada.", "vaesen")["id"], "medo")
        self.assertIsNone(match_rule("Se um vaesen surgir, vou fazer um teste de medo.", "vaesen"))
        self.assertIsNone(match_rule("Eu falhei no teste, mas não vou rolar os dados de novo.", "vaesen"))

    def test_withholds_on_ambiguous_or_already_resolved_events(self):
        for text in (
            "E se eu saltasse de um telhado para o outro?",
            "Vou agarrar o goblin?",
            "Eu não vou agarrar o goblin.",
            "Vou agarrar a corda.",
            "Vou agarrar o goblin. Melhor fugir.",
            "Já agarrei o goblin.",
            "Tomei oito pontos de dano.",
            "Perdi a concentração e tomei dano.",
            "Estou mantendo a concentração e não tomei dano.",
        ):
            with self.subTest(text=text):
                self.assertIsNone(match_rule(text))

    def test_cooldown_and_hourly_limit(self):
        policy = CardPolicy()
        text = "Vou agarrar o goblin."
        self.assertIsNotNone(policy.suggest(text, 0))
        self.assertIsNone(policy.suggest(text, 89))
        for when in (90, 180, 270):
            self.assertIsNotNone(policy.suggest(text, when))
        self.assertIsNone(policy.suggest(text, 3599))
        self.assertIsNotNone(policy.suggest(text, 3600))

    def test_vaesen_rules_and_system_isolation(self):
        examples = {
            "Eu quero forçar a jogada.": ("forcar", 42),
            "Vamos sacar cartas de iniciativa.": ("iniciativa", 61),
            "Vou esquivar do tiro.": ("esquiva", 65),
            "Vou aparar o golpe.": ("aparar", 65),
            "Vou imobilizar o inimigo.": ("imobilizar", 65),
            "Façam um teste de Medo.": ("medo", 71),
            "Vou tratar minhas condições físicas.": ("curar-fisico", 75),
            "Vou tratar as condições mentais do grupo.": ("curar-mental", 75),
        }
        for text, (expected, page) in examples.items():
            with self.subTest(text=text):
                card = match_rule(text, "vaesen")
                self.assertEqual((card["id"], card["book"], card["page"]), (expected, "core", page))
                self.assertIsNone(match_rule(text, "dnd"))
        for text in (
            "E se eu quiser forçar a jogada?",
            "Não vou forçar a jogada.",
            "Eu quero saltar de um telhado para o outro.",
            "Vou tratar minhas condições mentais.",
        ):
            with self.subTest(text=text):
                self.assertIsNone(match_rule(text, "vaesen"))

if __name__ == "__main__":
    unittest.main()
