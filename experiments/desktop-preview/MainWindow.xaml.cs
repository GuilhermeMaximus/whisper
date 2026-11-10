using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Navigation;

namespace Whisper.Preview;

public partial class MainWindow : Window
{
    private const string RuleSource = "https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf";
    private const int VoiceTestSeconds = 120;
    private enum CaptureMode { Synthetic, Microphone, Discord }
    private CancellationTokenSource? session;
    private string? cardBook;
    private int cardPage;
    private string? cardQuery;
    private VaesenCatalog? catalog;
    private ReferenceToast? referenceToast;
    private string? lastNotification;
    private long lastNotificationTime;

    public MainWindow()
    {
        InitializeComponent();
        DarkTitleBar.Apply(this);
        SystemPicker.SelectedIndex = File.Exists(PackPath()) ? 0 : 1;
    }

    private async void StartDemo(object sender, RoutedEventArgs args) => await StartSession(CaptureMode.Synthetic);

    private async void StartVoiceTest(object sender, RoutedEventArgs args) => await StartSession(CaptureMode.Microphone);

    private async void StartLive(object sender, RoutedEventArgs args)
    {
        if (!int.TryParse(PidInput.Text.Trim(), out int pid) || pid <= 0 || !IsDiscord(pid))
        {
            Status.Text = "Fonte indisponível";
            Detail.Text = "Informe o PID de um processo do Discord desktop.";
            return;
        }
        if (Consent.IsChecked != true)
        {
            Status.Text = "Consentimento pendente";
            Detail.Text = "Confirme o consentimento de todos antes de iniciar o ensaio.";
            return;
        }
        await StartSession(CaptureMode.Discord, pid);
    }

    private static bool IsDiscord(int pid)
    {
        try
        {
            using Process candidate = Process.GetProcessById(pid);
            return string.Equals(candidate.ProcessName, "Discord", StringComparison.OrdinalIgnoreCase);
        }
        catch (Exception ex) when (ex is ArgumentException or InvalidOperationException or Win32Exception)
        {
            return false;
        }
    }

    private async Task StartSession(CaptureMode mode, int? pid = null)
    {
        if (session is not null)
        {
            return;
        }
        using var lifetime = new CancellationTokenSource();
        session = lifetime;
        CancellationToken cancellation = lifetime.Token;
        SetRunning(true);
        Status.Text = "Preparando";
        Detail.Text = mode switch
        {
            CaptureMode.Microphone => "Carregando o modelo local e preparando o microfone.",
            CaptureMode.Synthetic => "Preparando a voz sintética do Windows.",
            _ => "Abrindo a fonte selecionada.",
        };
        if (mode == CaptureMode.Synthetic)
        {
            ShowExample();
        }
        else
        {
            ClearCard();
        }
        if (mode == CaptureMode.Microphone)
        {
            VoiceTestText.Text = "Aguardando sua fala…";
            VoiceLookupStatus.Text = "";
            VoiceTestPanel.Visibility = Visibility.Visible;
        }
        try
        {
            string bench = FindBench();
            string system = (SystemPicker.SelectedItem as ComboBoxItem)?.Tag as string ?? "dnd";
            if (system == "vaesen" && !File.Exists(PackPath()))
            {
                throw new InvalidOperationException("Importe os três PDFs de Vaesen antes de começar.");
            }
            string build = Path.Combine(bench, "build");
            string model = Path.Combine(build, "asr", "ggml-small-q5_1.bin");
            if (!File.Exists(model))
            {
                model = Path.Combine(build, "asr", "ggml-base-q5_1.bin");
            }
            string worker = Path.Combine(build, "asr", "runtime", "Release", "asr-worker.exe");
            if (!File.Exists(Path.Combine(build, "audio-capture.exe")) || !File.Exists(model) || !File.Exists(worker))
            {
                throw new InvalidOperationException("Prepare o executável da bancada e o modelo local conforme o README da prévia.");
            }

            if (mode != CaptureMode.Synthetic)
            {
                await Capture(bench, pid, worker, model, system, null, cancellation);
            }
            else
            {
                await RunDemo(bench, worker, model, system, cancellation);
            }
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested)
        {
            Status.Text = "Escuta encerrada";
            Detail.Text = "A captura foi interrompida.";
        }
        catch (Exception ex) when (ex is IOException or InvalidOperationException or Win32Exception or JsonException)
        {
            Status.Text = "Ensaio interrompido";
            Detail.Text = ex is Win32Exception ? "Não foi possível iniciar uma dependência local. Confira o Python e a bancada." : ex.Message;
        }
        finally
        {
            session = null;
            VoiceTestText.Text = "";
            VoiceTestPanel.Visibility = Visibility.Collapsed;
            if (mode == CaptureMode.Discord)
            {
                ClearCard();
            }
            SetRunning(false);
        }
    }

