# Whisper — Requisitos

**P0** é necessário para validar o MVP. **P1** entra se o piloto revelar uma necessidade concreta. **P2** depende de nova validação. As metas numéricas e seus métodos estão no [escopo do MVP](MVP_SCOPE.md).

## Funcionais

- **RF-01 · P0 · Sessão e consentimento.** Exibir fonte, edição, aviso de processamento local e retenção antes da captura. Iniciar após confirmação por sessão de que os participantes foram informados e concordaram. Disponibilizar prévia de fonte, pausa, retomada explícita e encerramento. Mudança de fonte invalida a confirmação. Chegada ou saída de pessoas, mudança de canal e revogação são tratadas pelo mestre com pausa e reconfirmação.
- **RF-02 · P0 · Captura seletiva.** Capturar áudio renderizado pelo Discord desktop no Windows 11 x64 via loopback por processo. Permitir microfone do mestre como fonte separada, desligada por padrão. Exibir atividade de cada fonte. Se a fonte falhar, informar e interromper a análise que dependa dela. A prévia mostra nível local e não alimenta ASR.
- **RF-03 · P0 · Transcrição incremental.** Produzir segmentos temporizados em português brasileiro durante a chamada. O pipeline distingue resultados revisáveis de segmentos estáveis, carrega a origem e sinaliza lacunas e baixa qualidade. A UI principal permanece sem transcrição.
- **RF-04 · P0 · Candidatos mecânicos.** Detectar um conjunto limitado de ações e dúvidas do mestre. Considerar contexto recente, negação, hipótese, correção, fala fora do jogo e resolução pelo mestre. Confirmar estado ficcional exige evidência explícita. Ambiguidade relevante termina em silêncio.
- **RF-05 · P0 · Base de regras.** Carregar um pacote versionado do SRD 5.2.1 com fontes e atribuição acessíveis offline. Recuperar regras da edição selecionada. Distinguir texto oficial verificado de adaptação, interpretação, opção do mestre e caso sem cobertura. Interpretação ou informação insuficiente nunca vira regra oficial. O MVP usa cartões curados, inclusive opções previstas na fonte.
- **RF-06 · P0 · Notificação.** Exibir cartão temporário, sem som e sem tomar foco, com título curto, um lembrete acionável e acesso à fonte. Suprimir duplicatas, respostas tardias e situações já resolvidas. Oferecer modos silencioso, conservador e padrão. Silencioso guarda cartões elegíveis só no histórico.
- **RF-07 · P0 · Histórico e exclusão.** Exibir cartões recentes da sessão, permitir dispensa e limpeza, manter o histórico em RAM e descartá-lo ao encerrar. Pausar apaga áudio e contexto, preservando apenas os cartões já emitidos até limpeza ou fim da sessão. Feedback do piloto é opcional e separado do histórico.
- **RF-08 · P0 · Controle durante compartilhamento.** Oferecer controle acessível na bandeja para ocultar cartões e janelas do Whisper antes do compartilhamento de tela. Indicadores do app devem evitar nomes e conteúdo de sessão. Orientar o mestre sobre o alcance do compartilhamento durante o onboarding.
- **RF-09 · P1 · Regras da mesa.** Permitir cadastrar regras caseiras localmente e definir quais regras substituem. Rotular a origem e resolver precedência de modo explícito. No MVP, usar o modo silencioso em categorias ou mesas em que regras divergentes tornariam os lembretes inadequados.
- **RF-10 · P0 · Instalação offline.** Permitir instalação e preparação do modelo a partir de arquivos locais verificados. Informar incompatibilidade ou falta de artefato antes de iniciar a captura.
- **RF-11 · P2 · Extensão.** Adicionar pacotes para outros sistemas e, se o problema justificar, diarização no dispositivo, integração com VTT e memória de campanha editável. Alterações de estado, como condições e duração, exigem confirmação ou uma fonte autorizada de eventos.

## Não funcionais

- **RNF-01 · P0 · Desempenho.** Captura e UI não bloqueiam pelo ASR. Buffers limitados, orçamento por evento, descarte de trabalho vencido e supressão durante lacunas. Medir CPU, memória, atraso e estabilidade com Discord e VTT no hardware de referência.
- **RNF-02 · P0 · Precisão e utilidade.** Cada afirmação mecânica exibida deve ser rastreável ao pacote da sessão. Medir precisão, cobertura, falsos positivos, latência, relevância percebida e distração. Uma regra fabricada ou de edição errada bloqueia a expansão do piloto.
- **RNF-03 · P0 · Execução local e minimização.** Captura, ASR, interpretação, regras e interface operam no PC do mestre, sem conta, serviço de rede ou telemetria automática. Áudio e transcrição ficam em memória com limites explícitos. Logs e diagnósticos excluem conteúdo de fala e identificadores de participantes. Configuração local persiste separadamente.
- **RNF-04 · P0 · Segurança.** Validar origem, integridade e licença de binários, modelos e pacotes antes da distribuição. Executar como usuário comum e limitar o acesso à comunicação com o worker. Tratar fala e dados de pacotes como entradas não confiáveis.
- **RNF-05 · P0 · Recuperação.** Suspensão, perda da fonte, fila saturada ou encerramento do processo de ASR não produzem alertas atrasados. Exibir estado de forma discreta e permitir retomar após revalidar a fonte e o contexto. Encerramento e pausa cancelam tarefas e invalidam resultados em voo.
- **RNF-06 · P0 · Acessibilidade.** Status compreensível sem depender de cor, operação por teclado, fonte legível, suporte a escala do Windows e histórico acessível depois que o popup some.
- **RNF-07 · P0 · Testabilidade.** Reexecutar o pipeline com áudio consentido ou sintético, segmentos gravados para teste e relógio controlado. Versionar corpus, pacote, modelo, hardware e configuração de limiares. Separar gravações do piloto dos arquivos do repositório.
- **RNF-08 · P1 · Atualização local.** Verificar versões e integridade dos artefatos de atualização e preservar a última combinação válida de binário, modelo e pacote para recuperação. O fluxo de atualização fica separado da sessão.

## Limites de confiança

Um segmento “final” encerra uma hipótese do ASR, mas ainda pode conter erros. Uma declaração de intenção não confirma resultado. Uma regra recuperada pode ser verdadeira para outra edição, ou depender de uma condição desconhecida. Cada etapa tem sua própria evidência e pode interromper o fluxo. Veja a [arquitetura](ARCHITECTURE.md).
