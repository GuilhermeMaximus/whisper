# Whisper — Prévia desktop

Janela WPF para experimentar a captura, o ASR e os primeiros lembretes mecânicos. O seletor permite usar Vaesen ou D&D 5e (2024). A biblioteca de Vaesen consulta os PDFs no próprio computador.

## Abrir

Prepare os binários e o modelo de acordo com as instruções da [bancada](../process-loopback/README.md). A prévia usa o Python disponível como `python.exe` no PATH e espera estes arquivos na bancada:

- `build/audio-capture.exe`
- `build/asr/runtime/Release/asr-worker.exe`, junto com as DLLs do whisper.cpp v1.9.2
- `build/asr/ggml-small-q5_1.bin` ou `build/asr/ggml-base-q5_1.bin`. A prévia prefere o Small multilíngue quando instalado.

Com o SDK .NET 10 disponível, rode a partir da raiz do repositório:

```powershell
dotnet run -c Release --project experiments/desktop-preview
```

Neste workspace, o SDK também foi preparado em `experiments/process-loopback/build/sdk`. Use `.experiments\process-loopback\build\sdk\dotnet.exe` no lugar de `dotnet` se ele não estiver no PATH.

## Experimentar

- **Testar minha voz.** Usa a entrada padrão do Windows por até dois minutos. Aguarde **Teste de voz ativo**, fale normalmente e faça uma pausa. O medidor mostra o áudio recebido e o último trecho reconhecido aparece durante o teste. Os cartões e as consultas usam o sistema selecionado. **Parar** encerra a captura e limpa a frase da tela. O teste funciona com o microfone sozinho.
- **Testar com voz sintética.** Reproduz fala com uma voz PT-BR instalada no Windows. O mesmo pipeline de captura e ASR alimenta o medidor. Em Vaesen, o ensaio fala “Regra pra classe social” e “Regra pra forçar jogada” na mesma captura. Em D&D, demonstra “Salto horizontal”.
- **Iniciar captura.** Para uma chamada privada de teste, informe o PID do Discord desktop e confirme que todos concordaram. O medidor e a latência usam a captura real. Um cartão pode aparecer quando um trecho corresponde a uma regra do detector local.
- **Incluir meu microfone.** Marque antes de iniciar se quiser que o Whisper também escute a sua voz. O segundo medidor usa a entrada padrão em **Configurações → Sistema → Som → Entrada** do Windows. Silenciar no Discord não desliga essa captura separada. Para interromper as duas fontes, use **Parar**.
- **Parar.** Encerra a captura e seus processos locais. A janela não exibe a transcrição da chamada. A referência pode ser aberta no navegador por ação do mestre.

## Biblioteca de Vaesen

Os três PDFs desta instalação já foram indexados. Em outra máquina, use um Python com `pypdfium2` para importar as mesmas edições:

```powershell
python experiments/process-loopback/import_vaesen.py --core 'C:\caminho\livro-de-regras.pdf' --britain 'C:\caminho\mythic-britain.pdf' --carpathia 'C:\caminho\mythic-carpathia.pdf'
```

O importador confere a edição pelos hashes e guarda o índice em `experiments/process-loopback/local-rules/vaesen.json`, fora do Git. Se mover um PDF, importe novamente para atualizar o caminho. A biblioteca lista tópicos técnicos com títulos únicos. A busca considera nomes, aliases, explicações e trechos técnicos selecionados. Use **Abrir PDF original** para consultar a fonte completa.

Use **Opcionais e variantes** para ver os tópicos marcados, incluindo Caminhos da Vida, classe social, variantes com efeitos de jogo e a opção de dialeto de *Old Meg*. *Mythic Carpathia* está identificado como beta.

O leitor prioriza a explicação ou o trecho técnico em português. Quando há dois idiomas para um trecho, **Ver original em inglês** alterna o texto na mesma janela. Alguns trechos permanecem em inglês quando a tradução automática não preserva os valores numéricos ou o início da seção.

Em outra máquina, após importar os livros, instale `ctranslate2` e `sentencepiece` em um Python 3.12 de 64 bits e extraia o [modelo en → pt-BR 1.9 do Argos](https://argos-net.com/v1/translate-en_pb-1_9.argosmodel) como um ZIP. Use a pasta que contém `sentencepiece.model` e `model/`:

```powershell
python experiments/process-loopback/translate_vaesen.py --model 'C:\caminho\translate-en_pb-1_9'
```

A geração roda na CPU sem acessar a rede, pode ser retomada e salva a tradução em `local-rules/vaesen-pt-br.json`, fora do Git. Reabra o Whisper após gerar o arquivo.

Vaesen tem oito lembretes automáticos nesta prévia. Eles cobrem forçar a jogada, iniciativa, esquiva, aparar, imobilização, Medo e tratamento de Condições físicas e mentais. Uma fala de jogo como “Eu falhei no teste, mas vou rolar os dados de novo” pode mostrar o lembrete de forçar a jogada. Os demais procedimentos estão disponíveis na biblioteca. As opções dos suplementos são apresentadas com sua fonte para consulta da Mestre.

Em **Interpretador local**, escolha **Qwen 2.5 3B** ou **DeepSeek R1 8B** antes de começar a escuta de Vaesen. O modelo usa a última fala e até quatro falas anteriores da mesma fonte, dentro de 90 s, para escolher uma referência do catálogo técnico. O cartão leva ao tópico e à página de origem. No teste de voz, a transcrição aparece antes da consulta. A linha de estado informa se o interpretador usa **GPU (Vulkan)** ou **CPU**. A configuração dos modelos e da aceleração está na [bancada](../process-loopback/README.md#interpretador-de-contexto-de-vaesen).

Na biblioteca, **Categoria** lista as referências pelo nome. Use **Criaturas**, **Rituais**, **Arquétipos**, **Talentos** ou **Melhorias da sede** para navegar. Diga **“Consultar ritual da Banshee”** ou **“Consultar ficha de Baba Iaga”** para abrir o tópico correspondente. Uma busca por “Arsenal” distingue a melhoria do livro básico da melhoria da Powder Gate.

## Cartões de D&D

O worker mantém o modelo carregado durante o ensaio. O detector trabalha com frases explícitas em português e tenta cobrir poucas formas por regra. Por exemplo, “Vou saltar de um telhado para o outro”, “Vou agarrar o goblin” e “Estou mantendo a concentração e tomei oito pontos de dano”. Hipóteses, negações, ações já resolvidas e trechos fora dos padrões ficam sem cartão. Há um intervalo mínimo de 90 s entre cartões e um teto de quatro por hora. Os cartões aparecem na própria janela, sem som.

A prévia considera um trecho estável por vez. O detector ainda não usa contexto entre trechos nem identificação de locutor. A validação com conversa real do Discord continua pendente.

Os cartões adaptam para o português material do **System Reference Document 5.2.1 (SRD 5.2.1)**, de Wizards of the Coast LLC, sob a licença **Creative Commons Attribution 4.0 International**. [SRD](https://www.dndbeyond.com/srd) · [Licença](https://creativecommons.org/licenses/by/4.0/legalcode)
