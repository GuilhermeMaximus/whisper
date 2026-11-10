# Whisper

Whisper é um companheiro em tempo real para Mestres de RPG de mesa. Ele escuta a chamada do Discord (e, se você quiser, o seu microfone), transcreve a fala **localmente** e mostra cartões discretos com lembretes de regras, sem interromper o jogo. Nada sai do seu computador: não há conta, nuvem nem chave de API, e o app não grava áudio nem transcrições.

Este repositório contém a documentação de produto e a **prévia desktop** (WPF/.NET 10) com a bancada de captura, transcrição e interpretação. Dois sistemas são suportados na prévia: **Vaesen** (com biblioteca de regras importada dos seus PDFs) e **D&D 5e (2024)** (cartões baseados no SRD 5.2.1).

> Plataforma: **Windows 11 x64**. A captura de áudio por processo (WASAPI) só existe no Windows.

## Como as peças se encaixam

```
Discord / microfone ──► audio-capture.exe ──► transcribe.py ──► asr-worker.exe (whisper.cpp)
                                                   │
                                                   ├─► rules.py / semantic.py   (regras e busca por significado)
                                                   └─► contextual.py ► llama-server (Qwen / DeepSeek, só Vaesen)
                                                   ▼
                                     Whisper.Preview (WPF): medidores, cartões e Biblioteca
```

A janela WPF inicia `transcribe.py` com o `python.exe` do PATH. Esse script coordena os executáveis nativos e devolve eventos de nível, transcrição e cartões.

## Estrutura

| Caminho | Conteúdo |
| --- | --- |
| `experiments/desktop-preview/` | Aplicativo WPF (janela principal, Biblioteca de Vaesen, notificação) |
| `experiments/process-loopback/` | Bancada: captura em C++, worker de ASR, scripts Python e testes |
| `experiments/process-loopback/build/` | Binários e modelos baixados (fora do Git) |
| `experiments/process-loopback/local-rules/` | Índice dos seus PDFs, traduções e fichas estruturadas (fora do Git) |
| `experiments/desktop-preview/vaesen-guide.json` | Guia dos 52 procedimentos de Vaesen, com texto próprio (no Git) |
| `docs/` | Visão, requisitos, escopo do MVP, arquitetura, riscos e roadmap |

## Passo a passo

### 1. Instale os pré-requisitos

