---
agent: agent
description: Registra que a área validou a saída do robô (fim da homologação)
---

Registre a homologação do robô, seguindo [as regras do padrão](../copilot-instructions.md).

Quem validou e como (informado pela pessoa):

${input:validacao:quem da área validou a saída, quando, e qual período/arquivo foi conferido}

Passos:
1. Confirme que a informação diz explicitamente que a área conferiu a saída e aprovou. "Rodou sem erro" não é homologação: se for só isso, PARE e explique que falta a validação da área.
2. Rode `uv run python -m core concluir-fase homologacao --obs "<quem> validou <o que> em <data>"`. Sem dado pessoal ou de cliente final na observação.
3. Se vier RECUSADO (por exemplo, nenhum DRY_RUN com sucesso depois do fim do desenvolvimento), mostre o motivo e pare. Nunca edite `docs/fases.json` à mão.

No final, mostre o resultado de `uv run python -m core fases` e o próximo passo: agendar com `.\scripts\agendar.ps1 instalar` (como administrador, na VM de produção), que cria a tarefa no Agendador de Tarefas e registra a fase Produção.