    private async Task RunDemo(string bench, string recognizer, string model, string system, CancellationToken cancellation)
    {
        string fixture = await File.ReadAllTextAsync(Path.Combine(bench, "speak.ps1"), cancellation);
        string command = Convert.ToBase64String(Encoding.Unicode.GetBytes(fixture));
        var options = LocalProcess("powershell.exe", "-NoProfile", "-EncodedCommand", command);
        options.RedirectStandardInput = true;
        options.Environment["WHISPER_DEMO_SYSTEM"] = system;
        options.Environment["WHISPER_DEMO_MODE"] = system == "vaesen" ? "lookup" : "";
        using Process speaker = Start(options);
        using var stopSpeaker = cancellation.Register(() => Kill(speaker));
        _ = speaker.StandardError.ReadToEndAsync();
        try
        {
            string? line = await speaker.StandardOutput.ReadLineAsync(cancellation).AsTask().WaitAsync(TimeSpan.FromSeconds(15), cancellation);
            if (line != "READY")
            {
                throw new InvalidOperationException("Não foi possível preparar a voz PT-BR instalada no Windows.");
            }
            await Capture(bench, speaker.Id, recognizer, model, system, speaker, cancellation);
        }
        catch (TimeoutException)
        {
            throw new InvalidOperationException("A voz sintética não ficou pronta a tempo.");
        }
        finally
        {
            Kill(speaker);
        }
    }

