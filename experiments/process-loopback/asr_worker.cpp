#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <fcntl.h>
#include <io.h>

#include <ggml-backend.h>
#include <whisper.h>

#include <bit>
#include <charconv>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {
template <typename Function>
Function import(HMODULE module, const char* name) {
    const auto address = GetProcAddress(module, name);
    if (!address) {
        throw std::runtime_error(std::string("Missing runtime symbol: ") + name);
    }
    return std::bit_cast<Function>(address);
}

HMODULE load(const std::filesystem::path& path) {
    const auto module = LoadLibraryExW(path.c_str(), nullptr,
        LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    if (!module) {
        throw std::runtime_error("Cannot load whisper.cpp runtime DLLs next to asr-worker.exe");
    }
    return module;
}

void send(std::string_view text) {
    const auto size = static_cast<std::uint32_t>(text.size());
    std::cout.write(reinterpret_cast<const char*>(&size), sizeof(size));
    std::cout.write(text.data(), text.size());
    if (!std::cout.flush()) {
        throw std::runtime_error("ASR output pipe closed");
    }
}

bool readFrames(std::vector<std::int16_t>& samples) {
    std::uint32_t frames = 0;
    std::cin.read(reinterpret_cast<char*>(&frames), sizeof(frames));
    if (std::cin.eof() && std::cin.gcount() == 0) {
        return false;
    }
    if (!std::cin || frames == 0 || frames > WHISPER_SAMPLE_RATE * 10) {
        throw std::runtime_error("Invalid ASR frame count");
    }
    samples.resize(frames);
    if (!std::cin.read(reinterpret_cast<char*>(samples.data()), frames * sizeof(samples[0]))) {
        throw std::runtime_error("Truncated ASR input");
    }
    return true;
}

void run(const std::filesystem::path& directory, const std::filesystem::path& model, int threads, bool vaesen) {
    const auto ggml = load(directory / L"ggml.dll");
    const auto whisper = load(directory / L"whisper.dll");
    auto loadBackends = import<decltype(&ggml_backend_load_all_from_path)>(ggml, "ggml_backend_load_all_from_path");
    auto contextDefaults = import<decltype(&whisper_context_default_params)>(whisper, "whisper_context_default_params");
    auto init = import<decltype(&whisper_init_from_file_with_params)>(whisper, "whisper_init_from_file_with_params");
    auto freeContext = import<decltype(&whisper_free)>(whisper, "whisper_free");
    auto defaults = import<decltype(&whisper_full_default_params)>(whisper, "whisper_full_default_params");
    auto recognize = import<decltype(&whisper_full)>(whisper, "whisper_full");
    auto segmentCount = import<decltype(&whisper_full_n_segments)>(whisper, "whisper_full_n_segments");
    auto segmentText = import<decltype(&whisper_full_get_segment_text)>(whisper, "whisper_full_get_segment_text");

    loadBackends(directory.string().c_str());
    auto contextOptions = contextDefaults();
    contextOptions.use_gpu = false;
    std::unique_ptr<whisper_context, decltype(freeContext)> context(init(model.string().c_str(), contextOptions), freeContext);
    if (!context) {
        throw std::runtime_error("Cannot initialize local ASR model");
    }

    auto options = defaults(WHISPER_SAMPLING_BEAM_SEARCH);
    options.language = "pt";
    options.n_threads = threads;
    options.no_context = true;
    options.no_timestamps = true;
    options.print_progress = false;
    options.print_realtime = false;
    options.print_timestamps = false;
    if (vaesen) {
        options.initial_prompt = reinterpret_cast<const char*>(
            u8"Vaesen, Banshee, Baba Yaga, Empatia, condições, perícias, arquétipos e rituais.");
    }

    send("");
    std::vector<std::int16_t> samples;
    std::vector<float> audio;
    while (readFrames(samples)) {
        audio.assign(samples.begin(), samples.end());
        for (float& sample : audio) {
            sample /= 32768.0f;
        }
        if (recognize(context.get(), options, audio.data(), static_cast<int>(audio.size())) != 0) {
            throw std::runtime_error("Local ASR inference failed");
        }
        std::string text;
        for (int i = 0; i < segmentCount(context.get()); ++i) {
            text += segmentText(context.get(), i);
        }
        send(text);
    }
}
}  // namespace

int main(int argc, char** argv) {
    try {
        int threads = 0;
        if (argc != 3 && (argc != 4 || std::string_view(argv[3]) != "vaesen")) {
            throw std::invalid_argument("Usage: asr-worker MODEL THREADS [vaesen]");
        }
        const std::string_view argument = argv[2];
        const auto end = argument.data() + argument.size();
        const auto [parsed, error] = std::from_chars(argument.data(), end, threads);
        if (error != std::errc{} || parsed != end || threads < 1) {
            throw std::invalid_argument("THREADS must be a positive integer");
        }
        if (_setmode(_fileno(stdin), _O_BINARY) == -1 || _setmode(_fileno(stdout), _O_BINARY) == -1) {
            throw std::runtime_error("Cannot configure binary ASR pipes");
        }
        run(std::filesystem::absolute(argv[0]).parent_path(), argv[1], threads, argc == 4);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
