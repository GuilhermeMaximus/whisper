# Whisper — Escopo e validação do MVP

## Pergunta de decisão

Um mestre consegue receber lembretes mecânicos corretos e a tempo, sem perder o fio da sessão e com os participantes cientes da escuta?

O MVP cobre Windows 11 x64, Discord desktop, sessões em português brasileiro e D&D 5e de 2024 com o SRD 5.2.1. O Whisper roda integralmente no PC do mestre e funciona sem acesso à rede depois de preparar o modelo. A chamada continua usando a conexão do Discord. Capturar a saída do Discord e oferecer microfone do mestre como opção explícita. O microfone ajuda a reconhecer perguntas e resoluções do mestre. Quando estiver desativado, o pipeline aceita menos candidatos que dependam de seu contexto.

## Menor conjunto útil

- **Uma sessão local.** Seleção de fonte e edição, roteiro de consentimento, medidores, bandeja, pausa e retomada, encerramento e limpeza de dados. Tratar uma mesa por sessão.
- **Três famílias de eventos.** Salto horizontal, declaração de tentativa de agarrar e lembrete de concentração em casos explícitos. A terceira família exige menção inequívoca a dano e concentração no mesmo evento, ou pergunta direta do mestre. Um personagem conjurar magia em um turno anterior não estabelece concentração ativa.
- **Um pacote curado.** Cada família tem cartões PT-BR revisados, com fonte, edição, condições e indicação de opção do mestre quando couber. Usar termos em inglês como aliases e conferir o texto oficial ao revisar o pacote. [SRD 5.2.1](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf)
- **Uma UI discreta.** Popup breve, sem foco e sem som, histórico da sessão, consulta da fonte e modo silencioso. Feedback simples no histórico para o piloto.

Exemplo de cartão para um salto declarado. “Salto horizontal · confira a distância. Se você se mover pelo menos 10 pés imediatamente antes de saltar, o alcance em pés vai até o valor de Força. No salto parado, use metade. A distância gasta movimento.” A referência abre o verbete *Long Jump*. O texto funciona como consulta e deixa a decisão com o mestre. “E se eu pulasse?” seguido de “melhor descer pela escada” deve terminar sem cartão.

## Fora da primeira versão

Bot do Discord, Windows 10, Discord no navegador, suporte móvel e multiplataforma, outros sistemas, catálogo completo de D&D, geração livre de regras, LLM no caminho obrigatório, diarização de jogadores, monitoramento de turnos, duração de efeitos, fichas, memória de campanha, VTT, editor de regras caseiras, gravação de sessão, transcrição consultável, contas, cobrança e sincronização.

## Aceitação funcional

1. **Captura e operação.** Com Discord e um segundo app reproduzindo sinais de teste distintos, apenas o áudio esperado entra na captura. Conferir o microfone separadamente, incluindo mute no Discord. Troca de PID ou fonte, suspensão, falta de permissão e perda do ASR apresentam estado acionável. Nenhuma falha muda para uma fonte mais ampla nem dispara avisos de áudio vencido.
2. **Contexto.** Em replay, a declaração clara de cada uma das três famílias pode gerar um cartão. Suprimir hipótese, negação, correção, fala fora do jogo, ação resolvida, baixa confiança, duplicata, regra de outra edição e trecho afetado por uma lacuna. Incluir cenas com casos semelhantes em sequência para testar a deduplicação.
3. **Fundamentação.** Todo cartão mostra versão e referência localizável. Revisar uma afirmação por vez, incluindo condições e exceções relevantes. Uma CD, um efeito ou uma aplicação sem suporte bloqueia o piloto. Testar casos como alvo sem dados de tamanho e confusão entre a mecânica de agarrar de 2014 e de 2024.
4. **Interface.** Validar em dois monitores e escalas comuns do Windows. Popup sem roubo de foco, som ou mensagem ao Discord. Histórico permite recuperar cartão expirado e limpar a lista. Silencioso registra cartões elegíveis só em RAM. Verificar que ocultar janelas retira o conteúdo visível em compartilhamento no cenário testado.
5. **Privacidade e instalação.** Instalar em VM limpa sem rede, preparar o modelo a partir de arquivo verificado e executar um replay. Repetir em chamada com acesso à rede bloqueado apenas para o Whisper, mantendo o Discord conectado. Antes da confirmação, só usar teste sintético. Após pausar ou encerrar, verificar fechamento da fonte, invalidação de tarefas e ausência de novas notificações. Inspecionar tráfego, arquivos e logs para verificar ausência de envio e gravação de conteúdo pelo Whisper. Encerramento remove o histórico volátil. Testar mudança de fonte, revogação e novo participante com a mesa de ensaio.

## Métricas técnicas

As metas são hipóteses de aceitação. A referência inicial é um notebook Windows 11 x64 com CPU de quatro núcleos, 16 GB de RAM e sem depender de GPU dedicada, além da máquina de desenvolvimento. Registrar CPU, modelo, versão do Windows, energia, periféricos, ASR e modo de captura. Medir com Discord, VTT e app abertos, comparando com uma rodada sem Whisper.

