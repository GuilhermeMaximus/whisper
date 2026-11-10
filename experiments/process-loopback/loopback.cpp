#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <audioclient.h>
#include <audioclientactivationparams.h>
#include <mmdeviceapi.h>
#include <mmsystem.h>
#include <wrl.h>
#include <fcntl.h>
#include <io.h>

#include <algorithm>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <numbers>
#include <stdexcept>
#include <string_view>
#include <vector>

using Microsoft::WRL::ComPtr;
using Microsoft::WRL::FtmBase;
using Microsoft::WRL::RuntimeClass;
using Microsoft::WRL::RuntimeClassFlags;

namespace {
constexpr DWORD sampleRate = 16000;

struct Failure {
    const char* operation;
    HRESULT code;
};

void check(HRESULT result, const char* operation) {
    if (FAILED(result)) {
        throw Failure{operation, result};
    }
}

struct Handle {
    explicit Handle(HANDLE handle) : value(handle) {
        if (!value) {
            check(HRESULT_FROM_WIN32(GetLastError()), "Open handle");
        }
    }
    ~Handle() { CloseHandle(value); }
    Handle(const Handle&) = delete;
    Handle& operator=(const Handle&) = delete;
    HANDLE value;
};

struct ComApartment {
    ComApartment() { check(CoInitializeEx(nullptr, COINIT_MULTITHREADED), "CoInitializeEx"); }
    ~ComApartment() { CoUninitialize(); }
};

DWORD wait(const HANDLE* handles, DWORD count, DWORD timeout) {
    const auto result = WaitForMultipleObjects(count, handles, FALSE, timeout);
    if (result == WAIT_FAILED) {
        check(HRESULT_FROM_WIN32(GetLastError()), "WaitForMultipleObjects");
    }
    return result;
}

class Activation final : public RuntimeClass<
    RuntimeClassFlags<Microsoft::WRL::ClassicCom>,
    IActivateAudioInterfaceCompletionHandler, FtmBase> {
public:
    STDMETHODIMP ActivateCompleted(IActivateAudioInterfaceAsyncOperation* operation) noexcept override {
        const auto callResult = operation->GetActivateResult(&result, &audioInterface);
        if (FAILED(callResult)) {
            result = callResult;
        }
        SetEvent(completed.value);
        return S_OK;
    }

    Handle completed{CreateEventW(nullptr, FALSE, FALSE, nullptr)};
    HRESULT result = E_PENDING;
    ComPtr<IUnknown> audioInterface;
};

WAVEFORMATEX pcmFormat() {
    WAVEFORMATEX format{};
    format.wFormatTag = WAVE_FORMAT_PCM;
    format.nChannels = 1;
    format.nSamplesPerSec = sampleRate;
    format.wBitsPerSample = 16;
    format.nBlockAlign = sizeof(std::int16_t);
    format.nAvgBytesPerSec = sampleRate * format.nBlockAlign;
    return format;
}

double phase(unsigned hz, std::uint64_t position) {
    return 2 * std::numbers::pi * hz * (position % sampleRate) / sampleRate;
}

struct ToneLevel {
    unsigned hz;
    double sine = 0;
    double cosine = 0;

    void add(double sample, std::uint64_t position) {
        const auto angle = phase(hz, position);
        sine += sample * std::sin(angle);
        cosine += sample * std::cos(angle);
    }

