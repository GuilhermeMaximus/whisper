from array import array
from contextlib import nullcontext
from io import BytesIO
import time
from unittest import TestCase, main
from unittest.mock import Mock, patch

from transcribe import HEADER, QPC_PER_SECOND, PendingSegments, Segment, run, segments


class AudioSourceTests(TestCase):
    def test_microphone_has_its_own_meter_and_segments(self):
        frames = 160
        pcm = BytesIO()
        for index in range(65):
            samples = array("h", [1000 if index < 25 else 0]) * frames
            pcm.write(HEADER.pack(frames, 0, 1_000_000 + index * 100_000))
            pcm.write(samples.tobytes())
        pcm.seek(0)

        with patch("transcribe.emit") as emit:
            captured = list(segments(pcm, show_meter=True, source="microphone"))

        self.assertEqual([segment.source for segment in captured], ["microphone"])
        meter = [call.args[0] for call in emit.call_args_list]
        self.assertTrue(any(event["rms"] > 0 for event in meter))
        self.assertTrue(all(event["source"] == "microphone" for event in meter))

    def test_busy_discord_does_not_replace_pending_microphone(self):
        pending = PendingSegments(per_source=1)
        first = Segment(b"old", 10, 1)
        microphone = Segment(b"mic", 11, 1, "microphone")
        newest = Segment(b"new", 12, 2)
        self.assertFalse(pending.offer(first))
        self.assertFalse(pending.offer(microphone))
        self.assertTrue(pending.offer(newest))
        self.assertEqual(pending.take(), microphone)
        self.assertEqual(pending.take(), newest)
        self.assertTrue(pending.empty())

    def test_quiet_speech_with_a_mid_sentence_pause_stays_together(self):
        pcm = BytesIO()
        for index, amplitude in enumerate([125] * 24 + [0] * 45 + [125] * 20 + [0] * 65):
            pcm.write(HEADER.pack(160, 0, (index + 1) * 100_000))
            pcm.write((array("h", [amplitude, -amplitude]) * 80).tobytes())
        pcm.seek(0)

        (utterance,) = list(segments(pcm, source="microphone"))

        self.assertEqual(utterance.speech_end, 9_000_000)
        self.assertGreater(max(array("h", utterance.pcm)), 125)

    def test_microphone_only_transcribes_and_looks_up_a_rule(self):
        pcm = BytesIO()
        start = int(time.perf_counter() * QPC_PER_SECOND) - 65 * 100_000
        for index in range(65):
            samples = array("h", [1000 if index < 25 else 0]) * 160
            pcm.write(HEADER.pack(160, 0, start + index * 100_000))
            pcm.write(samples.tobytes())
        pcm.seek(0)
        capture = Mock(stdout=pcm)
        capture.wait.return_value = 0
        recognize = Mock(return_value="Alguém lembra como funciona a classe social?")

        with patch("transcribe.capture_process", return_value=nullcontext(capture)) as launch, \
                patch("transcribe.emit") as emit, patch("semantic.load_semantic_catalog", return_value=None):
            code = run(None, 120, recognize, True, True, True, "vaesen")

        self.assertEqual(code, 0)
        launch.assert_called_once_with("mic", "120")
        events = [call.args[0] for call in emit.call_args_list]
        result = next(event for event in events if event["event"] == "transcription")
        self.assertEqual(result["source"], "microphone")
        self.assertEqual(result["text"], recognize.return_value)
        self.assertEqual(result["lookup"], "classe social")

    def test_microphone_only_reports_unavailable_source(self):
        capture = Mock(stdout=BytesIO())
        capture.wait.return_value = 1
        with patch("transcribe.capture_process", return_value=nullcontext(capture)), patch("transcribe.emit") as emit, \
                patch("semantic.load_semantic_catalog", return_value=None):
            code = run(None, 120, Mock(), False, True, True, "vaesen")

        self.assertEqual(code, 1)
        emit.assert_any_call({"event": "source-error", "source": "microphone"})


if __name__ == "__main__":
    main()
