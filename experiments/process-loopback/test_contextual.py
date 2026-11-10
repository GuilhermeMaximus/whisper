from contextlib import nullcontext
from pathlib import Path
import time
from unittest import TestCase
from unittest.mock import Mock, patch

from contextual import ContextualCatalog, SELECT_PROMPT, local_chat
from rules import read_vaesen_catalog
from transcribe import QPC_PER_SECOND, context_dispatch, run


class ContextualTests(TestCase):
    def test_context_interprets_omitted_subject_and_selects_a_catalog_reference(self):
        chat = Mock()

        def complete(prompt, data, fields, tokens):
            self.assertEqual(prompt, SELECT_PROMPT)
            if not data["falas_anteriores"]:
                return {"id": 0}
            self.assertEqual(data["falas_anteriores"], ["Ela nasceu numa família nobre."])
            choice = next(item for item in data["referencias"] if item["titulo"] == "Classe social")
            self.assertEqual((choice["livro"], choice["pagina"]), ("britain", 14))
            return {"id": choice["id"]}

        chat.complete.side_effect = complete
        lookup = ContextualCatalog(chat, read_vaesen_catalog())
        self.assertIsNone(lookup.lookup("Ela nasceu numa família nobre.", "microphone", 0))
        self.assertIsNone(lookup.lookup("E qual o bônus?", "discord", 4))
        self.assertEqual(lookup.lookup("E qual o bônus?", "microphone", 4), "Classe social")

    def test_rejects_a_reference_outside_the_catalog_results(self):
        chat = Mock()
        chat.complete.return_value = {"id": 999}
        lookup = ContextualCatalog(chat, read_vaesen_catalog())
        self.assertIsNone(lookup.lookup("Quais são os atributos da Banshee?", "microphone", 0))
        self.assertEqual(lookup.selected, {})

    def test_rephrased_question_uses_one_inference_with_a_short_result(self):
        chat = Mock()
        chat.complete.side_effect = lambda prompt, data, fields, tokens: {"id": next(
            item["id"] for item in data["referencias"] if item["titulo"] == "Iniciativa e rodadas")}
        semantic = Mock()
        semantic.rank.return_value = [("Iniciativa e rodadas", 0.92)]
        lookup = ContextualCatalog(chat, read_vaesen_catalog(), semantic)
        self.assertEqual(lookup.lookup("Como eu descubro quem joga primeiro?", "microphone", 0), "Iniciativa e rodadas")
        chat.complete.assert_called_once()
        self.assertEqual(chat.complete.call_args.args[-1], 16)

    def test_explicit_lookup_uses_the_catalog_without_inference(self):
        chat = Mock()
        lookup = ContextualCatalog(chat, read_vaesen_catalog())
        self.assertEqual(lookup.lookup("Consultar classe social.", "microphone", 0), "Classe social")
        chat.complete.assert_not_called()

    def test_gpu_startup_failure_uses_the_limited_cpu_runtime(self):
        cpu = Mock(backend="cpu")
        with patch("contextual.Path.is_file", return_value=True), \
                patch("contextual.start_chat", side_effect=[RuntimeError("GPU unavailable"), nullcontext(cpu)]) as start:
            with local_chat(Path("context-test"), model_name="deepseek") as selected:
                self.assertIs(selected, cpu)
        self.assertEqual([call.args[-1] for call in start.call_args_list], ["vulkan", "cpu"])

    def test_creature_scope_uses_earlier_mention_and_current_request_type(self):
        chat = Mock()
        lookup = ContextualCatalog(chat, read_vaesen_catalog())
        history = ["A Banshee apareceu perto do rio."]
        self.assertIsNone(lookup.lookup(history[0], "microphone", 0))
        chat.complete.assert_not_called()
        self.assertEqual(lookup.creature_scope("Como a gente se livra dela?", history)[0], "Ritual · Banshee")
        self.assertEqual(lookup.creature_scope("E os atributos dela?", history)[0], "Ficha de Banshee")

    def test_context_lookup_returns_a_separate_event(self):
        assistant = Mock()
        assistant.lookup.return_value = "Forçar a jogada"
        timestamp = int(time.perf_counter() * QPC_PER_SECOND)
        with patch("transcribe.emit") as emit:
            with context_dispatch(assistant) as submit:
                submit("Dá para tentar de novo?", "microphone", timestamp)
        emit.assert_called_once_with({"event": "context-result", "source": "microphone",
                                      "speechEndQpc100ns": timestamp, "lookup": "Forçar a jogada"})

    def test_explicit_deepseek_selection_does_not_substitute_another_rule_engine(self):
        recognize = Mock()
        with patch("transcribe.local_chat", return_value=nullcontext(None)) as server, \
                patch("transcribe.capture_session", return_value=0) as capture, patch("transcribe.emit") as emit:
            run(None, 120, recognize, True, True, True, "vaesen", use_context=True, context_model="deepseek")

        server.assert_called_once_with(model_name="deepseek")
        capture.assert_called_once_with(None, 120, recognize, True, True, False, "vaesen", False, None, None)
        emit.assert_called_once_with({"event": "lookup-ready", "contextual": False, "fallback": False,
                                     "semantic": False, "backend": None})
