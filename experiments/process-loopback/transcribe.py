import argparse
from array import array
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from http.client import HTTPException
from io import BytesIO
import json
import math
from pathlib import Path
import struct
import subprocess
from threading import Condition, Lock, Thread
import time
import wave

from contextual import MODELS, contextual_catalog, local_chat
from rules import CardPolicy, VaesenSpeech, read_vaesen_catalog


EXE = Path(__file__).resolve().parent / "build" / "audio-capture.exe"
HEADER = struct.Struct("<IIQ")
SAMPLE_RATE = 16000
QPC_PER_SECOND = 10_000_000
END_PAUSE_FRAMES = SAMPLE_RATE * 60 // 100
MAX_UTTERANCE_FRAMES = SAMPLE_RATE * 9
MIN_VOICE_FRAMES = SAMPLE_RATE * 12 // 100
OUTPUT_LOCK = Lock()
CONTEXT_ERRORS = (OSError, HTTPException, ValueError, RuntimeError, KeyError, TypeError)


@dataclass(frozen=True)
class Segment:
    pcm: bytes
    speech_end: int
    queued_at: float
    source: str = "discord"


class PendingSegments:
    """Keep recent segments in order with a separate bound for each source."""

    def __init__(self, per_source=3):
        self.available = Condition()
        self.by_source = {}
        self.per_source = per_source

    def offer(self, segment):
        with self.available:
            queue = self.by_source.setdefault(segment.source, deque(maxlen=self.per_source))
            replaced = len(queue) == self.per_source
            queue.append(segment)
            self.available.notify()
            return replaced

    def take(self):
        with self.available:
            if not self.available.wait_for(lambda: self.by_source, timeout=0.1):
                return None
            source = min(self.by_source, key=lambda key: self.by_source[key][0].queued_at)
            queue = self.by_source[source]
            segment = queue.popleft()
            if not queue:
                del self.by_source[source]
            return segment

    def discard(self, source):
        with self.available:
            self.by_source.pop(source, None)

    def empty(self):
        with self.available:
            return not self.by_source


def emit(event):
    with OUTPUT_LOCK:
        print(json.dumps(event), flush=True)


def normalize_pcm(pcm):
    samples = array("h", pcm)
    peak = max(map(abs, samples))
    if not peak:
        return bytes(pcm)
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    gain = min(4.0, 2600 / rms, 30000 / peak)
    return array("h", (round(sample * gain) for sample in samples)).tobytes() if gain > 1.1 else bytes(pcm)


def segments(pipe, show_meter=False, source="discord"):
    pre_roll = deque()
    pre_roll_frames = 0
    audio = bytearray()
    active_frames = quiet_frames = speech_end = last_timestamp = 0
    last_meter = 0
    peak_level = 0
    noise_floor = 55.0
    while header := pipe.read(HEADER.size):
        if len(header) != HEADER.size:
            raise ValueError("Truncated PCM header")
        frames, flags, timestamp = HEADER.unpack(header)
        if not 0 < frames <= SAMPLE_RATE:
            raise ValueError("Invalid PCM packet size")
        pcm = pipe.read(frames * 2)
        if len(pcm) != frames * 2:
            raise ValueError("Truncated PCM packet")

        # Do not assemble an utterance across a gap or an invalid clock reading.
        if flags & 5 or timestamp <= last_timestamp:
            audio.clear()
            pre_roll.clear()
            pre_roll_frames = active_frames = quiet_frames = speech_end = 0
            if flags & 4 or timestamp <= last_timestamp:
                last_timestamp = 0
                continue
        last_timestamp = timestamp
        samples = array("h", pcm)
        rms = math.sqrt(sum(sample * sample for sample in samples) / frames)
        loud = rms >= max(95.0, noise_floor * (1.25 if audio else 1.75))
        if not loud and not audio:
            noise_floor = noise_floor * 0.97 + rms * 0.03
        if show_meter:
            peak_level = max(peak_level, rms / 32768)
            if timestamp - last_meter >= QPC_PER_SECOND // 10:
                emit({"event": "level", "source": source, "rms": round(peak_level, 5)})
                last_meter = timestamp
                peak_level = 0

        if not audio and not loud:
            pre_roll.append((frames, pcm))
            pre_roll_frames += frames
            while pre_roll_frames > SAMPLE_RATE * 32 // 100:
                pre_roll_frames -= pre_roll.popleft()[0]
            continue
        if not audio:
            audio.extend(b"".join(chunk for _, chunk in pre_roll))
            pre_roll.clear()
            pre_roll_frames = 0
        audio.extend(pcm)
        if loud:
            active_frames += frames
            quiet_frames = 0
            speech_end = timestamp + frames * QPC_PER_SECOND // SAMPLE_RATE
        else:
            quiet_frames += frames

        if quiet_frames >= END_PAUSE_FRAMES or len(audio) >= 2 * MAX_UTTERANCE_FRAMES:
            if active_frames >= MIN_VOICE_FRAMES:
                yield Segment(normalize_pcm(audio), speech_end, time.perf_counter(), source)
            audio.clear()
            active_frames = quiet_frames = speech_end = 0
    if active_frames >= MIN_VOICE_FRAMES:
        yield Segment(normalize_pcm(audio), speech_end, time.perf_counter(), source)


