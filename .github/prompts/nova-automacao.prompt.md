---
agent: agent
description: Gera o robô a partir do PDD aprovado e da análise técnica (motor navegador, requests, híbrido ou download)
---

Crie o robô descrito no [PDD](../../docs/pdd.md) seguindo [as regras do padrão](../copilot-instructions.md), o motor da [análise técnica](../../docs/analise_tecnica.md) e os padrões da área em `docs/padroes/`.

**Antes de tudo**, rode `uv run python -m core checar-pdd` e `uv run python -m core checar-analise`. Se algum falhar, PARE: mostre os bloqueios e não gere código. O desenvolvimento só começa com o PDD aprovado, sem dúvidas pendentes e com o motor decidido (se faltar a análise, o próximo passo é `/analisar-tecnica`).

Contexto disponível:
- PDD e respostas das dúvidas: `docs/pdd.md`, `docs/duvidas.md`
- Análise técnica: `docs/analise_tecnica.md` (motor, endpoints ou telas, riscos)
- Padrões da área: todo `.md` em `docs/padroes/` (estilo, nomes, organização). Os Princípios do padrão prevalecem; conflito vai para o relatório final
- Requisições: `docs/requisicoes/*.resumo.md` (nunca abra o `.har`)
- Telas em `docs/screenshots/` (os nomes dos arquivos indicam a ordem do fluxo)
- Gravações do `playwright codegen` em `docs/recordings/`, que mostram os seletores reais. Elas têm o usuário e a senha digitados no login: use só os seletores, nunca copie valores da gravação para o código, os testes ou os docs
- Se o servidor MCP do Playwright estiver ativo, navegue no sistema (ambiente de homologação) para confirmar os seletores. Só leitura: nunca execute ações que alterem o sistema.

Passos:
1. Leia o PDD, a análise técnica, os padrões da área, as telas, as gravações e o resumo das requisições. Liste: o motor, as telas ou endpoints do fluxo, o item de entrada e seu `id`, os campos extraídos (seção "Dados extraídos"), os controles de qualidade e o destino da saída.
2. Siga o motor da análise. Se, ao ler o material, ele parecer errado (ex.: a API não traz um campo do PDD), PARE e explique: a mudança de motor volta para `/analisar-tecnica`, não é decidida aqui.
3. Gere ou atualize: `projeto/config.py`, `projeto/modelos.py` (item de entrada + modelo da linha extraída, na ordem do layout da saída), `projeto/entrada.py`, o fluxo em `projeto/flows/` e `projeto/main.py` com o destino da saída do PDD. Conforme o motor:
   - `navegador`/`download`: um Page Object por tela em `projeto/pages/` e `core.runner.executar`.
   - `http`: um cliente por grupo de endpoints em `projeto/api/` e `core.runner.executar_http` (sem Page Objects).
   - `hibrido`: Page Object só para o login, clientes em `projeto/api/` com a sessão de `sessao_http_do_navegador(page.context)`, e `core.runner.executar`.
4. Implemente TODOS os controles de qualidade do PDD com `execucao.conferir`/`execucao.validar`, antes do `execucao.entregar`.
5. Se o destino for Excel ou banco, inclua o extra na dependência do `pyproject.toml` (`automacao-core[excel]`, `automacao-core[banco]`) e rode `uv sync` (e diga qual driver do banco instalar, se não for MySQL).
6. Atualize `.env.example` com as novas variáveis (valores fictícios).
7. Crie o sistema simulado: para `navegador`/`download`, um site mínimo em `tests/<nome>/index.html` com as mesmas labels e roles das telas reais; para `http`/`hibrido`, respostas JSON fictícias com o mesmo formato do resumo das requisições, servidas pelo fixture `api_fake`. Depois os testes: caminho feliz (com paginação, se houver), consulta sem registros, total divergente bloqueando a saída, DRY_RUN e falha no login.
8. Remova o exemplo (`projeto/flows/extrair.py`, `projeto/pages/consulta_page.py`, `tests/test_exemplo_extracao.py`, `dados/entrada/consultas.csv`, `tests/portal_fake/`) se ainda existir e não for mais usado.
9. Rode `uv run pytest` e `uv run ruff check .` e corrija o que falhar.

No final, liste:
- Os pontos que o PDD não cobria e a decisão que você tomou em cada um (devem ser poucos; se forem relevantes, sugira abrir uma dúvida e atualizar o PDD)
- Os seletores em que você não confia (os que vieram de XPath/CSS frágil) ou os campos da API cujo significado você deduziu, para revisão humana
- Os conflitos entre os padrões da área (`docs/padroes/`) e as regras do template, e o que você seguiu
