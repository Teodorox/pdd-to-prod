# Padrão de automações

Este repositório é um template padronizado de robôs de **extração de dados via web** em Python: o robô navega no sistema, extrai as informações e as disponibiliza (arquivo em pasta de rede ou banco de dados) para a área consumir. Todo código e documento gerado DEVE seguir as regras abaixo. Responda em português.

## Princípios

1. **Determinístico em produção.** Nenhuma chamada a LLM/IA em runtime. A IA ajuda só na documentação e no desenvolvimento.
2. **Dado errado é pior que dado nenhum.** Na dúvida, o robô para, guarda evidências e notifica. Nunca entrega uma extração incompleta ou suspeita.
3. **Sem autocorreção.** Nada de seletor alternativo automático, fallback silencioso ou `try/except` que esconda falha.
4. **Não inventar.** Na documentação, o que não foi dito vira dúvida registrada. No código, o que não está no PDD também.

## Fluxo de trabalho (nesta ordem)

1. **Transcrição** da call com o cliente em `docs/transcricao/`, ou o **PDD que o cliente já entregou** em `docs/documento_cliente/` (convertido com `uv run python -m core importar-documento <arquivo>.docx`). As duas pastas ficam fora do git.
2. **`/gerar-pdd`**: gera o `docs/pdd.md` e o `docs/duvidas.md`. Ponto incerto vira `[DÚVIDA D-xx]` no PDD e uma linha em `duvidas.md`.
3. **Revisão humana**: a pessoa confere o PDD contra a call e responde as dúvidas. Depois roda **`/aplicar-respostas`**. Repete até zerar.
4. **`/preparar-envio-pdd`**: gera o `.docx` e o e-mail para o cliente aprovar. A pessoa envia.
5. **`/registrar-aprovacao`**: a pessoa cola a resposta do cliente. Aprovado segue; reprovado reabre o PDD.
6. **`/analisar-tecnica`**: decide o motor do robô (navegador, requests, híbrido ou download) em `docs/analise_tecnica.md` e diz quais insumos a pessoa entrega (ex.: `.har` em `docs/requisicoes/`).
7. **`/nova-automacao`**: só depois de `uv run python -m core checar-pdd` e `checar-analise` passarem (PDD `aprovado`, nenhuma dúvida pendente e motor decidido).
8. **`/revisar-automacao`**, depois homologação com `DRY_RUN=true` e **`/registrar-homologacao`** quando a área validar a saída.
9. **Produção**: `scripts/agendar.ps1 instalar` (cria a tarefa no Agendador de Tarefas do Windows).

**Fases.** Cada etapa acima termina registrando a fase com `uv run python -m core concluir-fase <fase> --obs "..."` (ou `reabrir-fase`), que confere o pré-requisito antes de aceitar. O histórico fica em `docs/fases.json`. Nunca edite esse arquivo à mão e nunca contorne um RECUSADO: mostre o motivo e pare. Para saber onde o robô está e o próximo passo: `uv run python -m core fases` (no terminal) ou o painel `docs/fases.html`, refeito a cada fase registrada (`core fases --abrir` abre no navegador).

**Padrões da área.** Todo `.md` em `docs/padroes/` (ex.: o documento de boas práticas de Python da área) vale no desenvolvimento e na revisão: estilo, nomes, organização e documentação do código. Os Princípios acima prevalecem. Em conflito entre os dois, não escolha em silêncio: siga o template e aponte o conflito no final da resposta.

## Documentação (PDD)

- Siga as seções de `docs/pdd.md`. Se a área tiver um modelo padrão, o `pdd.md` deve espelhar esse modelo.
- Use só o que está na transcrição ou nas respostas das dúvidas. Nunca suponha sistema, tela, campo, regra, volume ou prazo.
- Cada dúvida tem ID sequencial (`D-01`), o trecho da transcrição que a gerou, uma sugestão e quem responde (`dev` ou `cliente`).
- Status do PDD: `rascunho` → `em_validacao` → `enviado` → `aprovado` | `reprovado`. Só uma pessoa muda para `enviado`, `aprovado` ou `reprovado`.
- Nunca copie dado pessoal ou de cliente final (CPF, conta, nome de correntista, valores reais) para o PDD, as dúvidas, o código ou os testes. Use exemplos fictícios.

