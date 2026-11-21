---
agent: agent
description: Gera o Word do PDD e o texto do e-mail para o cliente aprovar
---

Prepare o envio do [PDD](../../docs/pdd.md) para aprovação do cliente, seguindo [as regras do padrão](../copilot-instructions.md).

Passos:
1. Confira se ainda há dúvidas pendentes em [docs/duvidas.md](../../docs/duvidas.md):
   - Pendentes com "Quem responde" = `dev`: PARE e peça para a pessoa responder antes do envio.
   - Pendentes com "Quem responde" = `cliente`: elas entram no e-mail como perguntas.
2. Gere o Word:
   - Sem dúvidas no PDD: `uv run python -m core exportar-pdd --modelo docs/modelos/modelo_pdd.docx` (sem `--modelo` se esse arquivo não existir)
   - Com dúvidas do cliente ainda no PDD: acrescente `--rascunho`
3. Preencha o [modelo de e-mail](../../docs/modelos/email_envio_pdd.md) com os dados do PDD e salve em `docs/envio/email.md`. Se não houver dúvidas para o cliente, remova o bloco de perguntas.
4. Mude o Status do PDD para `enviado` e preencha "Enviado em" na seção Aprovação com a data de hoje.
5. Registre a fase: `uv run python -m core concluir-fase pdd --obs "PDD <versão> enviado para aprovação"`. Se vier RECUSADO, mostre o motivo e pare.

No final, mostre o texto do e-mail pronto para colar e o caminho do .docx para anexar.

Lembre a pessoa: quando o cliente responder, ela deve rodar `/registrar-aprovacao` e colar a resposta do e-mail.
