---
agent: agent
description: Aplica no PDD as respostas preenchidas em docs/duvidas.md
---

Aplique no [PDD](../../docs/pdd.md) as respostas das dúvidas com Status `respondida` em [docs/duvidas.md](../../docs/duvidas.md), seguindo [as regras do padrão](../copilot-instructions.md).

Para cada dúvida `respondida`:
1. Substitua o marcador `[DÚVIDA D-xx]` no PDD pelo conteúdo da resposta, redigido no estilo do documento.
2. Se a resposta afetar outras seções (ex.: muda o escopo e, com isso, as regras e as exceções), atualize todas e cite quais foram alteradas.
3. Mude o Status da dúvida para `aplicada`.
4. Se a resposta for vaga ("depende", "ver depois") ou contradizer outro ponto do PDD, NÃO aplique: mantenha `respondida`, escreva o motivo na Resposta ("Copilot: resposta ainda ambígua porque...") e abra uma nova dúvida se for o caso.
5. Se a resposta trouxer um assunto novo, abra uma nova dúvida (próximo ID livre) em vez de supor.

Depois:
- Acrescente uma linha no "Histórico de versões" (incremente a versão menor, ex.: 0.1 → 0.2) resumindo as alterações.
- NÃO mude o Status do PDD. Quem muda para `enviado` ou `aprovado` é a pessoa.

No final, liste:
- As dúvidas aplicadas e as seções alteradas
- As dúvidas que continuam pendentes (`aberta` ou `respondida`) e por quê
- O resultado de `uv run python -m core checar-pdd`
