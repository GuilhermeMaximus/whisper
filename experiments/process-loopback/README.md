# Fase 0 — Loopback por processo

Bancada Windows 11 x64 para verificar o recorte do WASAPI por PID e observar falhas de origem. A captura solicita PCM mono de 16 kHz. O comando `capture` calcula métricas em memória e imprime um objeto JSON ao parar. O comando `stream` entrega pacotes PCM a um consumidor local pela saída padrão. A bancada não grava áudio.

## Compilar e testar

Requer Visual Studio Build Tools com C++ e Windows SDK. O teste automatizado também usa Python 3, apenas com a biblioteca padrão, e uma saída de áudio ativa. Ele reproduz pares de notas suaves, com volume baixo e pausas. No **x64 Native Tools Command Prompt**, a partir da raiz do repositório, rode:

```cmd
experiments\process-loopback\build.cmd
python experiments\process-loopback\smoke.py
```

Os dois sinais usam notas iniciais de 440 Hz e 880 Hz em processos separados. O teste captura o primeiro PID enquanto os dois tocam, observa o encerramento do alvo e valida a captura com o segundo PID. Em cada verificação de isolamento, a amplitude na frequência excluída deve ficar em até 5% da amplitude na frequência selecionada. O teste também verifica o fluxo PCM, os timestamps e a presença de pausas entre as notas.

## Ensaio no Discord

Em uma chamada privada de teste com os participantes informados e de acordo, identifique o PID raiz do Discord no Gerenciador de Tarefas. No PowerShell, substitua o PID de exemplo:

```powershell
.\experiments\process-loopback\build\audio-capture.exe capture 12345 30
```

Use um segundo aplicativo para reproduzir um tom distinto durante o ensaio. Repita com o Discord reiniciado e confirme o novo PID antes de capturar de novo. O código de saída é 0 ao completar o intervalo, 2 quando o processo alvo sai durante a captura e 1 em caso de erro.

`frames` mede amostras mono entregues, `gaps` conta descontinuidades sinalizadas pelo WASAPI e `timestampErrors` indica pacotes sem timestamp confiável. `packetAgeP95Ms` mede o tempo entre o timestamp do primeiro frame do pacote e a leitura do buffer. É uma métrica da captura, anterior à transcrição. As amplitudes `tone440` e `tone880` servem para ensaios com esses sinais conhecidos.

## Fluxo PCM para o transcritor

Iniciar `audio-capture.exe stream PID SEGUNDOS` para a saída do Discord ou `audio-capture.exe mic SEGUNDOS` para a entrada padrão do Windows. Cada fonte usa um processo e um pipe binário separados. Cada pacote contém um cabeçalho little-endian de 16 bytes no formato `<IIQ`, seguido de `frames × 2` bytes de PCM mono de 16 kHz e 16 bits com sinal.

- O primeiro `uint32` contém o número de frames.
- O segundo `uint32` contém os flags WASAPI. O bit 0 sinaliza descontinuidade, o bit 1 indica silêncio com amostras zeradas e o bit 2 indica timestamp inválido.
- O `uint64` contém o timestamp QPC em unidades de 100 ns do primeiro frame. Ignorar esse valor quando o bit 2 estiver ativo.

Consumir a saída continuamente. A escrita da bancada é síncrona, então um consumidor lento pode atrasar a captura. Na integração com ASR, a leitura do pipe deve ficar separada da inferência, com fila limitada e descarte de áudio vencido.

## Transcrição local em PT-BR

A ponte `transcribe.py` lê cada pipe numa thread dedicada. O limiar de energia acompanha o ruído de fundo em pausas. Cerca de 600 ms de silêncio delimitam trechos de até aproximadamente 9 s. Trechos com volume baixo recebem ganho antes da inferência. A fila mantém até três trechos pendentes por fonte e entrega os mais antigos primeiro. O worker recebe PCM por stdin e devolve texto UTF-8 por stdout. Ele carrega o modelo antes da captura e o mantém em memória até encerrar a sessão. Use `--show-text` para inspecionar texto de teste.

