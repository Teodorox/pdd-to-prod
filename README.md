# Template de automação

Base padronizada para robôs de **extração de dados via web** em Python (Playwright e requests; pyautogui só se preciso). O robô navega no sistema, extrai as informações, confere se veio tudo e disponibiliza o resultado para a área, em arquivo na pasta de rede ou no banco de dados.

A IA (GitHub Copilot ou Microsoft 365 Copilot) entra **só na documentação e no desenvolvimento**, guiada pelas regras em [.github/copilot-instructions.md](.github/copilot-instructions.md). Em produção, o robô roda de forma determinística, sem IA.

O que o template já garante:

- **Do PDD ao código com trava.** O Copilot gera o PDD a partir da transcrição da call e lista o que não ficou claro. O desenvolvimento só começa com o PDD aprovado e sem dúvidas pendentes (`checar-pdd`).
- **Extração completa ou nada.** O robô confere o total informado pela tela contra o que extraiu. Se divergir, não grava a saída.
- **Saída segura.** Gravação atômica em CSV, Excel ou banco. Reprocessar uma consulta substitui os dados dela, nunca duplica.
- **Não extrai o mesmo item duas vezes.** O estado de cada item fica em SQLite.
- **Monitoramento central.** Cada execução, com sinal de vida durante ela e a próxima execução prevista, vai para o banco de monitoramento (MySQL). Horário que passa sem o robô começar vira alerta.
- **Agendamento pelo Agendador de Tarefas do Windows.** O `agendar.ps1` cria a tarefa a partir dos horários do `.env`, roda sem usuário logado e cuida de timeout, horário perdido e notificação.
- **Falha com evidência.** Em cada erro ficam salvos o traceback, o screenshot, o HTML, a URL e o trace do Playwright, e sai uma notificação (log, Teams ou e-mail).
- **Nenhuma autocorreção.** Quem corrige é uma pessoa, com ajuda do Copilot.

## Requisitos e plataformas