1. **Windows 11 x64** com uma saída de áudio ativa e microfone padrão configurado (para o teste de voz).
2. **.NET 10 SDK** (<https://dotnet.microsoft.com/download>). Confirme com `dotnet --version`.
3. **Visual Studio Build Tools** com a carga *Desenvolvimento para desktop com C++* e o Windows SDK. Eles fornecem o compilador MSVC x64.
4. **Python 3.12 de 64 bits** disponível como `python.exe` no PATH. Confirme com `python --version`.
5. **Git**, para clonar o repositório.
6. Uma **voz PT-BR instalada no Windows** (Configurações → Hora e idioma → Fala), usada no teste com voz sintética.

Clone o projeto e abra o PowerShell na raiz dele:

```powershell
git clone <url-do-repositório> whisper
cd whisper
```

### 2. Compile a captura de áudio

Abra o **x64 Native Tools Command Prompt for VS** (menu Iniciar), vá até a raiz do repositório e rode:

```cmd
experiments\process-loopback\build.cmd
```

Isso gera `experiments\process-loopback\build\audio-capture.exe`. Se aparecer *Open an x64 Native Tools Command Prompt*, você abriu o prompt errado.

Teste (opcional, toca tons suaves e pede saída de áudio ativa):

```cmd
python experiments\process-loopback\smoke.py
```

### 3. Prepare o transcritor (whisper.cpp)

1. Baixe o ZIP **Windows x64** do whisper.cpp **v1.9.2** em <https://github.com/ggml-org/whisper.cpp/releases/expanded_assets/v1.9.2> e extraia em `experiments\process-loopback\build\asr\runtime\` de modo que exista `build\asr\runtime\Release\whisper.dll`.
2. Baixe o **código-fonte da mesma versão** (<https://github.com/ggml-org/whisper.cpp/tree/v1.9.2>) e extraia em `build\asr\` para que exista `build\asr\whisper.cpp-1.9.2\include\whisper.h`.
3. Baixe o modelo multilíngue e salve em `build\asr\`:
   - **Recomendado:** `ggml-small-q5_1.bin` (SHA-256 `ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb`). [Download](https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small-q5_1.bin)
   - **Mais leve:** `ggml-base-q5_1.bin`. [Download](https://huggingface.co/ggerganov/whisper.cpp/blob/main/ggml-base-q5_1.bin)

   O app prefere o Small quando ele existe. Confira o hash com `Get-FileHash <arquivo> -Algorithm SHA256`.
4. No mesmo **x64 Native Tools Command Prompt**, gere o worker:

   ```cmd
   experiments\process-loopback\build-asr.cmd
   ```

   O resultado é `build\asr\runtime\Release\asr-worker.exe`, ao lado das DLLs.

Teste o ASR (opcional):

```powershell
python experiments/process-loopback/smoke_asr.py --asr-worker experiments\process-loopback\build\asr\runtime\Release\asr-worker.exe --model experiments\process-loopback\build\asr\ggml-small-q5_1.bin
```

Neste ponto o **D&D 5e (2024)** já funciona com o teste de voz e a voz sintética.

### 4. Importe os livros de Vaesen (só para Vaesen)

Você precisa dos seus PDFs do livro de regras, de *Mythic Britain* e de *Mythic Carpathia*. O repositório não os inclui.

```powershell
pip install pypdfium2
python experiments/process-loopback/import_vaesen.py --core 'C:\caminho\livro-de-regras.pdf' --britain 'C:\caminho\mythic-britain.pdf' --carpathia 'C:\caminho\mythic-carpathia.pdf'
```

O importador confere a edição por hash e grava `experiments/process-loopback/local-rules/vaesen.json`. Se mover um PDF, importe de novo para atualizar o caminho. Sem esse arquivo, o app abre em D&D e recusa iniciar a escuta de Vaesen.

### 5. Gere a tradução para PT-BR (opcional, Vaesen)

```powershell
pip install ctranslate2 sentencepiece
```

Baixe o [modelo en → pt-BR 1.9 do Argos](https://argos-net.com/v1/translate-en_pb-1_9.argosmodel), renomeie para `.zip` e extraia. Use a pasta que contém `sentencepiece.model` e `model/`:

```powershell
python experiments/process-loopback/translate_vaesen.py --model 'C:\caminho\translate-en_pb-1_9'
```

Roda na CPU, offline, pode ser retomado e salva `local-rules/vaesen-pt-br.json`. Reabra o Whisper depois de gerar.

### 6. Organize as fichas em cartões padronizados (Vaesen)

Depois de importar os PDFs (e, se quiser, gerar a tradução), estruture as fichas de criaturas, rituais, talentos, melhorias e arquétipos:

```powershell
python experiments/process-loopback/build_vaesen_cards.py --report
```

O script lê o índice local, grava `experiments/process-loopback/local-rules/vaesen-cards.json` (fora do Git, pois deriva dos livros) e informa quantas fichas de cada categoria ganharam cartão. As que ficarem de fora continuam aparecendo como trecho do livro. Rode de novo sempre que reimportar os PDFs ou gerar uma nova tradução.

Os 52 procedimentos (iniciativa, Medo, forçar a jogada etc.) já vêm prontos no repositório, em `experiments/desktop-preview/vaesen-guide.json`, com texto próprio. Para gerar o guia impresso a partir dele:

```powershell
python experiments/process-loopback/export_vaesen_guide.py
```

O resultado é [`docs/VAESEN_GUIA_DO_MESTRE.md`](docs/VAESEN_GUIA_DO_MESTRE.md).

### 7. Ative a busca por significado (opcional, Vaesen)

Sem ela, a busca por nomes e o contexto de tópicos continuam funcionando.

```powershell
pip install onnxruntime tokenizers numpy
```

Baixe da [conversão ONNX do multilingual E5 Small](https://huggingface.co/Xenova/multilingual-e5-small/tree/761b726) os arquivos `tokenizer.json` e `onnx/model_quantized.onnx` e coloque-os em `experiments\process-loopback\build\semantic\` (o `model_quantized.onnx` dentro da subpasta `onnx\`).

### 8. Configure o interpretador local (opcional, Vaesen)

O interpretador usa um modelo de linguagem local para escolher a referência certa a partir das últimas falas.

1. Baixe o **llama.cpp b12242** para Windows x64 (<https://github.com/ggml-org/llama.cpp/releases/tag/b12242>).
   - Versão **CPU**: extraia em `build\context\runtime\` (precisa conter `llama-server.exe`).
   - Versão **Vulkan** (opcional, usa a GPU): extraia em `build\context\runtime-vulkan\`. A ponte tenta a GPU primeiro e cai para CPU se falhar.
2. Baixe um modelo GGUF para `build\context\`:
   - **Qwen 2.5 3B:** `qwen2.5-3b-instruct-q4_k_m.gguf` (SHA-256 `626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d`). [Download](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF)
   - **DeepSeek R1 8B:** `DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf`, 5,03 GB (SHA-256 `e0c2f118fd59f3a16f20d18b0e7f79e960c84bc8c66d94fd71a691e05151d54f`). [Download](https://huggingface.co/bartowski/deepseek-ai_DeepSeek-R1-0528-Qwen3-8B-GGUF/blob/main/deepseek-ai_DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf)
3. Na janela do Whisper, escolha o modelo em **Interpretador local** antes de iniciar. O servidor sobe em `127.0.0.1` e é encerrado junto com a sessão.

### 9. Confira a pasta `build`

Ao final, a árvore deve ficar assim (itens de Vaesen são opcionais):

```
experiments/process-loopback/
├── build/
│   ├── audio-capture.exe
│   ├── asr/
│   │   ├── ggml-small-q5_1.bin            (ou ggml-base-q5_1.bin)
│   │   └── runtime/Release/asr-worker.exe (+ whisper.dll e demais DLLs)
│   ├── semantic/  tokenizer.json, onnx/model_quantized.onnx
│   └── context/   runtime/, runtime-vulkan/, *.gguf
└── local-rules/   vaesen.json, vaesen-pt-br.json, vaesen-cards.json
```

### 10. Rode o aplicativo

Na raiz do repositório:

```powershell
dotnet run -c Release --project experiments/desktop-preview
```

O app localiza a bancada subindo as pastas a partir do executável até achar `experiments/process-loopback/transcribe.py`, então abra-o sempre a partir do repositório.

## Como os cards da Biblioteca são organizados

Todo tópico segue a mesma ordem, para leitura rápida no topo e leitura completa embaixo:

1. **Leitura rápida:** uma frase com a situação em que a regra se aplica e chips com os números-chave (dados, sucessos, custo, alcance).
2. **Como fazer:** passos numerados, na ordem em que a Mestre age.
3. **Atenção:** exceções e armadilhas.
4. **Veja também:** tópicos relacionados.

As fichas de criaturas, rituais, talentos, melhorias e arquétipos usam o mesmo desenho com campos próprios: atributos e Medo nos chips, depois poderes, combate, Condições e ritual. O botão **Ver trecho do livro** mostra o texto original e **Ver ficha organizada** volta ao cartão. A categoria da busca agrupa os procedimentos por assunto (Criação, Testes, Combate, Dano e Medo, Equipamento, Base, Vaesen e magia, Preparar o mistério, Suplementos).

O mesmo `vaesen-guide.json` alimenta o interpretador local: a frase "quando" de cada tópico entra na busca e na descrição enviada ao modelo, o que ajuda a casar falas de mesa com a regra certa.

## Usando o app

1. Escolha o **Sistema** (Vaesen ou D&D 5e). Em Vaesen, escolha também o **Interpretador local**.
2. **Testar notificação** mostra o cartão flutuante sem precisar de áudio.
3. **Testar com voz sintética** valida o pipeline inteiro (captura → ASR → regras) usando a voz PT-BR do Windows. Em Vaesen, fala "Regra pra classe social" e "Regra pra forçar jogada"; em D&D, "Salto horizontal".
4. **Testar minha voz** escuta só o microfone padrão por até 2 minutos. Espere **Teste de voz ativo**, fale e faça uma pausa. O último trecho reconhecido aparece na tela.
5. **Chamada real no Discord:** abra o Gerenciador de Tarefas, localize o processo raiz do **Discord** e copie o **PID**. Cole em **PID do Discord**, marque que os participantes foram informados e concordam e clique em **Iniciar captura**. Marque **Incluir meu microfone** antes de iniciar se quiser capturar sua própria voz (silenciar no Discord não desliga essa fonte).
6. **Parar** encerra a captura e todos os processos locais. Reiniciou o Discord? Confira o PID de novo.
7. **Biblioteca de Vaesen** abre a consulta por tópico, com filtros de livro, categoria e *Opcionais e variantes*. Busque, por exemplo, "Arsenal", ou diga "Consultar ritual da Banshee" durante a escuta.

Os cartões respeitam um intervalo mínimo de 90 s e no máximo quatro por hora. O app não toca som.

## Problemas comuns

| Sintoma | O que verificar |
| --- | --- |
| "Prepare o executável da bancada e o modelo local…" | Faltam `audio-capture.exe`, o modelo `.bin` ou `asr-worker.exe` (passos 2 e 3) |
| "Importe os três PDFs de Vaesen antes de começar" | Rode o passo 4 ou use D&D |
| Fichas aparecem só como trecho do livro | Rode o passo 6 e reabra o Whisper |
| "Abra a prévia a partir do repositório Whisper" | Rode `dotnet run` de dentro da pasta clonada |
| "Fonte indisponível" | O PID não é de um processo do Discord desktop |
| Nada é transcrito | Confirme `python` no PATH, volume do áudio e o microfone padrão do Windows |
| Interpretador usa CPU e fica lento | Instale o runtime Vulkan (passo 8) ou use o Qwen 2.5 3B |

## Testes

```powershell
python experiments/process-loopback/test_rules.py
python experiments/process-loopback/test_contextual.py
python experiments/process-loopback/test_audio_sources.py
```

## Documentação

[Guia rápido da Mestre (Vaesen)](docs/VAESEN_GUIA_DO_MESTRE.md) · [Visão do produto](docs/PRODUCT_VISION.md) · [Requisitos](docs/REQUIREMENTS.md) · [Escopo do MVP](docs/MVP_SCOPE.md) · [Arquitetura](docs/ARCHITECTURE.md) · [Pesquisa técnica](docs/TECHNICAL_RESEARCH.md) · [Riscos](docs/RISKS.md) · [Roadmap](docs/ROADMAP.md) · [Bancada de captura](experiments/process-loopback/README.md) · [Prévia desktop](experiments/desktop-preview/README.md)

## Licenças e atribuição

Os cartões de D&D adaptam o **System Reference Document 5.2.1**, de Wizards of the Coast LLC, sob a licença [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/legalcode). [SRD](https://www.dndbeyond.com/srd). Os livros de Vaesen não fazem parte do repositório: você importa os seus próprios PDFs.
