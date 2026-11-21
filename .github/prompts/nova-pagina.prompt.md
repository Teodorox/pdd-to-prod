---
agent: agent
description: Cria um Page Object para uma tela nova
---

Crie o Page Object da tela **${input:tela:nome da tela, ex.: consulta de movimentações}** seguindo [as regras do padrão](../copilot-instructions.md) e os padrões da área em `docs/padroes/`.

Fontes (use as que existirem):
- Screenshot: `docs/screenshots/${input:screenshot:arquivo do print em docs/screenshots}`
- Gravação do codegen em `docs/recordings/`
- HTML da tela salvo em uma pasta de `evidencias/`
- Servidor MCP do Playwright, se estiver ativo (somente navegação e leitura)

Regras:
- Arquivo em `projeto/pages/<nome>_page.py`, classe herdando `BasePage`.
- Todos os locators no `__init__`, respeitando a prioridade de seletor do padrão.
- `aguardar_carregar()` esperando o elemento que prova que a tela carregou.
- Métodos com nomes de negócio (`consultar`, `extrair_movimentacoes`, `ler_saldo`) que retornam dados tipados (modelos de `projeto/modelos.py`).
- Tabelas com `ler_tabela`, paginação com `percorrer_paginas` (identifique o indicador de página), downloads com `baixar`.
- Converta os textos na page: `valor_brl`, `data_br`, `somente_digitos`.
- Se a tela tiver uma ação que altera o sistema, documente na docstring que ela só pode ser chamada via `execucao.acao_critica`.

No final, liste os elementos que você não conseguiu identificar com segurança.
