# Whisper — Plano de execução

O repositório inicial contém apenas o README. O trabalho de desenvolvimento começa depois desta documentação. As fases abaixo usam critérios de saída porque o desempenho do áudio e a qualidade da interação ainda precisam ser medidos. O plano assume um desenvolvedor individual e apoio pontual de mestres para revisão e sessões de teste.

## Fase 0 — Investigação e provas de conceito

- **Primeira tarefa.** Usar a [bancada de loopback por processo](../experiments/process-loopback/README.md) para medir captura no Discord e encaminhar PCM em tempo real, com timestamps monotônicos, ao ASR no mesmo PC. Usar uma chamada privada de ensaio com roteiro e participantes informados. Bloquear o acesso à rede dos processos da bancada enquanto o Discord segue conectado.
- **Procedimento.** Reproduzir um sinal em outro aplicativo, pronunciar ações e negações no Discord, falar pelo microfone do mestre separadamente e repetir com sobreposição. Gravar apenas métricas por padrão. Se o exemplo gerar WAV, usar exclusivamente material de teste autorizado, com armazenamento separado e descarte definido. Repetir após trocar a saída, fechar/reabrir o Discord, suspender o Windows e alternar mute. Registrar PID, build do Windows, origem, lacunas e tempos por etapa.
- **Entregáveis.** Relato de isolamento por processo, recuperação de fonte, latência e recursos. Comparativo de `base` e `small` multilíngues quantizados em CPU. Se a fila crescer, testar Vosk e, em hardware compatível, medir aceleração no dispositivo com o mesmo replay. Preparar os primeiros casos positivos e negativos das três famílias.
- **Dependências.** Notebook de referência, SDK Windows, Discord desktop, binários e pesos com origem conhecida, colega ou segunda instância legítima para a chamada e roteiro de teste. [Exemplo oficial da Microsoft](https://learn.microsoft.com/en-us/samples/microsoft/windows-classic-samples/applicationloopbackaudio-sample/)
- **Conclusão.** Duas execuções de pelo menos 30 min com chamada seletiva sem o sinal do outro app. Demonstrar identificação da perda da fonte e recuperação segura. No conjunto de trechos claros, obter p95 de até 4 s do fim da fala a segmento estável, reservando até 1 s para o resto do pipeline, e medir preservação de termos críticos. Medir ambos os modos de entrada. Se a fala sobreposta comprometer a decisão, registrar em quais casos a abstinência é suficiente.
- **Riscos e decisão.** Se o áudio do Discord não puder ser isolado com confiabilidade, investigar o PID e testar roteamento dedicado de forma controlada. Se for preciso capturar um endpoint compartilhado para funcionar, reavaliar o recorte antes de seguir. Se a inferência for o gargalo, comparar modelos e configurações no dispositivo. Se a comunicação com o worker for o gargalo medido, avaliar ASR no processo desktop. [Pesquisa](TECHNICAL_RESEARCH.md) · [Arquiteturas](ARCHITECTURE.md)

## Fase 1 — Fundação técnica

- **Entregáveis.** Uma solução .NET com app Windows, núcleo, adaptadores e testes. Convenções para timestamps, estados de sessão, versão de dependências e dados de teste. Automatizar build e testes em Windows. Fixar pacote e ASR como entradas versionadas, com origem, checksums e licenças.
- **Dependências.** Captura e ASR escolhidos na Fase 0. Delimitar regras e fontes que entrarão no pacote 5.2.1.
- **Conclusão.** Checkout limpo produz build e testes. O núcleo roda com fontes e relógio falsos, sem interface. Replay sintético percorre o contrato de segmentos. Lista de artefatos e licenças reproduzível.
- **Riscos.** Complexidade prematura em empacotamento ou abstrações. Criar as fronteiras necessárias para trocar fontes, ASR e relógio e adiar separação adicional até haver outro consumidor.

## Fase 2 — Pipeline de áudio

- **Entregáveis.** Adaptador WASAPI, prévia de níveis, microfone opcional, normalização e VAD, fila limitada, worker de ASR e segmentos estáveis. Integrar cancelamento, pausa e recuperação sem buffer de transcrição persistente.
- **Dependências.** Contratos e ferramenta de replay da Fase 1, cenários de captura da Fase 0.
- **Conclusão.** Chamada de 2 h com protocolo de recursos e estabilidade do MVP. Exercitar mudança de PID, perda de microfone, suspensão, saturação e encerramento do worker. Resultados de geração anterior são rejeitados. A chamada funciona com acesso à rede bloqueado para o Whisper e seus workers.
- **Riscos.** Fila crescente com duas fontes, eco e confusão entre fonte parada e conversa silenciosa. Usar replay dos mesmos estímulos, separar métricas por origem e checar se o microfone melhora a decisão antes de promover seu uso.

## Fase 3 — Inteligência contextual

- **Entregáveis.** Pacote curado das três famílias, léxico bilíngue, janela de contexto, detector, validação, cartões e política de silêncio. Ferramenta de avaliação que distingue falha de ASR, interpretação, recuperação e supressão.
- **Dependências.** Contratos de segmentos, exemplos anotados e revisão das fontes. Curadoria e testes com transcrição de referência podem começar antes de estabilizar a Fase 2.
- **Conclusão.** Holdout com metas de cobertura, silêncio e correção do [MVP](MVP_SCOPE.md). Revisão humana por afirmação dos cartões. Comparar transcrição de referência e ASR para atribuir perdas. Ausência de erro crítico e de mistura entre edições.
- **Riscos.** Alta precisão artificial com pouquíssimos disparos, gatilhos frágeis e uso de regra correta em contexto errado. Manter critérios de cobertura e separar dados de ajuste do holdout.

## Fase 4 — Interface desktop

- **Entregáveis.** Onboarding, bandeja, medidores, popup, modos de frequência, histórico e detalhe da fonte. Roteiro de consentimento, ação de pausa e controle para ocultar janelas. Instalador x64 e preparação do modelo.
- **Dependências.** Estado da sessão e cartões validados. Testes de foco e compartilhamento podem avançar com cartões sintéticos.
- **Conclusão.** Instalação e preparação do modelo em VM limpa e offline. Validar a UI sem roubo de foco, múltiplos monitores, compartilhamento, exclusão do histórico e recuperação de falhas. Ensaio com um mestre que faça o fluxo sem instrução oral.
- **Riscos.** Aviso exposto durante compartilhamento, instalador bloqueado ou onboarding confuso. Testar a distribuição e o modo oculto antes de colocar conteúdo de sessão na tela.

## Fase 5 — Validação em sessões reais

- **Entregáveis.** Relatório do piloto com contagens, distribuições de latência, categorias úteis, falhas e feedback dos mestres. Registrar evidências de consentimento operacional sem coletar nomes ou conteúdo como telemetria. Consolidar requisitos de hardware e custo energético medido em bancada.
- **Dependências.** Critérios das fases anteriores, pacote e avisos revisados, mesas adultas consentidas, política de coleta e prazo de exclusão.
- **Conclusão.** Executar observação inicial e seis sessões de pelo menos três mesas. Comparar resultados com as metas técnicas e de experiência. Escolher entre ampliar o piloto, restringir o escopo a categorias úteis ou iterar no maior gargalo medido. Falha de privacidade ou erro mecânico crítico suspende a expansão até revisão.
- **Riscos.** Viés de mesa, baixa amostra e feedback só sobre os melhores cartões. Reportar denominadores e ausências de feedback e preservar um novo holdout para a próxima rodada.
