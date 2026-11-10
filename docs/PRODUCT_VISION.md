# Whisper — Visão do produto

## Problema e público

Em uma sessão de RPG por voz, o mestre precisa ouvir os jogadores, sustentar a ficção e decidir quando consultar uma regra. Parar para procurar a distância de um salto interrompe a cena. Receber um aviso para cada menção a uma regra também interrompe. O Whisper deve reduzir o tempo gasto nessas consultas sem transferir para o mestre o trabalho de filtrar alertas.

O público inicial são mestres de mesas adultas que jogam em português brasileiro no Discord desktop, em Windows 11 x64, usando D&D 5e com as regras revisadas de 2024. Essa combinação delimita a captura, o vocabulário e a edição a validar. Mesas de 2014, outros sistemas e outras plataformas entram depois de demonstrar valor no recorte inicial.

## Proposta de valor

O Whisper acompanha a conversa com autorização dos participantes e exibe, somente na interface local do mestre, lembretes mecânicos breves com fonte verificável. Todo o processamento do Whisper acontece na própria máquina do mestre, inclusive a transcrição e a consulta de regras. O mestre pode ignorar, dispensar ou abrir a referência. Os participantes recebem o aviso sobre o processamento antes da escuta. O produto deixa narração, interpretação, testes e consequências a cargo do mestre.

Quando alguém declara que vai saltar de um telhado a outro, um cartão pode lembrar que o salto horizontal usa o valor de Força em pés com pelo menos 10 pés de corrida imediatamente antes, que um salto parado cobre metade e que a distância gasta movimento. A fonte é o verbete *Long Jump*. Se a mesa estiver apenas cogitando o salto, ou se a questão for agarrar a borda e a evidência disponível não sustentar uma resposta, o Whisper se abstém dessa parte. O aplicativo pode mostrar a regra de salto sem saber a distância entre os telhados ou a Força do personagem. [SRD 5.2.1, Rules Glossary](https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf)

## Hipóteses que precisam sobreviver ao piloto

1. **Valor.** Há consultas mecânicas recorrentes e demoradas o suficiente para justificar um assistente. Medir uso e utilidade por categoria de regra e pedir exemplos de consultas evitadas.
2. **Timing.** Um lembrete chega depois que a intenção fica clara e antes que o mestre resolva a ação. Medir latência e registrar avisos tecnicamente corretos que chegaram tarde.
3. **Atenção.** A maioria dos avisos entregues é relevante e a experiência continua confortável durante silêncios e conversa fora do jogo. Medir distração e falsos positivos junto da cobertura para distinguir silêncio útil de baixa capacidade de detecção.
4. **Adoção.** O mestre consegue instalar, selecionar a fonte e informar todos os participantes com pouco suporte. Medir quantas mesas conseguem iniciar, quantas desistem e em qual passo.
5. **Distribuição.** O aplicativo atende uma parcela suficiente do público inicial no próprio PC. Comparar modelos e perfis de hardware para definir requisitos mínimos e medir o esforço de instalação. Cobrança e disposição a pagar ficam para depois de validar uso recorrente.

## Jornada da primeira sessão

1. **Instalação.** Abrir um instalador Windows x64 e preparar o modelo local. Se o modelo for distribuído à parte, o onboarding orienta a seleção do arquivo já obtido e verifica sua integridade. Uma checagem orienta quando falta espaço ou a máquina está fora do recorte.
2. **Edição.** Selecionar “D&D 5e · regras de 2024 · SRD 5.2.1”. A tela explica que a cobertura inicial é parcial e mostra as categorias cobertas.
3. **Fonte.** Selecionar Discord desktop e, opcionalmente, o microfone do mestre. Conferir medidores separados durante uma prévia autorizada, com um colega falando e o mestre respondendo. A interface identifica fonte indisponível, permissão bloqueada e silêncio.
4. **Aviso aos participantes.** O mestre lê ou compartilha um texto curto com finalidade, processamento no PC, retenção e como pedir pausa. Confirma que todos concordaram antes da prévia com voz real. Se alguém entrar, trocar de canal ou retirar a concordância, o mestre pausa e reconfirma antes de retomar. O loopback não detecta a lista de participantes de forma confiável, então esse passo é manual e precisa ser observado no piloto.
5. **Sessão.** O indicador na bandeja mostra escuta ativa. Os avisos aparecem sem som nem mudança de foco. O modo discreto mantém os cartões no histórico e permite ao mestre abrir a janela quando quiser. Antes de compartilhar a tela inteira, o mestre pode ocultar popups e fechar a janela do histórico.
6. **Consulta.** O mestre abre o histórico recente, expande um cartão para conferir a fonte e, se quiser, marca “Útil”, “Irrelevante” ou “Chegou tarde”. O aplicativo permite limpar o histórico a qualquer momento.
7. **Encerramento.** “Encerrar” interrompe a captura e limpa áudio, transcrição e histórico volátil. O piloto pede uma avaliação curta, com coleta separada e opcional de métricas sem conteúdo de fala.

O teste de fonte reduz a chance de descobrir silêncio no meio da sessão. A seleção explícita de edição evita confundir mesas de 2014 e 2024. A etapa de consentimento é a maior fricção social. O piloto deve verificar se o roteiro cabe em poucos segundos e se os mestres lembram de pausar quando a composição da mesa muda.

Leia também [requisitos](REQUIREMENTS.md) e [escopo e métricas do MVP](MVP_SCOPE.md).