## Estrutura

```
core             # pacote automacao-core, instalado no .venv (não fica na pasta do robô). Nunca copie nem altere: melhoria vai para o repositório do template, em nova versão
scripts/         # instalar.ps1, executar.ps1, agendar.ps1. Do padrão: renovados por `uv run automacao atualizar`, não alterar por robô
.github/, GUIA.md, docs/modelos/  # também do padrão (renovados pelo `atualizar`)
projeto/
  config.py      # ProjetoSettings(Settings): campos específicos, lidos do .env
  modelos.py     # Item de entrada (herda core.runner.Item, `id` estável) e modelo da linha extraída
  entrada.py     # leitura/validação da entrada (arquivo, parâmetros, banco)
  pages/         # Page Objects: os ÚNICOS lugares com seletores (motor navegador)
  api/           # clientes HTTP: os ÚNICOS lugares com URLs de endpoint e payloads (motor http/hibrido)
  flows/         # regra de negócio: usa Page Objects, nunca seletores
  main.py        # entrypoint: logs, entrada, destino da saída, core.runner.executar
docs/
  pdd.md         # PDD (fonte da verdade do que construir)
  duvidas.md     # dúvidas do PDD e respostas
  analise_tecnica.md  # motor do robô e por quê (gerado por /analisar-tecnica)
  padroes/       # padrões de desenvolvimento da área (boas práticas de Python)
  requisicoes/   # .har gravado pelo dev (NÃO versionado, nunca ler) e o resumo .resumo.md (sem valores)
  fases.json     # histórico das fases do robô (gerado por `core concluir-fase`, não editar)
  fases.html     # painel de fases gerado a partir do fases.json (não versionado, não editar)
  transcricao/   # transcrições das calls (não versionado)
  modelos/       # modelo do e-mail de envio, Word da empresa, prompt do M365 Copilot
  documento_cliente/  # PDD/passo a passo que o cliente entregou (.docx) e o .md convertido (não versionado)
  screenshots/, recordings/   # prints e gravações do codegen (contexto; NÃO versionados: dados reais e o login digitado)
tests/           # pytest; sites simulados em tests/<nome>/index.html servidos localmente
```

## Escolha da ferramenta (motor)

O motor é decidido em `/analisar-tecnica` e registrado em `docs/analise_tecnica.md`. Não troque o motor durante o desenvolvimento: se ele parecer errado, pare e volte à análise.

| Motor | Quando | Código |
|---|---|---|
| `download` | O sistema já gera o relatório com os campos do PDD | `core.runner.executar` + `BasePage.baixar` |
| `http` | Telas alimentadas por endpoints JSON e login reproduzível por requisição | `core.runner.executar_http` + `projeto/api/` |
| `hibrido` | Dados em endpoints JSON, mas login só pela tela (SSO, 2FA, CAPTCHA) | `executar` + `sessao_http_do_navegador(page.context)` + `projeto/api/` |
| `navegador` | Dados só na tela (HTML do servidor, sem API) | `executar` + Page Objects |

**pyautogui** (`core.desktop`): só para o que não é web (app desktop, diálogo nativo do Windows).

Nunca abra um arquivo `.har`: ele tem cookies, tokens e dados reais. Use o resumo de `uv run python -m core resumir-har`.

Selenium: só em automações legadas já existentes. Código novo usa Playwright.

## Page Objects (`projeto/pages/`)

- Uma classe por tela, herdando `core.base_page.BasePage`, com `caminho` relativo a `BASE_URL`.
- Locators declarados no `__init__` como atributos (`self.botao_consultar = page.get_by_role(...)`).
- Prioridade de seletor:
  1. `get_by_role(role, name=...)`
  2. `get_by_label(...)`, `get_by_placeholder(...)`, `get_by_text(...)`
  3. `get_by_test_id(...)`
  4. CSS estável (id, atributo `name`, `data-*`)
  5. XPath: último recurso, com comentário explicando por quê
