---
agent: agent
description: Diagnostica uma falha a partir da pasta de evidências e propõe a correção para revisão humana
---

Analise a falha registrada em `evidencias/${input:pasta:nome da pasta em evidencias/}` seguindo [as regras do padrão](../copilot-instructions.md).

Arquivos da pasta (robô de navegador):
- `erro.txt`: traceback
- `tela.png`: tela no momento da falha
- `pagina.html`: DOM no momento da falha
- `url.txt`: onde estava
- `trace.zip`: para a pessoa abrir com `uv run playwright show-trace <caminho>` (você não consegue ler)

Robô HTTP (motor `http`): `erro.txt`, `chamadas.txt` (últimas chamadas: método, URL, status) e `ultima_resposta.txt`. No passo 1, "seletor/tela mudou" vira "contrato da API mudou" (campo novo, renomeado ou tipo diferente) e a correção fica em `projeto/api/` e `projeto/modelos.py`. Resposta HTML ou 401/403 no lugar do JSON costuma ser sessão expirada: é (c) ou (e), nunca afrouxar a validação.
Siga também os padrões da área em `docs/padroes/`.

Faça nesta ordem:
1. **Classifique a causa:** (a) seletor/tela mudou, (b) dado divergente ou extração incompleta (`ValidacaoFalhou`, ex.: total da tela diferente do extraído), (c) sistema fora/lento, (d) dado de entrada inválido, (e) bug na automação.
2. **Explique** em 2 a 4 linhas o que aconteceu, citando o trecho do HTML ou do erro que comprova.
3. **Proponha a correção:**
   - (a): ajuste APENAS o Page Object, com seletor que respeite a prioridade do padrão. Mostre o seletor antigo e o novo, e o elemento no `pagina.html` que o novo encontra.
   - (b): primeiro descarte bug de paginação/leitura (a tabela mudou de colunas? o indicador de página trocou antes dos dados?). Se for isso, é (a) ou (e). Se o sistema realmente informa um total diferente do que mostra, NÃO altere código: é para uma pessoa investigar no sistema.
   - (c) ou (d): não altere código. Diga o que verificar.
   - (e): corrija e adicione um teste que reproduz o problema.
4. Rode `uv run pytest`.

Proibido:
- Afrouxar ou remover `execucao.conferir`/`validar`, ou descartar linhas para o total bater
- Adicionar retry, `try/except`, `sleep` ou seletor alternativo "de reserva"
- Mexer em `core/`

Se o item estiver em `revisao_manual`, lembre a pessoa de conferir no sistema (e, se houver ação crítica, se ela foi efetivada) e resolver com:
`uv run python -m core resolver <ITEM_ID> --como concluido|pendente --obs "<o que foi conferido>"`