    private async Task Capture(string bench, int? pid, string recognizer, string model, string system, Process? speaker, CancellationToken cancellation)
    {
        bool demo = speaker is not null;
        bool voiceTest = pid is null;
        bool includeMicrophone = !demo && !voiceTest && IncludeMicrophone.IsChecked == true;
        int seconds = voiceTest ? VoiceTestSeconds : demo ? 15 : 1800;
        var contextModel = (ComboBoxItem)ContextModelPicker.SelectedItem;
        string contextModelLabel = (string)contextModel.Content;
        var options = LocalProcess(
            "python.exe", Path.Combine(bench, "transcribe.py"), pid?.ToString() ?? "mic", seconds.ToString(),
            "--asr-worker", recognizer, "--model", model, "--threads", Math.Min(Environment.ProcessorCount, 3).ToString(),
            "--meter", "--cards", "--system", system);
        if (system == "vaesen")
        {
            options.ArgumentList.Add("--contextual");
            options.ArgumentList.Add("--context-model");
            options.ArgumentList.Add((string)contextModel.Tag);
        }
        if (includeMicrophone)
        {
            options.ArgumentList.Add("--microphone");
        }
        if (voiceTest)
        {
            options.ArgumentList.Add("--show-text");
        }
        MicrophoneStatus.Text = voiceTest || includeMicrophone ? "Microfone padrão do Windows · aguardando entrada" :
            "Microfone padrão do Windows · desligado";
        using Process worker = Start(options);
        using var stopWorker = cancellation.Register(() => Kill(worker));
        _ = worker.StandardError.ReadToEndAsync();
        try
        {
            Status.Text = voiceTest ? "Abrindo microfone" : demo ? "Ensaio em andamento" : "Capturando Discord";
            Detail.Text = system == "vaesen" ? $"Carregando o modelo de voz e o {contextModelLabel}." :
                "Aguardando áudio da fonte selecionada.";
            bool receivedLevel = false;
            bool matched = false;
            bool transcribed = false;
            bool microphoneFailed = false;
            string? contextNotice = null;
            string contextEngineLabel = contextModelLabel;
            long latestSpeech = 0;
            while (await worker.StandardOutput.ReadLineAsync(cancellation) is string line)
            {
                using JsonDocument json = JsonDocument.Parse(line);
                JsonElement message = json.RootElement;
                bool isMicrophone = message.TryGetProperty("source", out JsonElement source) && source.GetString() == "microphone";
                switch (message.GetProperty("event").GetString())
                {
                    case "lookup-ready":
                        contextNotice = message.GetProperty("contextual").GetBoolean() ? null :
                            message.GetProperty("fallback").GetBoolean() ? $"{contextModelLabel} indisponível · busca anterior ativa" :
                            $"{contextModelLabel} indisponível · confira o arquivo do modelo e a memória disponível";
                        if (contextNotice is null)
                        {
                            string backend = message.GetProperty("backend").GetString() == "vulkan" ? "GPU (Vulkan)" : "CPU";
                            contextEngineLabel = $"{contextModelLabel} · {backend}";
                        }
                        if (voiceTest)
                        {
                            VoiceLookupStatus.Text = contextNotice ?? $"{contextEngineLabel} · conectado ao catálogo";
                        }
                        break;
                    case "level":
                        double level = Math.Clamp(Math.Sqrt(message.GetProperty("rms").GetDouble()) * 2.8, 0, 1);
                        if (isMicrophone)
                        {
                            MicrophoneMeter.Value = level;
                            MicrophoneStatus.Text = "Microfone padrão do Windows · ativo";
                            if (voiceTest && !receivedLevel)
                            {
                                Status.Text = "Teste de voz ativo";
                                Detail.Text = "Pode falar. Faça uma pausa entre as frases para ver o que o Whisper entendeu.";
                                receivedLevel = true;
                            }
                            break;
                        }
                        Meter.Value = level;
                        if (!receivedLevel)
                        {
                            if (speaker is not null)
                            {
                                await speaker.StandardInput.WriteLineAsync("play");
                                await speaker.StandardInput.FlushAsync(cancellation);
                            }
                            Detail.Text = contextNotice ?? (demo ? "O medidor mostra o áudio da voz sintética." :
                                "Fonte ativa. A transcrição permanece no computador.");
                            receivedLevel = true;
                        }
                        break;
                    case "source-error" when isMicrophone:
                        microphoneFailed = true;
                        MicrophoneMeter.Value = 0;
                        MicrophoneStatus.Text = "Microfone indisponível · confira a entrada e as permissões do Windows";
                        break;
                    case "transcription" when message.GetProperty("hasText").GetBoolean():
                        transcribed = true;
                        if (voiceTest)
                        {
                            latestSpeech = message.GetProperty("speechEndQpc100ns").GetInt64();
                            VoiceTestText.Text = message.GetProperty("text").GetString();
                            VoiceLookupStatus.Text = message.TryGetProperty("contextPending", out _)
                                ? $"{contextEngineLabel} · consultando o catálogo…" : contextNotice ?? "Nenhum tópico associado a este trecho";
                        }
                        double elapsed = message.GetProperty("fromSpeechEndMs").GetDouble();
                        Detail.Text = $"{(isMicrophone ? "Microfone" : "Discord")} · trecho transcrito em {elapsed / 1000:0.00} s.";
                        if (message.TryGetProperty("card", out JsonElement card))
                        {
                            matched = true;
                            ShowCard(
                                demo || voiceTest ? "DETECTADO NO ENSAIO" : "LEMBRETE DA SESSÃO",
                                card.GetProperty("title").GetString()!,
                                card.GetProperty("body").GetString()!,
                                card.GetProperty("section").GetString()!,
                                card.GetProperty("page").GetInt32(),
                                card.TryGetProperty("book", out JsonElement book) ? book.GetString() : null);
                            if (voiceTest)
                            {
                                VoiceLookupStatus.Text = $"Lembrete · {CardTitle.Text}";
                            }
                        }
                        else if (message.TryGetProperty("lookup", out JsonElement lookup) && lookup.GetString() is string query)
                        {
                            bool found = ShowLookup(query);
                            matched |= found;
                            if (voiceTest)
                            {
                                VoiceLookupStatus.Text = found ? $"Consulta · {CardTitle.Text}" : "Nenhum tópico associado a este trecho";
                            }
                        }
                        break;
                    case "context-result":
                        bool foundContext = message.TryGetProperty("lookup", out JsonElement reference) &&
                            reference.GetString() is string title && ShowLookup(title);
                        matched |= foundContext;
                        if (voiceTest && message.GetProperty("speechEndQpc100ns").GetInt64() == latestSpeech)
                        {
                            VoiceLookupStatus.Text = foundContext ? $"Referência encontrada · {CardTitle.Text}" :
                                message.TryGetProperty("error", out _) ? "Falha ao consultar o modelo local" :
                                message.TryGetProperty("stale", out _) ? "Consulta atrasada · tente de novo" :
                                "Nenhuma referência indicada para este trecho";
                        }
                        break;
                    case "transcription" when voiceTest:
                        Detail.Text = "O microfone recebeu áudio. Nenhuma fala foi reconhecida nesse trecho.";
                        break;
                }
            }
            await worker.WaitForExitAsync(cancellation);
            cancellation.ThrowIfCancellationRequested();
            if (voiceTest && microphoneFailed)
            {
                Status.Text = "Microfone indisponível";
                Detail.Text = "Confira a entrada padrão e o acesso de aplicativos da área de trabalho ao microfone no Windows.";
                return;
            }
            if (worker.ExitCode is not (0 or 2))
            {
                throw new InvalidOperationException("A captura ou a transcrição falhou. Confira a fonte e os arquivos locais da bancada.");
            }
            Status.Text = voiceTest ? "Teste de voz concluído" : demo ? "Ensaio concluído" :
                worker.ExitCode == 2 ? "Fonte encerrada" : "Captura encerrada";
            if (voiceTest)
            {
                Detail.Text = transcribed ? "O Whisper transcreveu sua voz durante o teste." :
                    "Nenhuma fala foi reconhecida. Confira se o medidor responde quando você fala.";
            }
            else if (demo && !matched)
            {
                Detail.Text = "A frase do ensaio não foi reconhecida por completo. Confira a saída de áudio e tente de novo.";
            }
            else if (!demo && worker.ExitCode == 2)
            {
                Detail.Text = "O processo selecionado saiu. Confira o novo PID antes de retomar.";
            }
        }
        finally
        {
            Kill(worker);
        }
    }