- Proibido: seletores com índice posicional (`nth-child`, `nth(3)`), classes CSS geradas (`.css-1x2y3z`), XPath absoluto.
- Sobrescreva `aguardar_carregar()` esperando um elemento que prove que a tela está pronta.
- Use os métodos da base (`clicar`, `preencher`, `ler_texto`, `selecionar`, `esperar_visivel`) com uma `descricao` de negócio. Eles geram o log.
- Tabelas: `ler_tabela(locator, descricao)` (dicts por cabeçalho). Paginação: `percorrer_paginas(...)` com um indicador de página que muda a cada troca. Downloads: `baixar(...)`.
- Converta na própria page: `core.texto.valor_brl` (→ `Decimal`), `data_br` (→ `date`), `somente_digitos`.
- Campos sensíveis (senha, token, CPF completo): `preencher(..., sensivel=True)`.
- Métodos retornam dados tipados (modelo pydantic/dataclass), não dicts soltos.

## Robô HTTP (`projeto/api/`, motor `http` ou `hibrido`)

- Uma classe por grupo de endpoints (ex.: `ContratosApi`), recebendo a `SessaoHttp` no `__init__`. Caminhos relativos a `BASE_URL` (a sessão junta), genéricos e constantes da classe.
- Chame com `sessao.json_ok(metodo, caminho, ...)`: status fora de 2xx ou resposta que não é JSON (tela de login, sessão expirada) é erro, nunca fallback.
- Valide a resposta INTEIRA num modelo pydantic antes de usar (`Modelo.model_validate(dado)`). Campo novo, faltando ou com tipo diferente = contrato mudou = falha.
- Converta valores como na tela: `Decimal` para dinheiro (nunca `float`; o `json_ok` já devolve números decimais como `Decimal`), `date` para datas.
- Paginação: siga o total ou o "próxima página" que a API devolve até o fim, e confira o total com `execucao.conferir`. Nunca pare por "página veio vazia" sem a API confirmar o fim.
- Login: na função `preparar(sessao)`. Usuário e senha do `.env` (`SecretStr`). Token, cookie e CSRF vêm da resposta do login; nunca fixos no código, nos testes ou nos docs. Reproduza só os cabeçalhos que a API exige (anotados na análise); não imite um navegador para contornar bloqueio (WAF, antibot): se o sistema bloquear, volte à análise.
- Sem `verify=False`. Certificado interno: `SessaoHttp(verificar_tls="<caminho do .pem>")` via `criar_sessao`, com o caminho no `.env`.
- Nunca logue URL com token, payload de login nem resposta inteira. Log de negócio ("consulta da agência X: 120 registros").
- Retry: só o automático de GET da `SessaoHttp`. POST que altera algo é ação crítica (`execucao.acao_critica`).

## Fluxos (`projeto/flows/`)

- Assinatura: `def extrair_x(page: Page, execucao: ExecucaoItem, item: MeuItem, *, destino: Destino) -> None` (motor `http`: `sessao: SessaoHttp` no lugar de `page`). Em `main.py`, passe com `functools.partial(extrair_x, destino=...)`.
- Login e preparação única vão em uma função separada, passada como `preparar=` para `executar`.
- Nunca use `page.locator(...)` nem `sessao.get(...)` aqui. Se precisar de um elemento ou endpoint, crie no Page Object ou no cliente de `projeto/api/`.

## Qualidade da extração

- Cada linha extraída é um modelo pydantic (`projeto/modelos.py`) com tipos certos (`date`, `Decimal`, `str` com `min_length` quando obrigatório). A ordem dos campos é a ordem das colunas da saída.
- **Completude**: antes de entregar, prove que veio tudo. Use `execucao.conferir("total de registros", total_da_tela, len(linhas))` e, quando a tela informar, a soma dos valores. Use também `execucao.validar(...)` para regras como "sem documento repetido".
- Consulta sem registros é resultado válido só se a tela disser isso explicitamente (total 0, mensagem de "nenhum registro"). Tabela vazia sem essa confirmação é erro.
- Nunca capture `ValidacaoFalhou`, nunca "limpe" ou descarte linhas que não validam. Falhe.

## Saída (`core.saida`)

