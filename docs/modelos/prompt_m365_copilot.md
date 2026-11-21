# Prompt para o Microsoft 365 Copilot (alternativa ao /gerar-pdd)

Use quando a transcrição estiver só no Teams e não puder ser baixada. No Copilot da reunião (Teams) ou no Copilot do Word, cole o texto abaixo e anexe o `docs/pdd.md` deste repositório como modelo. Depois, salve a resposta em `docs/pdd.md` e `docs/duvidas.md` e siga o fluxo normal (revisão → `/aplicar-respostas` → envio).

---

Com base na transcrição desta reunião, preencha o PDD seguindo EXATAMENTE as seções do modelo anexo, em Markdown.

Regras:
1. Use só o que foi dito na reunião. Não invente sistemas, telas, campos, regras ou volumes.
2. Quando algo não estiver claro, faltar ou houver contradição, escreva `[DÚVIDA D-01]` (numerando em sequência) no ponto do PDD em vez de supor.
3. Depois do PDD, gere uma tabela Markdown de dúvidas com as colunas: ID | Status | Seção do PDD | Pergunta | Trecho da transcrição | Sugestão | Quem responde | Resposta. Status sempre `aberta`, Resposta vazia. "Quem responde" é `dev` para decisões técnicas (formato da saída, tecnologia) e `cliente` para regras de negócio.
4. Não copie dados pessoais nem dados de clientes (CPF, conta, nomes de correntistas). Troque por exemplos fictícios.
5. Mantenha `**Status:** rascunho`.