    double amplitude(std::uint64_t frames) const {
        return frames ? 2 * std::hypot(sine, cosine) / frames : 0;
    }
};

struct Metrics {
    ToneLevel low{440};
    ToneLevel high{880};
    std::uint64_t frames = 0;
    unsigned packets = 0;
    unsigned gaps = 0;
    unsigned timestampErrors = 0;
    double energy = 0;
    std::vector<double> agesMs;
};

struct PacketHeader {
    std::uint32_t frames;
    std::uint32_t flags;
    std::uint64_t qpc100ns;
};
static_assert(sizeof(PacketHeader) == 16);

void writePacket(const PacketHeader& header, const std::vector<std::int16_t>& samples) {
    std::cout.write(reinterpret_cast<const char*>(&header), sizeof(header));
    std::cout.write(reinterpret_cast<const char*>(samples.data()), samples.size() * sizeof(samples[0]));
    if (!std::cout.flush()) {
        throw std::runtime_error("PCM output pipe closed");
    }
}

void collect(IAudioCaptureClient& capture, Metrics& metrics, LONGLONG counterFrequency,
    std::vector<std::int16_t>* pcm) {
    while (true) {
        UINT32 pending = 0;
        check(capture.GetNextPacketSize(&pending), "GetNextPacketSize");
        if (!pending) {
            return;
        }

        BYTE* data = nullptr;
        UINT32 frames = 0;
        DWORD flags = 0;
        UINT64 packetClock = 0;
        check(capture.GetBuffer(&data, &frames, &flags, nullptr, &packetClock), "GetBuffer");
        if (!frames) {
            return;
        }
        LARGE_INTEGER observed{};
        QueryPerformanceCounter(&observed);
        const auto age = (1000.0 * observed.QuadPart / counterFrequency) - packetClock / 10000.0;
        const bool silent = (flags & AUDCLNT_BUFFERFLAGS_SILENT) != 0;
        if (pcm) {
            if (silent) {
                pcm->assign(frames, 0);
            } else {
                const auto* samples = reinterpret_cast<const std::int16_t*>(data);
                pcm->assign(samples, samples + frames);
            }
            check(capture.ReleaseBuffer(frames), "ReleaseBuffer");
            writePacket({frames, flags, packetClock}, *pcm);
            continue;
        }
        if (!silent) {
            const auto* samples = reinterpret_cast<const std::int16_t*>(data);
            for (UINT32 i = 0; i < frames; ++i) {
                const auto sample = samples[i] / 32768.0;
                metrics.energy += sample * sample;
                metrics.low.add(sample, metrics.frames + i);
                metrics.high.add(sample, metrics.frames + i);
            }
        }
        check(capture.ReleaseBuffer(frames), "ReleaseBuffer");
        if (flags & AUDCLNT_BUFFERFLAGS_TIMESTAMP_ERROR) {
            ++metrics.timestampErrors;
        } else {
            metrics.agesMs.push_back(age);
        }
        if (flags & AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY) {
            ++metrics.gaps;
        }
        metrics.frames += frames;
        ++metrics.packets;
    }
}

int captureAudio(IAudioClient& client, DWORD seconds, bool stream, HANDLE target = nullptr, DWORD pid = 0) {
    if (stream && _setmode(_fileno(stdout), _O_BINARY) == -1) {
        throw std::runtime_error("Cannot set binary PCM output mode");
    }
    const Handle ready{CreateEventW(nullptr, FALSE, FALSE, nullptr)};
    const auto format = pcmFormat();
    DWORD flags = AUDCLNT_STREAMFLAGS_EVENTCALLBACK
        | AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM | AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY;
    if (target) {
        flags |= AUDCLNT_STREAMFLAGS_LOOPBACK;
    }
    check(client.Initialize(AUDCLNT_SHAREMODE_SHARED, flags, 0, 0, &format, nullptr), "Initialize");
    check(client.SetEventHandle(ready.value), "SetEventHandle");
    ComPtr<IAudioCaptureClient> capture;
    check(client.GetService(IID_PPV_ARGS(&capture)), "Get capture client");
    UINT32 bufferFrames = 0;
    check(client.GetBufferSize(&bufferFrames), "GetBufferSize");
    std::vector<std::int16_t> pcm;
    if (stream) {
        pcm.reserve(bufferFrames);
    }
    LARGE_INTEGER counterFrequency{};
    QueryPerformanceFrequency(&counterFrequency);
    Metrics metrics;
    check(client.Start(), "Start");
    const auto deadline = GetTickCount64() + seconds * 1000;
    const HANDLE handles[]{target ? target : ready.value, ready.value};
    const DWORD audioIndex = target ? 1 : 0;
    bool targetExited = false;
    auto now = GetTickCount64();
    while (now < deadline) {
        const auto result = wait(handles, audioIndex + 1, static_cast<DWORD>(deadline - now));
        if (target && result == WAIT_OBJECT_0) {
            targetExited = true;
            break;
        }
        if (result == WAIT_OBJECT_0 + audioIndex) {
            collect(*capture.Get(), metrics, counterFrequency.QuadPart, stream ? &pcm : nullptr);
        }
        now = GetTickCount64();
    }
    check(client.Stop(), "Stop");
    if (stream) {
        return targetExited ? 2 : 0;
    }
    std::sort(metrics.agesMs.begin(), metrics.agesMs.end());
    std::cout << "{\"pid\":" << pid << ",\"sampleRate\":" << sampleRate
        << ",\"frames\":" << metrics.frames << ",\"packets\":" << metrics.packets
        << ",\"gaps\":" << metrics.gaps << ",\"timestampErrors\":" << metrics.timestampErrors
        << ",\"rms\":" << (metrics.frames ? std::sqrt(metrics.energy / metrics.frames) : 0)
        << ",\"tone440\":" << metrics.low.amplitude(metrics.frames)
        << ",\"tone880\":" << metrics.high.amplitude(metrics.frames)
        << ",\"packetAgeP95Ms\":";
    if (metrics.agesMs.empty()) {
        std::cout << "null";
    } else {
        std::cout << metrics.agesMs[(95 * metrics.agesMs.size() - 1) / 100];
    }
    std::cout << ",\"targetExited\":" << std::boolalpha << targetExited << "}\n";
    return targetExited ? 2 : 0;
}

int captureProcess(DWORD pid, DWORD seconds, bool stream) {
    const Handle target{OpenProcess(SYNCHRONIZE, FALSE, pid)};
    const ComApartment apartment;
    const auto completion = Microsoft::WRL::Make<Activation>();
    if (!completion) {
        throw Failure{"Allocate activation handler", E_OUTOFMEMORY};
    }
    AUDIOCLIENT_ACTIVATION_PARAMS config{};
    config.ActivationType = AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK;
    config.ProcessLoopbackParams = {pid, PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE};
    PROPVARIANT parameters{};
    parameters.vt = VT_BLOB;
    parameters.blob = {sizeof(config), reinterpret_cast<BYTE*>(&config)};
    ComPtr<IActivateAudioInterfaceAsyncOperation> operation;
    check(ActivateAudioInterfaceAsync(VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK, __uuidof(IAudioClient),
        &parameters, completion.Get(), &operation), "ActivateAudioInterfaceAsync");
    if (wait(&completion->completed.value, 1, 5000) == WAIT_TIMEOUT) {
        throw Failure{"Activate audio client", HRESULT_FROM_WIN32(ERROR_TIMEOUT)};
    }
    check(completion->result, "Activate audio client");
    ComPtr<IAudioClient> client;
    check(completion->audioInterface.As(&client), "Get audio client");
    return captureAudio(*client.Get(), seconds, stream, target.value, pid);
}

int captureMicrophone(DWORD seconds) {
    const ComApartment apartment;
    ComPtr<IMMDeviceEnumerator> devices;
    check(CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_INPROC_SERVER,
        IID_PPV_ARGS(&devices)), "Enumerate audio devices");
    ComPtr<IMMDevice> microphone;
    check(devices->GetDefaultAudioEndpoint(eCapture, eConsole, &microphone), "Find default microphone");
    ComPtr<IAudioClient> client;
    check(microphone->Activate(__uuidof(IAudioClient), CLSCTX_INPROC_SERVER, nullptr, &client), "Activate microphone");
    return captureAudio(*client.Get(), seconds, true);
}