| O quê | Para quê |
|---|---|
| Windows 10/11 ou Windows Server | VMs onde os robôs rodam (agendamento pelo Agendador de Tarefas) |
| [uv](https://docs.astral.sh/uv/) e Python 3.11+ | Ambiente e dependências (o uv instala o Python) |
| Playwright + Chromium | Navegação (motor `navegador`, `hibrido` e `download`) |
| `requests` | Robôs por requisição (motor `http`) |
| VS Code com GitHub Copilot | Prompts de documentação e desenvolvimento em `.github/prompts/` |
| Opcional: MySQL | Monitoramento central (`MONITOR_URL`) |
| Opcional: SMTP e/ou Microsoft Teams (webhook) | Notificação de falhas |

Todas as configurações ficam no `.env` de cada robô. Veja o [.env.example](.env.example): valores de exemplo, nenhum segredo.

## Começando um robô novo

> Passo a passo completo, numerado, da pasta vazia até a produção: [docs/passo_a_passo.md](docs/passo_a_passo.md).

O padrão é distribuído como o pacote **`automacao-core`**, instalado direto do repositório Git (GitHub, GitLab ou outro servidor Git). Cada robô é uma **pasta e um projeto próprios** no seu servidor Git. Este repositório é só o padrão: não se desenvolve robô dentro dele.

```powershell
mkdir extracao-test; cd extracao-test
uv init --bare
uv add "automacao-core @ git+https://<servidor-git>/<grupo>/automacao-template.git@v1.0.0"
uv run automacao iniciar        # cria projeto/, docs/, tests/, scripts/, .github/, .env.example...
uv sync
git init; git remote add origin https://<servidor-git>/<grupo>/extracao-test.git
```

O `core` não é copiado para a pasta do robô: ele fica instalado no `.venv` e o código usa `from core.runner import executar` normalmente. O guia completo (este arquivo) vai junto como `GUIA.md`.

| Na pasta do robô | De quem é | O que acontece no `automacao atualizar` |
|---|---|---|
| `projeto/`, `tests/`, `docs/pdd.md`, `docs/duvidas.md`, `.env.example`, `.gitignore` | do robô | nada: nunca são tocados |
| `.github/` (instruções e prompts do Copilot), `scripts/`, `docs/modelos/`, `GUIA.md` | do padrão | são renovados para a versão instalada. Não edite no robô |

**Saída em Excel ou banco**: inclua o extra na dependência (`automacao-core[excel]`, `automacao-core[banco]` ou `automacao-core[excel,banco]`) e rode `uv sync`.

### Atualizando um robô para uma versão nova do padrão

```powershell
uv add "automacao-core @ git+https://<servidor-git>/<grupo>/automacao-template.git@v1.1.0"
uv run automacao atualizar      # renova prompts, scripts e instruções; mostra o que mudou
uv run pytest
```

Cada robô fica travado na versão do seu `uv.lock`: uma versão nova do padrão não muda nenhum robô em produção até alguém atualizar.

### Mantendo o padrão (quem cuida deste repositório)

1. Faça a melhoria aqui, com testes (`uv run pytest`, `uv run ruff check .`).
2. Suba a `version` no `pyproject.toml` (ex.: `1.1.0`) e faça o commit.
3. Crie a tag: `git tag v1.1.0` e `git push --tags`.

Arquivos que vão para a pasta do robô ficam listados em `core/modelo.py` e no `pyproject.toml` (`force-include`). Ao criar um arquivo novo do padrão, inclua nos dois.

### Rodando o exemplo neste repositório

```bash
uv sync
uv run playwright install chromium   # VM sem internet: veja "Navegador" em Agendamento
cp .env.example .env
uv run pytest
```

Para rodar o exemplo (extração de movimentações num portal fake), use dois terminais:

```bash
uv run python -m http.server 8000 -d tests/portal_fake   # terminal 1
uv run python -m projeto.main                             # terminal 2
```

As consultas saem em `dados/saida/`, uma por arquivo. A agência `9999` falha de propósito: o portal fake informa um total maior do que mostra na tabela, e o robô bloqueia a saída dessa consulta. Veja a pasta `evidencias/` e abra o trace:

```bash
uv run playwright show-trace evidencias/<pasta>/trace.zip
```

## Criando um robô novo

### 1. Documentação (PDD)

1. Crie a pasta do robô com `automacao iniciar` (veja "Começando um robô novo").
2. Salve a fonte do PDD. As duas pastas ficam fora do git, porque têm dados do cliente.
   - **Call com o cliente:** a transcrição em `docs/transcricao/`.
   - **O cliente já mandou o PDD ou o passo a passo (Word):** salve o `.docx` em `docs/documento_cliente/` e converta:
     ```powershell
     uv run python -m core importar-documento docs/documento_cliente/pdd_cliente.docx
     ```
     Sai um `pdd_cliente.md` com o texto na ordem do Word e as imagens em `docs/screenshots/` (`pdd_cliente_01.png`, `_02`...), cada uma marcada no lugar exato do texto. É assim que o Copilot sabe a qual passo cada tela pertence. Veio em PDF? Peça o Word ao cliente; se não houver, abra o PDF no Word, salve como `.docx` e confira antes.
3. No chat do Copilot (modo Agent), rode `/gerar-pdd` indicando a transcrição ou o `.md` do documento do cliente. Mesmo com o PDD pronto, ele reescreve nas seções do padrão e transforma o que faltar em dúvida. Ele preenche o [docs/pdd.md](docs/pdd.md) e lista em [docs/duvidas.md](docs/duvidas.md) tudo o que não ficou claro.
4. Revise o PDD contra o que foi dito na call. Responda as dúvidas na própria tabela (coluna Resposta, Status `respondida`) e rode `/aplicar-respostas`. Repita até não sobrar dúvida.
5. Rode `/preparar-envio-pdd`. Ele gera o `.docx` em `docs/envio/` e o texto do e-mail. Se o Word modelo da área estiver em `docs/modelos/modelo_pdd.docx`, o documento sai com os estilos dele.
6. Envie ao cliente. Quando ele responder, rode `/registrar-aprovacao` e cole a resposta do e-mail. Se for reprovado, os pontos dele viram novas dúvidas e o PDD é reaberto.

Se a transcrição só estiver no Teams, use o [prompt para o Microsoft 365 Copilot](docs/modelos/prompt_m365_copilot.md) e salve o resultado no `pdd.md` e no `duvidas.md`.

### 2. Análise técnica (navegador ou requests?)

Antes de escrever código, decida **como** o robô vai buscar os dados. Ler a tela com Playwright funciona sempre, mas quando o sistema tem endpoints JSON por trás das telas, chamar esses endpoints com `requests` costuma ser muito mais rápido, mais leve e dispensa o Chromium na VM.

1. Confira a trava: `uv run python -m core checar-pdd`.
2. Coloque o documento de boas práticas de Python da área em [docs/padroes/](docs/padroes/README.md) (uma vez por repositório).
3. Salve os prints das telas em `docs/screenshots/`, numerados na ordem do fluxo (`01_login.png`, `02_consulta.png`...). A pasta não vai para o git: prints de sistema real costumam mostrar dados de clientes.
4. Grave o fluxo no ambiente de homologação, já gravando as requisições:
   ```powershell
   uv run playwright codegen <url-homologacao> --target python -o docs/recordings/fluxo.py --save-har=docs/requisicoes/fluxo.har
   uv run python -m core resumir-har docs/requisicoes/fluxo.har
   ```
   Enquanto você faz o processo na janela que abrir (login, consulta, download...), o codegen grava sozinho os cliques no `fluxo.py` e todas as requisições no `.har`. **Feche a janela do navegador** para os arquivos serem gravados; o `resumir-har` é o passo seguinte, rodado à mão.
   - O `.har` tem cookies e dados reais e não vai para o git. O resumo (`fluxo.resumo.md`) só tem a estrutura e é o que o Copilot lê. Detalhes em [docs/requisicoes/](docs/requisicoes/README.md).
   - O `fluxo.py` tem o usuário e a **senha digitados** no login. Por isso `docs/recordings/` também não vai para o git.
5. No Copilot, rode `/analisar-tecnica`. Ele compara os motores (navegador, http, híbrido, download) em desempenho, autenticação, navegação, estabilidade, evidência, segurança, manutenção e instalação, e grava a decisão em `docs/analise_tecnica.md`. Se faltar material, ele diz o que entregar, como obter e onde salvar. Entregue e rode de novo.

| Motor | Quando | Como roda |
|---|---|---|
| `download` | o sistema já gera o relatório | `executar` + `BasePage.baixar` |
| `http` | dados em endpoints JSON e login por requisição | `executar_http`, sem navegador |
| `hibrido` | dados em JSON, mas login só pela tela (SSO, 2FA, CAPTCHA) | `executar` + `sessao_http_do_navegador` |
| `navegador` | dados só na tela | `executar` + Page Objects |

### 3. Desenvolvimento

1. Confira as travas: `uv run python -m core checar-pdd` e `uv run python -m core checar-analise`.
2. No Copilot, rode `/nova-automacao`. Ele segue o motor da análise e os padrões da área.
3. Revise o código. Antes de homologar, rode `/revisar-automacao`.
4. Teste em homologação com `DRY_RUN=true` (extrai mas não grava a saída). Quando a área validar a saída, rode `/registrar-homologacao`.

### Acompanhando as fases

Cada etapa acima registra sozinha a fase concluída (`core concluir-fase`). O comando confere o pré-requisito antes: não registra a aprovação sem o `checar-pdd` passar, nem o desenvolvimento sem a análise técnica decidida ou com testes falhando. O `agendar.ps1 instalar` registra a produção.

```powershell
uv run python -m core fases           # no terminal: a trilha e o próximo passo
uv run python -m core fases --abrir   # o painel docs/fases.html no navegador
```

O painel `docs/fases.html` é refeito a cada fase registrada e se recarrega sozinho a cada 30 segundos. Ele mostra:
- a trilha das 6 fases;
- a fase atual e há quanto tempo o robô está nela;
- o próximo passo;
- o histórico (quem, quando e a evidência de cada fase).

O histórico fica em `docs/fases.json`. Não edite esse arquivo.

### Prompts disponíveis no Copilot (`.github/prompts/`)

| Comando | Para quê |
|---|---|
| `/gerar-pdd` | Gera o PDD e a lista de dúvidas a partir da transcrição da call |
| `/aplicar-respostas` | Aplica no PDD as dúvidas respondidas |
| `/preparar-envio-pdd` | Gera o Word do PDD e o e-mail de aprovação |
| `/registrar-aprovacao` | Registra a resposta do cliente (aprovado ou reprovado) |
| `/registrar-homologacao` | Registra que a área validou a saída |
| `/analisar-tecnica` | Decide o motor (navegador, requests, híbrido, download) e lista os insumos que faltam |
| `/nova-automacao` | Gera o robô a partir do PDD aprovado, da análise técnica, dos prints e das gravações |
| `/nova-pagina` | Cria o Page Object de uma tela |
| `/corrigir-falha` | Diagnostica uma pasta de `evidencias/` e propõe a correção |
| `/revisar-automacao` | Confere o código contra o padrão e o PDD (não altera o código) e registra o fim do desenvolvimento |

O arquivo `.vscode/mcp.json` habilita o **Playwright MCP**. Com ele, o Copilot consegue navegar no sistema durante o desenvolvimento para descobrir seletores reais. Use só em homologação. O servidor pede Node.js e é ativado pelo VS Code na primeira vez que for usado.

## Saída

O destino é decidido no PDD e configurado em `projeto/main.py`:

| Destino | Classe | Instalação |
|---|---|---|
| CSV (`;`, decimal com vírgula, abre direto no Excel) | `DestinoCsv` | já incluso |
| Excel (.xlsx com tipos nativos) | `DestinoExcel` | extra `automacao-core[excel]` |
| Banco de dados (tabela já existente) | `DestinoBanco` | extra `automacao-core[banco]` (já inclui o driver do MySQL; outro banco precisa do driver dele) |

Cada consulta grava a sua parte (arquivo próprio, ou linhas identificadas pela chave no banco). Se uma consulta for reprocessada, os dados dela são substituídos.

## Quando um robô falha

1. A notificação traz o erro e o caminho da pasta de evidências.
2. Abra o trace (`playwright show-trace`) ou rode `/corrigir-falha` no Copilot.
3. Itens que esgotaram as tentativas vão para revisão manual. Depois de entender o problema, resolva pelo CLI:

```bash
uv run python -m core listar --status revisao_manual
uv run python -m core resolver 0001_2026-10 --como pendente --obs "portal corrigido, pode extrair de novo"
```

## Ciclo de vida de um item

| Situação | Status | Na próxima execução |
|---|---|---|
| Sucesso | `concluido` | pulado |
| Falhou (sistema fora, tela mudou, total divergente) | `erro` | tenta de novo, até `MAX_TENTATIVAS_ITEM` |
| Esgotou as tentativas | `revisao_manual` | pulado até alguém resolver |

Se acontecerem `MAX_ERROS_CONSECUTIVOS` erros seguidos, a execução para (provavelmente o sistema está fora ou a tela mudou). Robôs que também **alteram** o sistema (aprovar, enviar) usam `execucao.acao_critica`, que tem regras extras: falha durante a ação vai direto para revisão manual e para a execução.

## Instalando numa VM e agendando

Cada robô é uma pasta independente, com o seu `.env`, estado, logs e tarefa agendada. Numa VM Windows:

```powershell
winget install astral-sh.uv                  # uma vez por máquina (o uv baixa o Python sozinho)
git clone <repositório do robô> C:\Robos\<nome>
cd C:\Robos\<nome>
.\scripts\instalar.ps1                        # cria o .env na 1ª vez; preencha e rode de novo
.\scripts\executar.ps1 -Visivel               # teste vendo o navegador na tela
.\scripts\agendar.ps1 instalar                # como administrador: pede a conta do robô
```

A agenda fica no `.env` do robô:

```ini
AGENDA_DIAS=seg,ter,qua,qui,sex     # ou "todos"
AGENDA_HORARIOS=07:00,13:30
AGENDA_TOLERANCIA_MIN=60            # VM desligada no horário: roda ao voltar se o atraso for até 60 min
AGENDA_TIMEOUT_MIN=240              # execução travada é encerrada (com o navegador) e notificada
```

Como funciona:
- O `agendar.ps1 instalar` cria a tarefa `\Robos\robo-<AUTOMACAO_NOME>` no Agendador de Tarefas, com um gatilho por horário de `AGENDA_HORARIOS` nos dias de `AGENDA_DIAS`. Ela roda com a conta do robô, com ou sem usuário logado.
- A ação da tarefa é `python -m core execucao-agendada`, na pasta do robô. Ela roda o robô num processo separado, com `HEADLESS=true`, e cuida do resto: encerra a execução que passar do timeout, manda o sinal de vida ao monitoramento e notifica falhas.
- **Não crie nem edite a tarefa à mão.** O horário tem que ser o do `.env`, e o core confere a cada disparo. Mudou a agenda? Rode `agendar.ps1 instalar` de novo e a tarefa é recriada.
- VM desligada no horário: a tarefa roda quando a VM volta. Se o atraso passar da tolerância, ela não roda atrasada, só notifica. Rode manualmente com `.\scripts\executar.ps1` se precisar.
- O robô não roda duas vezes ao mesmo tempo: a tarefa não abre uma segunda instância, e o `executar.ps1` rodado durante uma execução agendada não começa e avisa.
- O status (última execução, código de saída, próxima execução) fica em `estado.agenda.json`. Consulte com `.\scripts\agendar.ps1 status`.

| Comando | Para quê |
|---|---|
| `uv run python -m core agenda` | Mostra a agenda do `.env` e as próximas 5 execuções |
| `.\scripts\agendar.ps1 instalar` | Cria ou recria a tarefa (também depois de mudar a agenda ou a senha da conta do robô) |
| `.\scripts\agendar.ps1 status` | Estado da tarefa, última e próxima execução |
| `.\scripts\agendar.ps1 remover` | Tira o robô da agenda e avisa o monitoramento |
| `.\scripts\executar.ps1 [-Visivel] [-DryRun]` | Roda uma vez, agora, fora da agenda |

Cuidados:
- **Navegador:** o `instalar.ps1` coloca o Chromium do Playwright em `navegadores\`, dentro do projeto, e a tarefa acha esse Chromium com qualquer conta. Na VM sem internet, copie o navegador da pasta de rede:
  ```powershell
  .\scripts\instalar.ps1 -Navegadores \\servidor\rpa\ms-playwright
  ```
  - A pasta de rede precisa ter **a versão exata** que o Playwright do `uv.lock` espera (ex.: `chromium-1248` e `chromium_headless_shell-1248`). Se faltar, o script diz qual versão é e como baixá-la.
  - Para abastecer a pasta, numa máquina com internet e com o mesmo `uv.lock`, rode `$env:PLAYWRIGHT_BROWSERS_PATH='\\servidor\rpa\ms-playwright'; uv run playwright install chromium`. Várias versões podem ficar lado a lado nessa pasta.
  - Alternativa sem copiar nada: `CANAL_NAVEGADOR=msedge`, que usa o Edge já instalado na VM. Ele é atualizado pelo Windows, então teste antes de adotar.
- **Conta da tarefa:** use o usuário do robô, que precisa ter acesso à pasta de rede ou ao banco da saída. Se a senha dele mudar, rode `agendar.ps1 instalar` de novo; senão a tarefa para de rodar e o monitoramento acusa `NAO_INICIOU`.
- **Desativar a tarefa no Agendador** tira o robô do ar sem avisar ninguém na hora; ele aparece no monitoramento só no horário seguinte. Para parar de propósito, use `agendar.ps1 remover`.
- Robôs com `pyautogui` (desktop) precisam de tela: a tarefa tem que rodar "somente quando o usuário estiver conectado", numa sessão aberta.

## Monitoramento central

Com `MONITOR_URL` no `.env`, cada robô grava no banco de monitoramento o início, o meio (um evento por item), o fim e as falhas de cada execução. A execução agendada grava um sinal de vida ao começar, a cada 5 min durante e ao terminar, com a próxima execução prevista. O log detalhado continua em arquivo na VM.

Uma view (`vw_robo_saude`) mostra, por robô, se o horário previsto passou sem a execução começar, se ficou sem sinal no meio, travou, foi tirado da agenda ou se a última execução falhou. A implantação está em [docs/monitoramento/README.md](docs/monitoramento/README.md).

Se o banco de monitoramento cair, os robôs continuam rodando. A falta de sinal aparece no monitoramento.

## Acompanhando a execução (DEV e homologação)

| Como | Para quê |
|---|---|
| `.\scripts\executar.ps1 -Visivel` | Abre o navegador na tela, com cada ação mais lenta (`SLOW_MO_MS=300`) |
| `HEADLESS=false` e `SLOW_MO_MS` no `.env` | O mesmo, de forma fixa na máquina de desenvolvimento |
| Debugger do VS Code (F5 em `projeto/main.py`) | Para em breakpoints, com o navegador aberto |
| `$env:PWDEBUG=1; uv run python -m projeto.main` | Playwright Inspector: passo a passo, mostrando o que cada seletor encontra |
| `TRACE=sempre` no `.env` | Guarda o trace de todos os itens, inclusive os que deram certo, para rever depois com `playwright show-trace` |
| `$env:HEADLESS="false"; uv run pytest` | Roda os testes vendo o navegador |

Em produção, a execução agendada força `HEADLESS=true`, porque não há tela.

## Segurança

`evidencias/`, `logs/`, `dados/saida/`, `docs/transcricao/`, `docs/documento_cliente/`, `docs/screenshots/`, `docs/recordings/` e os `.har` de `docs/requisicoes/` podem conter dados sensíveis (e ficam fora do git), como telas e dados de clientes. O trace também guarda o que foi digitado, incluindo senhas na etapa de login. Restrinja o acesso a essas pastas no servidor e defina uma rotina de limpeza.

- Segredos (senhas, URL de banco, webhook) ficam só no `.env` ou num cofre de credenciais, como `SecretStr`. Nunca no código, nos testes ou na documentação.
- Nenhuma IA roda em produção. Nos prompts do Copilot, o conteúdo de transcrições, documentos e e-mails de terceiros é tratado como dado, nunca como instrução.
- O CSV de saída grava os valores exatamente como vieram do sistema. Se um campo de texto puder começar com `=`, `+`, `-` ou `@`, quem abrir no Excel deve abrir como texto (risco de fórmula), já que o robô não altera o dado extraído.
- Encontrou uma vulnerabilidade? Abra uma issue sem detalhes sensíveis ou use o *Private vulnerability reporting* do GitHub.

## Estrutura

```
core/       pacote automacao-core (no robô, instalado no .venv): runner, estado, saída, agendador, monitoramento, evidências, notificação, navegador, http, PDD
scripts/    instalar, executar e agendar (do padrão: renovados por `automacao atualizar`)
projeto/    o robô: config, modelos, entrada, pages/ (navegador), api/ (requests), flows/, main.py
docs/       PDD, dúvidas, análise técnica, padrões da área, transcrições, modelos, prints, gravações e requisições
tests/      pytest + site simulado
```

## Licença

[MIT](LICENSE) © 2026 Teodorox