Obtenha o ZIP Windows x64 do whisper.cpp **v1.9.2** e o modelo multilíngue **ggml-base-q5_1.bin**. Compare os SHA-256 publicados antes de executar. Extraia o runtime em `build/asr/runtime` e os fontes da mesma versão em `build/asr`, dentro da pasta da bancada. Rode `experiments\process-loopback\build-asr.cmd` no **x64 Native Tools Command Prompt** para gerar `asr-worker.exe` junto das DLLs. O teste usa uma voz PT-BR instalada no Windows. [Binário Windows e hash](https://github.com/ggml-org/whisper.cpp/releases/expanded_assets/v1.9.2) · [Código-fonte](https://github.com/ggml-org/whisper.cpp/tree/v1.9.2) · [Modelo e hash](https://huggingface.co/ggerganov/whisper.cpp/blob/main/ggml-base-q5_1.bin)

A prévia usa `ggml-small-q5_1.bin` se o arquivo estiver em `build/asr/`. O SHA-256 publicado é `ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb`. [Modelo multilíngue Small](https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small-q5_1.bin)

```powershell
python experiments/process-loopback/smoke_asr.py --asr-worker C:\caminho\asr-worker.exe --model C:\caminho\ggml-base-q5_1.bin
```

Para um ensaio autorizado com um PID específico, substitua o PID e ajuste a duração:

```powershell
python experiments/process-loopback/transcribe.py 12345 30 --asr-worker C:\caminho\asr-worker.exe --model C:\caminho\ggml-base-q5_1.bin
```

Para comparação, use `--whisper-cli C:\caminho\whisper-cli.exe` no lugar de `--asr-worker`. Nessa opção, `inferenceMs` inclui o carregamento do modelo a cada trecho. `fromSpeechEndMs` inclui a espera pelo silêncio e a fila. O fim da fala é estimado pelo limiar de energia. Música, ruído e falas sobrepostas exigem avaliação própria.

Use `--cards` para adicionar um cartão ao evento de transcrição quando houver uma correspondência. Esse modo pode rodar sem `--show-text`. Os padrões, as fontes e o limite de frequência são descritos na [prévia desktop](../desktop-preview/README.md). Rode `python experiments/process-loopback/test_rules.py` para verificar exemplos positivos, casos de silêncio e o intervalo entre cartões.

Em `--system vaesen --cards`, o detector procura tópicos pelo nome, pelo significado e pelo contexto recente da mesma fonte. O campo `lookup` envia o tópico à janela. A busca por significado roda na CPU com o [multilingual E5 Small](https://huggingface.co/intfloat/multilingual-e5-small). Instale `onnxruntime` e `tokenizers` no Python da prévia ou em `build/semantic/deps` e coloque `tokenizer.json` e `onnx/model_quantized.onnx` da [conversão ONNX](https://huggingface.co/Xenova/multilingual-e5-small/tree/761b726) diretamente em `build/semantic/`. A busca por nomes e o contexto de tópicos continuam disponíveis sem esse modelo. Os modelos e as dependências são locais durante a captura.

Acrescente `--microphone` para incluir a entrada padrão do Windows. Os eventos de nível e transcrição identificam a fonte como `discord` ou `microphone`. Se o microfone falhar, a ponte sinaliza a falha e mantém a captura do Discord.

Para testar apenas a entrada padrão, use `mic` no lugar do PID. A prévia usa essa opção no botão **Testar minha voz**.

## Interpretador de contexto de Vaesen

Coloque o executável e as DLLs da versão Windows x64 CPU do llama.cpp em `build/context/runtime/`. Coloque `qwen2.5-3b-instruct-q4_k_m.gguf` em `build/context/`. O SHA-256 publicado do modelo é `626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d`. [Runtime testado](https://github.com/ggml-org/llama.cpp/releases/tag/b12242) · [Modelo Qwen](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF)

Para usar o DeepSeek, baixe a quantização Q4_K_M (5,03 GB) e salve em `build/context/DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf`. Confira o SHA-256 `e0c2f118fd59f3a16f20d18b0e7f79e960c84bc8c66d94fd71a691e05151d54f`. Na prévia, selecione **DeepSeek R1 8B**. Pela bancada, acrescente `--context-model deepseek` junto de `--contextual`. O mesmo servidor local executa o modelo. [DeepSeek R1 8B](https://huggingface.co/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B) · [GGUF e checksum](https://huggingface.co/bartowski/deepseek-ai_DeepSeek-R1-0528-Qwen3-8B-GGUF/blob/main/deepseek-ai_DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf)

Com `--system vaesen --cards --contextual`, a ponte inicia o servidor na interface `127.0.0.1` e o encerra junto da sessão. As falas recentes ficam em memória. A busca local prepara os candidatos e o modelo faz uma única escolha, respondendo com um ID. A ponte só aceita IDs válidos da lista. Pedidos explícitos com um tópico único são resolvidos diretamente pelo catálogo. A consulta roda separada do ASR e emite o resultado em `context-result`.

Para acelerar na GPU, extraia a edição Vulkan do mesmo runtime em `build/context/runtime-vulkan/`. A ponte tenta esse runtime primeiro e usa CPU se a inicialização da GPU falhar. O ajuste automático de camadas usa `--fit-target 2500`, conforme a memória informada pelo backend. O interpretador usa até três threads de CPU, prioridade abaixo da normal e espera ativa desativada. Na prévia, o transcritor também usa até três threads. O teste de voz mostra **GPU (Vulkan)** ou **CPU** junto do modelo conectado. [Runtime Vulkan b12242](https://github.com/ggml-org/llama.cpp/releases/tag/b12242)

## Resultado inicial

O teste sintético passou neste Windows com SDK 10.0.26100.0 e MSVC x64. Nas duas janelas de isolamento de 3 s, o tom selecionado teve amplitude de aproximadamente 0,072 e o outro ficou abaixo de 0,00002. O p95 da idade dos pacotes ficou entre 11,2 e 11,5 ms nas três capturas, sem descontinuidades sinalizadas nem erros de timestamp. A captura retornou 2 quando o PID alvo encerrou e funcionou com o segundo PID escolhido explicitamente.

Com os sinais intermitentes, o teste voltou a passar. A saída incremental entregou 47.520 amostras em uma janela de 3 s, com timestamps válidos e intervalos silenciosos.

O ensaio de voz sintética transcreveu “Eu quero saltar de um telhado para o outro.” por WASAPI e pelo modelo base quantizado, em CPU com quatro threads. Duas execuções mediram 1,64 s e 3,39 s do fim estimado da fala ao texto, sem descarte por fila ou atraso. A seleção da árvore do Discord e o ensaio de longa duração seguem na [Fase 0](../../docs/ROADMAP.md#fase-0--investigação-e-provas-de-conceito).

Em duas rodadas, o worker transcreveu dois trechos por sessão com um único carregamento do modelo em cada sessão. Os quatro trechos chegaram entre 1,37 s e 2,66 s. O CLI mediu 2,71 s em um trecho da mesma frase na comparação direta. A amostra confirma a reutilização do modelo e ainda não permite estimar ganho de latência.

[Exemplo oficial de loopback por processo](https://learn.microsoft.com/en-us/samples/microsoft/windows-classic-samples/applicationloopbackaudio-sample/) · [Timestamps de IAudioCaptureClient::GetBuffer](https://learn.microsoft.com/en-us/windows/win32/api/audioclient/nf-audioclient-iaudiocaptureclient-getbuffer)
