import json
import struct
import subprocess
import time


from transcribe import EXE


def start_chime(frequency, seconds):
    return subprocess.Popen(
        [str(EXE), "chime", str(frequency), str(seconds)],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def capture(pid, seconds, expected_exit=0):
    result = subprocess.run(
        [str(EXE), "capture", str(pid), str(seconds)],
        capture_output=True,
        text=True,
        timeout=seconds + 8,
    )
    if result.returncode != expected_exit:
        raise RuntimeError(f"Capture exited with {result.returncode}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def verify_isolation(result, expected, excluded):
    if result["frames"] < 32000 or result["targetExited"]:
        raise RuntimeError(f"Incomplete capture: {result}")
    if result[expected] < 0.001 or result[excluded] > result[expected] / 20:
        raise RuntimeError(f"Audio was silent or not isolated: {result}")
    if result["packetAgeP95Ms"] is None:
        raise RuntimeError(f"No valid WASAPI timestamps: {result}")


def verify_stream(pid):
    result = subprocess.run(
        [str(EXE), "stream", str(pid), "3"],
        capture_output=True,
        check=True,
        timeout=11,
    )
    header = struct.Struct("<IIQ")
    offset = 0
    total_frames = 0
    last_timestamp = 0
    peaks = []
    while offset < len(result.stdout):
        frames, flags, timestamp = header.unpack_from(result.stdout, offset)
        offset += header.size
        end = offset + frames * 2
        if not frames or end > len(result.stdout):
            raise RuntimeError("Invalid PCM packet size")
        if not flags & 4:  # AUDCLNT_BUFFERFLAGS_TIMESTAMP_ERROR
            if timestamp <= last_timestamp:
                raise RuntimeError("Non-monotonic PCM timestamp")
            last_timestamp = timestamp
        peaks.append(max(abs(sample) for (sample,) in struct.iter_unpack("<h", result.stdout[offset:end])))
        total_frames += frames
        offset = end
    if total_frames < 32000 or not last_timestamp:
        raise RuntimeError("Incomplete PCM stream")
    if max(peaks) < 100 or sum(peak < 16 for peak in peaks) < len(peaks) / 5:
        raise RuntimeError("Expected audible notes separated by quiet packets")
    print(f"PCM stream passed with {total_frames} frames and quiet intervals.", flush=True)


def main():
    if not EXE.is_file():
        raise SystemExit("Run build.cmd first.")
    with start_chime(440, 8) as low, start_chime(880, 17) as high:
        try:
            time.sleep(0.6)
            if low.poll() is not None or high.poll() is not None:
                raise RuntimeError("A chime process exited before capture. Check the audio output.")
            result = capture(low.pid, 3)
            verify_isolation(result, "tone440", "tone880")
            print(json.dumps(result), flush=True)

            result = capture(low.pid, 7, expected_exit=2)
            if not result["targetExited"] or result["frames"] == 0:
                raise RuntimeError(f"Target exit not detected during active capture: {result}")
            print(json.dumps(result), flush=True)

            result = capture(high.pid, 3)
            verify_isolation(result, "tone880", "tone440")
            print(json.dumps(result), flush=True)
            verify_stream(high.pid)
        finally:
            for chime in (low, high):
                if chime.poll() is None:
                    chime.terminate()
    print("Process isolation and explicit reattachment passed.")


if __name__ == "__main__":
    main()