- **Latência de ponta a ponta.** Mediana ≤ 2,5 s e p95 ≤ 5 s do fim da evidência audível mínima até o cartão renderizado, entre alertas entregues. Decompor em VAD, ASR, política e UI. Eventos descartados por prazo aparecem separadamente na cobertura e nos motivos de supressão. Registrar também quando a ação foi resolvida antes do cartão.
- **Qualidade do ASR.** Medir WER por condição acústica e taxa de preservação de termos críticos, incluindo negações e nomes de mecânicas. Meta inicial de ≥ 90% de termos críticos preservados nos trechos claros. Publicar resultado separado para sobreposição e ruído. WER serve ao diagnóstico. O critério principal é seu efeito na decisão.
- **Correção mecânica.** ≥ 98% dos cartões auditados integralmente corretos e 100% com referência verificável. Regra fabricada, edição incorreta ou opção descrita como obrigatória é erro crítico e bloqueia expansão, independentemente da taxa.
- **Cobertura oportuna.** ≥ 50% dos eventos elegíveis recebem cartão válido dentro da janela em replay de holdout, contando perdas por classificação, atraso, cooldown e ausência de dados. Rotular elegibilidade antes de ver saídas. Reportar também a cobertura antes da política para identificar o que o limite de alertas exclui.
- **Silêncio correto.** ≤ 5% dos casos negativos anotados disparam um cartão em replay. Separar hipótese, correção, negação, conversa paralela, casos fora do pacote e falsos positivos em silêncio. Registrar também taxa por hora em gravações longas para captar disparos fora dos exemplos anotados.
- **Recursos e estabilidade.** CPU incremental média ≤ 15 pontos percentuais da capacidade total e RSS/working set somado de app e worker ≤ 1,5 GiB no p95, em ensaio de 2 h. Medir pico, crescimento entre sessões, uso de GPU se habilitada e perda de áudio. Meta de nenhuma interrupção de chamada atribuível ao app e ≥ 99% de tempo ativo sem lacuna atribuível ao pipeline em chamada estável.
- **Custo.** US$ 0/h de APIs. Medir o consumo de energia incremental por hora de sessão, incluindo silêncio. Registrar modelo, quantidade de fontes e perfil de hardware. Converter em R$/h com a tarifa informada. [Método de estimativa](TECHNICAL_RESEARCH.md#infraestrutura-e-custo-por-hora)

## Métricas de experiência

- **Relevância.** ≥ 80% dos cartões avaliados pelo mestre são úteis e ≤ 15% irrelevantes. “Chegou tarde” é uma categoria própria. Mostrar a taxa de cartões sem avaliação. Se menos de 60% receberem avaliação, tratar o resultado como inconclusivo e usar debrief com amostra de cartões.
- **Frequência.** Até 4 popups em uma janela móvel de 1 h no perfil padrão e até 2 no conservador. Reportar distribuição por sessão, incluindo sessões sem popup e cartões consultados no modo silencioso. Janelas sem eventos elegíveis podem ter zero alertas.
- **Distração.** Mediana ≤ 2 em escala de 1 a 5, com 1 para “não interrompeu” e 5 para “interrompeu muito”. No debrief, separar distração visual, troca de foco, atraso e erro.
- **Onboarding.** Pelo menos 80% dos mestres iniciam a primeira sessão sem intervenção do pesquisador. Meta de mediana ≤ 5 min do primeiro uso com modelo preparado à captura ativa. Registrar download e instalação separadamente, além de recusas e dificuldades de consentimento.

## Protocolo de validação

Começar com um conjunto de desenvolvimento e um holdout por mesa ou gravação, evitando que frases vizinhas vazem entre eles. Preparar no holdout pelo menos 50 eventos elegíveis, 100 casos negativos anotados e uma hora de conversa contínua com trechos sem eventos. Rotular categoria, contexto, momento em que a evidência fica suficiente, resolução e regras aplicáveis. Duas pessoas podem revisar uma amostra quando possível. Para um desenvolvedor individual, pedir ao mestre revisor que julgue os casos controversos e os cartões sem ver qual ASR gerou o resultado.

Rodar primeiro em modo de observação com saída oculta e, após revisão, em seis sessões de pelo menos três mesas consentidas. Se viável, alternar popup e histórico silencioso em sessões diferentes de uma mesma mesa, anotando perfil e ordem. Coletar contagens e tempos com exportação opcional e sem texto de sessão. Qualquer uso de gravação real para replay tem autorização, armazenamento e prazo próprios. Inspecionar casos em que uma regra certa chegou tarde ou repetiu uma decisão do mestre.

Os seis encontros são um piloto de decisão. Informar contagens e denominadores por categoria, mesa e hardware, além de incerteza quando o volume permitir. Se a cobertura ou relevância falhar, ajustar o detector com a amostra de desenvolvimento e usar um novo holdout. Se houver poucos alertas avaliáveis, ampliar a amostra antes de concluir. Só ampliar o piloto depois dos critérios de privacidade, erros críticos, latência e experiência. [Plano por fases](ROADMAP.md)