def read_capture(pipe, pending, show_meter, source="discord"):
    return sum(pending.offer(segment) for segment in segments(pipe, show_meter, source))


@contextmanager
def capture_process(*arguments):
    with subprocess.Popen(
        [str(EXE), *arguments], stdout=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    ) as capture:
        try:
            yield capture
        finally:
            stop_capture(capture)


def stop_capture(capture):
    if capture.poll() is None:
        capture.terminate()


def read_microphone(capture, pending, show_meter, primary):
    dropped = 0
    try:
        dropped = read_capture(capture.stdout, pending, show_meter, "microphone")
        failed = capture.wait(timeout=2) != 0
    except (OSError, ValueError, subprocess.TimeoutExpired):
        failed = True
        stop_capture(capture)
    if failed and not primary.done():
        pending.discard("microphone")
        emit({"event": "source-error", "source": "microphone"})
    return dropped


def recognize(segment, cli, model, threads):
    wav = BytesIO()
    with wave.open(wav, "wb") as writer:
        writer.setparams((1, 2, SAMPLE_RATE, 0, "NONE", "not compressed"))
        writer.writeframes(segment.pcm)
    # In v1.9.2, a "-" output basename disables the normal segment callback.
    # Use a named basename without any file output formats to keep text on the pipe.
    result = subprocess.run(
        [
            str(cli), "-m", str(model), "-f", "-", "-l", "pt", "-t", str(threads),
            "-ng", "-nt", "-np", "-of", "segment",
        ],
        input=wav.getvalue(),
        capture_output=True,
        timeout=10,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout.decode("utf-8").strip()


def worker_reply(worker):
    header = worker.stdout.read(4)
    if len(header) != 4:
        raise RuntimeError("Local ASR worker closed its output")
    (length,) = struct.unpack("<I", header)
    if length > 1_048_576:
        raise RuntimeError("Invalid ASR response size")
    payload = worker.stdout.read(length)
    if len(payload) != length:
        raise RuntimeError("Truncated ASR response")
    return payload.decode("utf-8").strip()


@contextmanager
def resident_recognizer(executable, model, threads, system=None):
    arguments = [str(executable), str(model), str(threads)]
    if system == "vaesen":
        arguments.append(system)
    with subprocess.Popen(
        arguments,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS,
    ) as worker, ThreadPoolExecutor(max_workers=1) as io:
        def request(segment):
            worker.stdin.write(struct.pack("<I", len(segment.pcm) // 2))
            worker.stdin.write(segment.pcm)
            worker.stdin.flush()
            return worker_reply(worker)

        try:
            if io.submit(worker_reply, worker).result(timeout=10):
                raise RuntimeError("Unexpected ASR readiness response")
            yield lambda segment: io.submit(request, segment).result(timeout=15)
            worker.stdin.close()
            if worker.wait(timeout=2):
                raise RuntimeError("Local ASR worker did not exit cleanly")
        finally:
            if worker.poll() is None:
                worker.kill()


@contextmanager
def context_dispatch(assistant):
    ready = Condition()
    queue = deque(maxlen=6)
    closed = False

    def submit(text, source, speech_end):
        with ready:
            queue.append((text, source, speech_end))
            ready.notify()

    def resolve():
        while True:
            with ready:
                ready.wait_for(lambda: queue or closed)
                if not queue:
                    return
                text, source, speech_end = queue.popleft()
            result = {"event": "context-result", "source": source, "speechEndQpc100ns": speech_end}
            try:
                if time.perf_counter() - speech_end / QPC_PER_SECOND <= 30:
                    result["lookup"] = assistant.lookup(text, source, speech_end / QPC_PER_SECOND)
                else:
                    result["stale"] = True
            except CONTEXT_ERRORS:
                result["error"] = True
            emit(result)

    worker = Thread(target=resolve, name="context-lookup", daemon=True)
    worker.start()
    try:
        yield submit
    finally:
        with ready:
            closed = True
            ready.notify()
        worker.join()


def run(pid, seconds, transcribe, show_text, show_meter, show_cards, system, include_microphone=False,
        use_context=False, context_model="qwen"):
    with ExitStack() as services:
        vaesen = None
        submit_context = None
        backend = None
        allow_cards = show_cards
        if show_cards and system == "vaesen":
            if use_context:
                try:
                    chat = services.enter_context(local_chat(model_name=context_model))
                    if chat:
                        assistant = contextual_catalog(chat, read_vaesen_catalog())
                        submit_context = services.enter_context(context_dispatch(assistant))
                        backend = chat.backend
                except CONTEXT_ERRORS:
                    pass
            if submit_context is None:
                if use_context and context_model == "deepseek":
                    allow_cards = False
                else:
                    vaesen = VaesenSpeech(use_semantic=True)
            emit({"event": "lookup-ready", "contextual": submit_context is not None,
                  "fallback": vaesen is not None,
                  "semantic": vaesen is not None and vaesen.semantic is not None, "backend": backend})
        return capture_session(pid, seconds, transcribe, show_text, show_meter, allow_cards, system,
                               include_microphone, vaesen, submit_context)


def capture_session(pid, seconds, transcribe, show_text, show_meter, show_cards, system, include_microphone, vaesen, submit_context):
    pending = PendingSegments()
    policy = CardPolicy(system) if show_cards and submit_context is None else None
    stale = 0
    microphone_only = pid is None
    secondary_microphone = include_microphone and not microphone_only
    primary_source = "microphone" if microphone_only else "discord"
    arguments = ("mic", str(seconds)) if microphone_only else ("stream", str(pid), str(seconds))
    with ThreadPoolExecutor(max_workers=2 if secondary_microphone else 1) as executor, ExitStack() as streams:
        capture = streams.enter_context(capture_process(*arguments))
        reader = executor.submit(read_capture, capture.stdout, pending, show_meter, primary_source)
        microphone = microphone_reader = None
        if secondary_microphone:
            try:
                microphone = streams.enter_context(capture_process("mic", str(seconds)))
                microphone_reader = executor.submit(read_microphone, microphone, pending, show_meter, reader)
                reader.add_done_callback(lambda _: stop_capture(microphone))
            except OSError:
                emit({"event": "source-error", "source": "microphone"})

        while True:
            segment = pending.take()
            if segment is None:
                if reader.done() and (microphone_reader is None or microphone_reader.done()) and pending.empty():
                    break
                continue
            follows_discord = secondary_microphone and segment.source == "microphone"
            if follows_discord and reader.done():
                continue

            started = time.perf_counter()
            if started - segment.queued_at > 5:
                stale += 1
                continue
            text = transcribe(segment)
            finished = time.perf_counter()
            if finished - segment.speech_end / QPC_PER_SECOND > 12 or (follows_discord and reader.done()):
                stale += 1
                continue
            result = {
                "event": "transcription",
                "source": segment.source,
                "speechEndQpc100ns": segment.speech_end,
                "inferenceMs": round((finished - started) * 1000, 1),
                "fromSpeechEndMs": round((finished - segment.speech_end / QPC_PER_SECOND) * 1000, 1),
                "hasText": bool(text),
            }
            if show_text:
                result["text"] = text
            if submit_context and text:
                result["contextPending"] = True
            if policy is not None:
                lookup = vaesen.lookup(text, segment.source, segment.speech_end / QPC_PER_SECOND) if vaesen else None
                if lookup is not None:
                    result["lookup"] = lookup
                else:
                    card = policy.suggest(text, segment.speech_end / QPC_PER_SECOND)
                    if card is not None:
                        result["card"] = card
                        if vaesen:
                            vaesen.remember(card["title"], segment.source, segment.speech_end / QPC_PER_SECOND)
            emit(result)
            if submit_context and text:
                submit_context(text, segment.source, segment.speech_end)
        dropped = reader.result() + (microphone_reader.result() if microphone_reader is not None else 0)
        code = capture.wait(timeout=5)
    if microphone_only and code:
        emit({"event": "source-error", "source": "microphone"})
    emit({"event": "summary", "dropped": dropped, "stale": stale, "captureExit": code})
    return code


def capture_pid(value):
    if value == "mic":
        return None
    try:
        pid = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("expected a PID or 'mic'") from None
    if pid <= 0:
        raise argparse.ArgumentTypeError("PID must be positive")
    return pid


def main():
    parser = argparse.ArgumentParser(description="Local incremental PT-BR transcription bench")
    parser.add_argument("pid", metavar="PID|mic", type=capture_pid)
    parser.add_argument("seconds", type=int)
    backend = parser.add_mutually_exclusive_group(required=True)
    backend.add_argument("--asr-worker", type=Path)
    backend.add_argument("--whisper-cli", type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--threads", default=4, type=int)
    parser.add_argument("--show-text", action="store_true", help="Print text from authorized test material")
    parser.add_argument("--meter", action="store_true", help="Emit local audio level events")
    parser.add_argument("--cards", action="store_true", help="Emit matched rule cards")
    parser.add_argument("--contextual", action="store_true", help="Use the local contextual model and separate lookup events")
    parser.add_argument("--context-model", choices=MODELS, default="qwen", help="Local model used with --contextual")
    parser.add_argument("--system", choices=("dnd", "vaesen"), default="dnd")
    parser.add_argument("--microphone", action="store_true", help="Also capture the default Windows input")
    args = parser.parse_args()
    if args.pid is None and args.microphone:
        parser.error("'mic' already uses the microphone as its only source")
    for dependency in (EXE, args.asr_worker or args.whisper_cli, args.model):
        if not dependency.is_file():
            parser.error(f"File not found: {dependency}")
    if args.threads < 1:
        parser.error("--threads must be positive")
    model = args.model.resolve()
    if args.asr_worker:
        with resident_recognizer(args.asr_worker.resolve(), model, args.threads, args.system) as transcribe:
            return run(args.pid, args.seconds, transcribe, args.show_text, args.meter, args.cards, args.system,
                       args.microphone, use_context=args.contextual, context_model=args.context_model)
    cli = args.whisper_cli.resolve()
    return run(
        args.pid, args.seconds, lambda segment: recognize(segment, cli, model, args.threads),
        args.show_text, args.meter, args.cards, args.system, args.microphone,
        use_context=args.contextual, context_model=args.context_model,
    )


if __name__ == "__main__":
    raise SystemExit(main())