- Destino definido no PDD: `DestinoCsv` (pasta de rede), `DestinoExcel` (extra `excel`) ou `DestinoBanco` (extra `banco`, tabela já existente).
- Grave SEMPRE via `execucao.entregar(destino, linhas)`, no fim do fluxo, depois de todas as validações. Ele respeita `DRY_RUN` e registra a quantidade no estado.
- Cada item grava a sua parte (chave = `item.id`). Reprocessar substitui, nunca duplica. A gravação é atômica.

## Ações que alteram o sistema (raro em extração)

Se o robô precisar clicar em algo que altera o sistema e não pode ser desfeito (aprovar, enviar, baixar título, excluir):
- SEMPRE via `execucao.acao_critica("descrição", funcao)`. Ela executa uma vez, marca o ponto sem volta no estado e respeita `DRY_RUN` (retorna `None`: trate e saia do fluxo).
- ANTES, confira na tela os dados relevantes com `execucao.conferir`. DEPOIS, valide o resultado e guarde a prova com `execucao.registrar`.
- Nunca coloque retry, loop ou `try/except` em volta de uma ação crítica.

Gerar relatório, exportar ou filtrar não é ação crítica.

## Agendamento

- O robô é agendado no **Agendador de Tarefas do Windows** pelo `scripts/agendar.ps1`, a partir de `AGENDA_*` no `.env` (um gatilho por horário). A tarefa roda `python -m core execucao-agendada`, que cuida de timeout, horário perdido, sinal de vida e notificação. Não crie a tarefa à mão, não crie loops de espera nem agendamento no código do projeto.
- `projeto/main.py` roda UMA execução e termina, com código de saída 0 (sucesso) ou 1 (falha).
- Monitoramento central (início, itens, fim, falha, heartbeat) é automático pelo `core` quando `MONITOR_URL` está no `.env`. Não grave log de execução no banco por conta própria no projeto.

## Esperas e tempo

- Proibido `time.sleep` e `page.wait_for_timeout`. Espere por estado: `expect(locator).to_be_visible()`, `to_have_text`, `page.wait_for_url`, `page.expect_response`.
- Timeouts vêm de `TIMEOUT_MS`; só sobrescreva pontualmente e com comentário.

## Erros e retry

- Não trate exceções no fluxo. O `core.runner` captura, salva evidências (tela, HTML, trace), marca o estado e notifica.
- Retry automático só existe para GET HTTP (já embutido em `SessaoHttp`). Itens com erro são tentados de novo na PRÓXIMA execução, pelo próprio runner, até `MAX_TENTATIVAS_ITEM`.

## Entrada e estado

- Valide a entrada INTEIRA com pydantic antes de começar (ver `projeto/entrada.py`).
- `Item.id` deve ser estável e único (ex.: agência + competência, nº do contrato), nunca o número da linha. É o que garante não extrair duas vezes e substituir a saída certa ao reprocessar.

## Configuração e segredos

- Tudo configurável vai em `ProjetoSettings` + `.env.example` (com valor fictício). Segredos (senha, URL de banco com senha) como `SecretStr`.
- Nunca escreva credenciais, URLs de produção com token ou dados reais no código, nos testes ou em docs/.

## Logs

- Use `logging` (nunca `print`). Logue eventos de negócio (consulta feita, N registros extraídos), não detalhes de implementação.
- Nunca logue senha, token ou dado sensível completo.

## Testes

- pytest, sem mocks do Playwright nem do requests. Simule o site em `tests/<nome>/index.html` (ver `tests/portal_fake`) e sirva pelo fixture `portal_url`. Robô HTTP: simule a API com o fixture `api_fake` (rotas → JSON fictício no formato do resumo das requisições).
- Cubra: caminho feliz (com paginação, se houver), consulta sem registros, total divergente bloqueando a saída, DRY_RUN e falha no login.
- Rode com `uv run pytest`. Lint: `uv run ruff check . && uv run ruff format .`

## Estilo

- Python 3.11+, type hints em tudo, `str | None` em vez de `Optional`.
- Nomes de domínio em português (`movimentacao`, `agencia`, `competencia`), consistentes com o sistema automatizado.
- Gerenciador de pacotes: `uv` (nunca pip direto).