    private static string FindBench()
    {
        for (var current = new DirectoryInfo(AppContext.BaseDirectory); current is not null; current = current.Parent)
        {
            string candidate = Path.Combine(current.FullName, "experiments", "process-loopback");
            if (File.Exists(Path.Combine(candidate, "transcribe.py")))
            {
                return candidate;
            }
        }
        throw new InvalidOperationException("Abra a prévia a partir do repositório Whisper.");
    }

    private static ProcessStartInfo LocalProcess(string executable, params string[] arguments)
    {
        var options = new ProcessStartInfo(executable)
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8,
        };
        foreach (string argument in arguments)
        {
            options.ArgumentList.Add(argument);
        }
        return options;
    }

    private static Process Start(ProcessStartInfo options) =>
        Process.Start(options) ?? throw new InvalidOperationException("Não foi possível iniciar a bancada.");

    private static void Kill(Process process)
    {
        try
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }
        }
        catch (Exception ex) when (ex is InvalidOperationException or Win32Exception)
        {
            // The process can exit between the status check and the kill.
        }
    }

    private void SetRunning(bool running)
    {
        VoiceTestButton.IsEnabled = DemoButton.IsEnabled = LiveButton.IsEnabled = PidInput.IsEnabled = Consent.IsEnabled = !running;
        IncludeMicrophone.IsEnabled = !running;
        SystemPicker.IsEnabled = ContextModelPicker.IsEnabled = !running;
        StopButton.IsEnabled = running;
        if (!running)
        {
            Meter.Value = 0;
            MicrophoneMeter.Value = 0;
            if (!MicrophoneStatus.Text.StartsWith("Microfone indisponível", StringComparison.Ordinal))
            {
                UpdateMicrophoneSelection();
            }
            Consent.IsChecked = false;
        }
    }

    private void Stop(object sender, RoutedEventArgs args) => session?.Cancel();

    private void DismissCard(object sender, RoutedEventArgs args) => ClearCard();

    private void ClearCard()
    {
        cardQuery = null;
        CardPanel.Visibility = Visibility.Collapsed;
        referenceToast?.Close();
    }

    private void SystemChanged(object sender, SelectionChangedEventArgs args)
    {
        if (IsInitialized)
        {
            Consent.IsChecked = false;
            ShowExample();
        }
    }

    private void ShowExample()
    {
        if ((SystemPicker.SelectedItem as ComboBoxItem)?.Tag as string == "vaesen")
        {
            ContextModelPanel.Visibility = Visibility.Visible;
            ShowCard("EXEMPLO DE CONSULTA", "Classe social",
                "O ensaio demonstra como consultar uma regra opcional durante a escuta.",
                "Classe social", 14, "britain", notify: false);
        }
        else
        {
            ContextModelPanel.Visibility = Visibility.Collapsed;
            ShowCard("EXEMPLO DE CARTÃO", "Salto horizontal",
                "Confira a distância do salto e o movimento disponível antes de resolver a ação.",
                "Long Jump", 184, notify: false);
        }
    }

    private void ShowCard(string state, string title, string body, string section, int page, string? book = null, bool notify = true)
    {
        cardQuery = null;
        cardBook = book;
        cardPage = page;
        CardState.Text = $"{state}  ·  {(book is null ? "D&D 5e (2024)" : "VAESEN")}";
        CardTitle.Text = title;
        CardBody.Text = body;
        string source = book switch
        {
            "britain" => "Mythic Britain & Ireland",
            "carpathia" => "Mythic Carpathia (beta)",
            null => "SRD 5.2.1",
            _ => "Livro de Regras",
        };
        SourceLabel.Text = $"{source} · {section}";
        CardSource.NavigateUri = new Uri(book is null ? $"{RuleSource}#page={page}" : "about:blank");
        CardPanel.Visibility = Visibility.Visible;
        if (notify) NotifyCard();
    }

    private bool ShowLookup(string query)
    {
        try
        {
            VaesenCatalog source = GetCatalog();
            var exact = source.FindExact(query);
            if (exact.Length == 1)
            {
                var topic = exact[0].Topic;
                var page = exact[0].Page;
                ShowCard(topic.Kind?.ToUpperInvariant() ?? "CONSULTA DE REGRA", topic.Title,
                    topic.Summary ?? "Abra a página de referência para conferir a regra e suas exceções.",
                    page.Page.Section, page.Page.Number, page.Book.Id, notify: false);
                SourceLabel.Text = $"{page.Book.Title} · p. {page.Page.Printed ?? page.Page.Number}";
                NotifyCard();
                return true;
            }
            int count = exact.Length > 1 ? exact.Length : source.Search(query).Length;
            if (count == 0)
            {
                ClearCard();
                Detail.Text = "Não encontrei uma referência para essa consulta.";
                return false;
            }
            ShowCard("BUSCA NO CATÁLOGO", "Consulta de Vaesen",
                exact.Length > 1
                    ? $"{count} tópicos correspondem à consulta. Confira qual regra se aplica à sua mesa."
                    : $"{count} {(count == 1 ? "tópico encontrado" : "tópicos encontrados")} na biblioteca.",
                "Resultados da biblioteca", 0, "vaesen", notify: false);
            SourceLabel.Text = "Abrir resultados da biblioteca";
            cardQuery = query;
            NotifyCard();
            return true;
        }
        catch (Exception ex) when (ex is IOException or InvalidDataException or JsonException or InvalidOperationException)
        {
            ClearCard();
            Detail.Text = "Não foi possível consultar o índice local de Vaesen.";
            return false;
        }
    }

    private void ResetConsent(object sender, System.Windows.Controls.TextChangedEventArgs args)
    {
        if (Consent is not null)
        {
            Consent.IsChecked = false;
        }
    }

    private void MicrophoneChanged(object sender, RoutedEventArgs args)
    {
        if (Consent is not null)
        {
            Consent.IsChecked = false;
            UpdateMicrophoneSelection();
        }
    }

    private void UpdateMicrophoneSelection() =>
        MicrophoneStatus.Text = IncludeMicrophone.IsChecked == true
            ? "Microfone padrão do Windows · selecionado para a próxima captura"
            : "Microfone padrão do Windows · desligado";

    protected override void OnClosed(EventArgs args)
    {
        session?.Cancel();
        referenceToast?.Close();
        base.OnClosed(args);
    }

    private void NotifyCard(bool preview = false)
    {
        string title = CardTitle.Text;
        string body = CardBody.Text;
        string source = SourceLabel.Text;
        string? book = cardBook;
        int page = cardPage;
        string? query = cardQuery;
        Uri link = CardSource.NavigateUri;
        string key = $"{book}|{page}|{query}|{title}|{body}";
        long now = Environment.TickCount64;
        if (!preview && key == lastNotification && now - lastNotificationTime < 20_000) return;
        if (!preview)
        {
            lastNotification = key;
            lastNotificationTime = now;
        }
        referenceToast?.Close();
        var notification = new ReferenceToast(this, title, body, source, () =>
        {
            if (query is not null) ShowLibrary(query: query);
            else if (book is not null) ShowLibrary(book, page, topicTitle: title);
            else OpenExternalReference(link);
        });
        referenceToast = notification;
        notification.Closed += (_, _) =>
        {
            if (ReferenceEquals(referenceToast, notification)) referenceToast = null;
        };
        notification.Show();
    }

    private void TestNotification(object sender, RoutedEventArgs args)
    {
        if (CardPanel.Visibility != Visibility.Visible) ShowExample();
        NotifyCard(preview: true);
    }

    private void OpenSource(object sender, RequestNavigateEventArgs args)
    {
        args.Handled = true;
        if (cardQuery is not null)
        {
            ShowLibrary(query: cardQuery);
            return;
        }
        if (cardBook is not null)
        {
            ShowLibrary(cardBook, cardPage, topicTitle: CardTitle.Text);
            return;
        }
        OpenExternalReference(args.Uri);
    }

    private void OpenExternalReference(Uri link)
    {
        try
        {
            Process.Start(new ProcessStartInfo(link.AbsoluteUri) { UseShellExecute = true });
        }
        catch (Win32Exception)
        {
            Detail.Text = "Não foi possível abrir a referência no navegador.";
        }
    }

    private static string PackPath() => Path.Combine(FindBench(), "local-rules", "vaesen.json");

    private VaesenCatalog GetCatalog() => catalog ??= new VaesenCatalog(PackPath());

    private void OpenLibrary(object sender, RoutedEventArgs args) => ShowLibrary();

    private void ShowLibrary(string? book = null, int? page = null, string? query = null, string? topicTitle = null)
    {
        try
        {
            var library = new VaesenLibrary(GetCatalog(), book, page, query, topicTitle) { Owner = this };
            library.Show();
            if (WindowState == WindowState.Minimized) WindowState = WindowState.Normal;
            library.Activate();
        }
        catch (Exception ex) when (ex is IOException or InvalidDataException or JsonException or InvalidOperationException)
        {
            Detail.Text = "Biblioteca indisponível. Importe os PDFs de Vaesen conforme as instruções do README.";
        }
    }
}