void playChime(unsigned hz, unsigned seconds) {
    std::vector<std::int16_t> samples(sampleRate * seconds);
    constexpr unsigned repeatFrames = sampleRate * 6 / 5;
    constexpr unsigned noteFrames = sampleRate * 3 / 10;
    constexpr unsigned noteOffset = sampleRate * 7 / 20;
    for (std::size_t i = 0; i < samples.size(); ++i) {
        const auto cycle = i % repeatFrames;
        const bool secondNote = cycle >= noteOffset;
        const auto notePosition = secondNote ? cycle - noteOffset : cycle;
        if (notePosition < noteFrames) {
            const auto progress = static_cast<double>(notePosition) / noteFrames;
            const auto envelope = std::sin(std::numbers::pi * progress) * std::exp(-2 * progress);
            const auto frequency = secondNote ? hz * 3 / 2 : hz;
            samples[i] = static_cast<std::int16_t>(1800 * envelope * std::sin(phase(frequency, i)));
        }
    }
    const Handle done{CreateEventW(nullptr, FALSE, FALSE, nullptr)};
    const auto format = pcmFormat();
    HWAVEOUT output = nullptr;
    if (waveOutOpen(&output, WAVE_MAPPER, &format, reinterpret_cast<DWORD_PTR>(done.value), 0,
        CALLBACK_EVENT) != MMSYSERR_NOERROR) {
        throw std::runtime_error("Cannot open default audio output");
    }
    WAVEHDR header{};
    header.lpData = reinterpret_cast<LPSTR>(samples.data());
    header.dwBufferLength = static_cast<DWORD>(samples.size() * sizeof(samples[0]));
    auto result = waveOutPrepareHeader(output, &header, sizeof(header));
    if (result == MMSYSERR_NOERROR) {
        ResetEvent(done.value);
        result = waveOutWrite(output, &header, sizeof(header));
        if (result == MMSYSERR_NOERROR &&
            WaitForSingleObject(done.value, seconds * 1000 + 3000) != WAIT_OBJECT_0) {
            result = MMSYSERR_ERROR;
        }
        waveOutReset(output);
        waveOutUnprepareHeader(output, &header, sizeof(header));
    }
    waveOutClose(output);
    if (result != MMSYSERR_NOERROR) {
        throw std::runtime_error("Cannot play test chime");
    }
}

unsigned number(std::string_view text, unsigned max) {
    unsigned value = 0;
    const auto end = text.data() + text.size();
    const auto [parsed, error] = std::from_chars(text.data(), end, value);
    if (error != std::errc{} || parsed != end || !value || value > max) {
        throw std::invalid_argument("Invalid numeric argument");
    }
    return value;
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 3 && std::string_view(argv[1]) == "mic") {
            return captureMicrophone(number(argv[2], 1800));
        }
        if (argc == 4) {
            const std::string_view command = argv[1];
            if (command == "capture" || command == "stream") {
                return captureProcess(number(argv[2], MAXDWORD), number(argv[3], 1800), command == "stream");
            }
            if (command == "chime") {
                playChime(number(argv[2], 4000), number(argv[3], 30));
                return 0;
            }
        }
        std::cerr << "Usage: audio-capture capture PID SECONDS | audio-capture stream PID SECONDS"
            " | audio-capture mic SECONDS | audio-capture chime HZ SECONDS\n";
    } catch (const Failure& error) {
        std::cerr << error.operation << " failed (HRESULT 0x" << std::hex
            << static_cast<unsigned>(error.code) << ")\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
    }
    return 1;
}
