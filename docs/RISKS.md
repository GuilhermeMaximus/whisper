# Whisper — Registro de riscos

Impacto e probabilidade são estimativas anteriores aos testes. “Alto” em impacto indica risco à confiança, à privacidade ou à hipótese central. “Médio” em probabilidade indica um cenário plausível que a bancada ainda precisa reproduzir. Rever as avaliações após as fases 0 e 5.

## Produto e qualidade

### R01 · Alertas irrelevantes ou intrusivos

**Impacto alto · probabilidade alta.** Termos mecânicos aparecem em hipóteses, piadas e decisões já tomadas. Mitigar com contexto recente, vetos, prazo, deduplicação, modos de frequência e feedback. Validar com holdout negativo e debrief sobre interrupção. Se os avisos úteis forem raros, analisar a cobertura junto da taxa de disparos.

### R02 · Regra correta aplicada à situação errada ou mecânica fabricada

**Impacto alto · probabilidade média.** Falta um requisito, a fala indica uma hipótese ou o pacote contém texto de outra edição. Fixar versão, usar condições estruturadas, cartões curados e fonte por afirmação. A inferência se abstém quando a evidência não sustenta a aplicação. Validar com auditoria por afirmação, regressões de edição e cenários com dados ausentes. Uma regra inventada, edição errada ou opção tratada como obrigação suspende a expansão.

### R03 · Cobertura pequena ou baixa adoção

**Impacto alto · probabilidade média.** Os três eventos podem aparecer pouco em mesas reais, ou o mestre pode preferir consultar as regras manualmente. Entrevistar mestres sobre frequência de consulta, observar instalação e rotular oportunidades antes de medir o pipeline. Validar eventos por hora, repetição de uso e percepção de valor. Se faltar ocorrência real, trocar categorias antes de adicionar sistemas.

### R04 · Aviso aparece para jogadores

**Impacto alto · probabilidade média.** Compartilhamento de desktop, notificações na tela ou outra pessoa no mesmo computador podem expor o cartão. Usar janela local, controle manual para ocultar todas as janelas e ausência de áudio. Testar no Discord com compartilhamento de tela e de janela. A exclusão de captura do Windows é complementar e não substitui o controle manual. [SetWindowDisplayAffinity](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity)

## Engenharia e operação

### R05 · Latência e backlog

**Impacto alto · probabilidade alta.** ASR mais lento que a chegada de fala ou endpointing que aguarda silêncio prolongado produz lembrete atrasado. Limitar filas, usar timestamps de origem, descartar trabalho vencido e sinalizar lacunas. Validar p95 por etapa, cobertura oportuna, cauda sob sobreposição e recuperação após saturação.

### R06 · Transcrição incorreta ou identificação falsa de locutor

**Impacto alto · probabilidade alta.** Sotaques, termos em inglês e falas simultâneas podem apagar uma negação ou confundir pergunta do mestre com sugestão de jogador. Preservar a origem do microfone, restringir o vocabulário de detecção e suprimir quando qualidade ou papel forem decisivos e incertos. Medir WER, termos críticos e erros de intenção em corpus PT-BR por condição acústica.

### R07 · Consumo de recursos prejudica a chamada

**Impacto alto · probabilidade média.** Dois streams e modelos grandes podem competir com Discord e VTT. Medir CPU, memória, GPU e energia sob carga, testar modelo quantizado, limitar paralelismo e descarregar o worker ao encerrar. Validar com ensaio de 2 h no notebook de referência e comparar com a chamada sem Whisper.

### R08 · Captura de Discord indisponível ou incorreta

