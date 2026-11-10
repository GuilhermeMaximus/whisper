import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys


BENCH = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Exercise WASAPI and local ASR with synthetic PT-BR speech")
    backend = parser.add_mutually_exclusive_group(required=True)
    backend.add_argument("--asr-worker", type=Path)
    backend.add_argument("--whisper-cli", type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--system", choices=("dnd", "vaesen"), default="dnd")
    parser.add_argument("--lookup", action="store_true", help="Exercise two natural Vaesen requests in one session")
    args = parser.parse_args()
    if args.lookup and args.system != "vaesen":
        parser.error("--lookup requires --system vaesen")
    command = "repeat" if args.asr_worker and not args.lookup else "play"
    expected_segments = 2 if args.asr_worker or args.lookup else 1
    expected_words = ("forçar", "jogada") if args.system == "vaesen" else ("saltar", "telhado")
    expected_card = "forcar" if args.system == "vaesen" else "long-jump"
    fixture = (BENCH / "speak.ps1").read_text(encoding="utf-8")
    encoded_fixture = base64.b64encode(fixture.encode("utf-16-le")).decode("ascii")
    with subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-EncodedCommand", encoded_fixture],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        env={**os.environ, "WHISPER_DEMO_SYSTEM": args.system, "WHISPER_DEMO_MODE": "lookup" if args.lookup else ""},
    ) as speaker:
        try:
            if speaker.stdout.readline().strip() != "READY":
                raise RuntimeError("The Windows speech fixture did not start")
            with subprocess.Popen(
                [
                    sys.executable, str(BENCH / "transcribe.py"), str(speaker.pid), "20",
                    "--asr-worker" if args.asr_worker else "--whisper-cli",
                    str(args.asr_worker or args.whisper_cli), "--model", str(args.model), "--show-text",
                    "--meter", "--cards", "--system", args.system,
                    *(["--contextual"] if args.lookup else []),
                ],
                stdout=subprocess.PIPE,
                text=True,
            ) as bench:
                try:
                    with ThreadPoolExecutor(max_workers=1) as reader:
                        try:
                            def wait_for_level():
                                for line in bench.stdout:
                                    if json.loads(line).get("event") == "level":
                                        return line
                                return ""
                            first = reader.submit(wait_for_level).result(timeout=48)
                        except TimeoutError:
                            bench.kill()
                            raise
                    if not first or json.loads(first).get("event") != "level":
                        raise RuntimeError("The capture did not report its first audio level")
                    speaker.stdin.write(command + "\n")
                    speaker.stdin.flush()
                    output, _ = bench.communicate(timeout=65)
                finally:
                    if bench.poll() is None:
                        bench.terminate()
            results = [json.loads(line) for line in output.splitlines()]
            for result in results:
                if result.get("event") != "level":
                    print(json.dumps(result))
            if args.lookup:
                from rules import normalize_speech
                queries = [normalize_speech(result["lookup"]) for result in results if result.get("lookup")]
                if bench.returncode != 2 or queries != ["classe social", "forcar a jogada"]:
                    raise RuntimeError(f"Expected both Vaesen queries, got {queries}")
                return
            matches = sum(
                all(word in text for word in expected_words)
                for text in (result.get("text", "").casefold() for result in results)
            )
            if bench.returncode != 2 or matches != expected_segments:
                raise RuntimeError(f"Expected {expected_segments} transcribed segments and an explicit target exit")
            cards = [result["card"]["id"] for result in results if "card" in result]
            if cards != [expected_card]:
                raise RuntimeError(f"Expected exactly one {expected_card} card for the session")
        finally:
            if speaker.poll() is None:
                speaker.terminate()


if __name__ == "__main__":
    main()
