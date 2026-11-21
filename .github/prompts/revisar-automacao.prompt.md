---
agent: agent
description: Revisa o robô contra o padrão e o PDD antes de ir para produção
---

Revise o código em `projeto/` e `tests/` contra [as regras do padrão](../copilot-instructions.md), o [PDD](../../docs/pdd.md), a [análise técnica](../../docs/analise_tecnica.md) e os padrões da área em `docs/padroes/`. Não altere o código, só aponte.

Checklist (para cada item: OK, ou o problema com arquivo:linha):
- [ ] Todos os campos da seção "Dados extraídos" do PDD estão no modelo, com os tipos certos
- [ ] Todas as regras de negócio, exceções e controles de qualidade do PDD estão implementados
- [ ] Completude conferida antes da entrega (total da tela x linhas extraídas, somas, quando houver)
- [ ] Consulta sem registros só é aceita quando a tela confirma explicitamente
- [ ] Saída gravada só via `execucao.entregar`, no fim do fluxo, no destino definido no PDD
- [ ] O motor usado é o da análise técnica (`executar` ou `executar_http`) e os endpoints/telas são os listados nela
- [ ] Segue os padrões da área (`docs/padroes/`); conflitos com o template apontados, não decididos em silêncio
- [ ] HTTP: URLs e payloads só em `projeto/api/`; respostas validadas em modelo pydantic; status e Content-Type conferidos (`json_ok`); nenhum token/cookie fixo no código ou nos testes
- [ ] Seletores só em `projeto/pages/`, seguindo a prioridade e sem índice posicional/classe gerada
- [ ] Paginação com `percorrer_paginas` e indicador de página que prova a troca
- [ ] Nenhum `time.sleep`, `wait_for_timeout`, retry manual ou `try/except` que esconda erro
- [ ] Nenhuma linha descartada ou "corrigida" em silêncio
- [ ] `Item.id` estável e único; entrada validada inteira antes de começar
- [ ] Valores monetários como `Decimal`, datas como `date`, nunca `float`/texto
- [ ] Se houver ação que altera o sistema: via `execucao.acao_critica`, com conferência antes e prova depois
- [ ] Segredos só no `.env`/`SecretStr`, nada sensível em log, código, testes ou docs
- [ ] `.env.example` atualizado
- [ ] Testes: caminho feliz, sem registros, total divergente, DRY_RUN, falha no login
- [ ] Usa API (`core.http`) ou relatório para download onde a análise técnica indicou, em vez de ler a tela

No final, dê um veredito: **pronto para homologação** ou **ajustes necessários**, listando os bloqueadores.

Só se o veredito for **pronto para homologação**, registre a fase: `uv run python -m core concluir-fase desenvolvimento --obs "revisão OK: <resumo em uma linha>"`. O comando roda os testes e o lint; se vier RECUSADO, mostre o motivo e troque o veredito para **ajustes necessários**.