**Impacto alto · probabilidade média.** Mudança de PID, dispositivos e configurações de voz podem gerar silêncio ou som errado. Fixar o escopo a Discord desktop em Windows 11 x64, testar a árvore de processos e usar medidor e conferência antes de retomar. Validar com outro app emitindo áudio, USB/Bluetooth, reinício, suspensão, mídia compartilhada e microfone bloqueado. Evitar fallback amplo. [Loopback por processo](https://learn.microsoft.com/en-us/samples/microsoft/windows-classic-samples/applicationloopbackaudio-sample/)

### R09 · Modelo ou dependência local indisponível

**Impacto alto · probabilidade média.** Pesos ausentes, incompatíveis ou corrompidos impedem a transcrição. Verificar versões e integridade antes da captura e orientar recuperação com arquivo local. Validar em VM offline com instalação limpa, arquivo truncado, modelo incompatível e falha de inicialização do worker.

### R10 · Manutenção e distribuição acima da capacidade individual

**Impacto médio · probabilidade média.** UI, binários nativos, modelos, permissões, instalador e pacotes de regras podem exigir ciclos distintos de atualização. Manter uma plataforma, dependências fixadas, build verificável, smoke test de instalação e atualização em VM limpa. Registrar regressões por versão do Windows, Discord e ASR. Adiar suporte novo se a matriz atual já demandar manutenção desproporcional.

## Privacidade, contratos e conteúdo

### R11 · Escuta de pessoas que não concordaram

**Impacto alto · probabilidade média.** Um participante entra durante a sessão ou revoga a concordância. Captura por processo não fornece lista de participantes e pode incluir outros sons do Discord. Usar autorização por sessão, roteiro claro, pausa imediata acessível, confirmação após mudança e aviso sobre a abrangência da fonte e do microfone. Validar com teste de chegada e revogação durante ensaio. Se os mestres não conseguirem manter o procedimento, limitar o piloto a mesas fechadas estáveis e reavaliar antes de oferecer o produto a grupos abertos.

### R12 · Exposição ou retenção indevida de dados locais

**Impacto alto · probabilidade média.** Conteúdo pode vazar por logs, dumps, paginação, comunicação local com o worker ou gravações de teste. Usar RAM limitada, restringir pipes e manter o fluxo normal sem gravação. Excluir dados de teste no prazo definido, limitar acesso, verificar tráfego e arquivos e testar cancelamento em todas as saídas. Antes de piloto comercial, identificar controlador e operadores, base legal, prazos e direitos dos titulares. O consentimento operacional da mesa integra esse desenho. [LGPD, texto atualizado](https://www2.camara.leg.br/legin/fed/lei/2018/lei-13709-14-agosto-2018-787077-normaatualizada-pl.html)

### R13 · Redistribuição de conteúdo ou marca sem direitos

**Impacto alto · probabilidade média.** Materiais públicos ou traduções comerciais podem ser acessíveis com condições diferentes. Fixar o SRD 5.2.1, registrar fonte e licença por entrada, manter atribuição e indicar adaptações próprias. Verificar pacotes de modelos, fontes e assets antes de distribuir. Validar rastreabilidade no instalador e na UI. Antes de lançamento comercial, fazer busca de marca do nome Whisper e avaliar a distinção do nome do projeto de ASR. [SRD oficial](https://www.dndbeyond.com/srd) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

### R14 · Integração futura com bot incompatível com política ou criptografia

**Impacto médio no plano atual e alto se virar fonte principal · probabilidade média.** Recepção de áudio, associação a usuário e reconexão dependem do protocolo e da biblioteca. A visibilidade do bot e a permissão de canal cobrem apenas parte da autorização. Se a opção avançar, validar DAVE e o fluxo em ambiente controlado e revisar o uso de voz e dados com os termos vigentes. Interromper se o fluxo exigir API privada ou se a autorização permanecer indefinida. [Conexões de voz](https://docs.discord.com/developers/topics/voice-connections) · [Developer Policy](https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy)

## Condições para ampliar o piloto

Captura seletiva verificada, consentimento operacional praticável, ausência de erro mecânico crítico, nenhuma persistência ou transmissão imprevista e metas mínimas de latência e experiência no recorte. Revisar primeiro o maior desvio medido. [Escopo e critérios](MVP_SCOPE.md) · [Plano de execução](ROADMAP.md)
