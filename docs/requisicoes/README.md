# Requisições do sistema (.har)

Quando a análise técnica (`/analisar-tecnica`) avalia usar **requests** em vez do navegador, ela precisa ver
quais chamadas o sistema faz por trás da tela. Isso vem de um arquivo **.har**: a gravação de tudo que o
navegador pediu e recebeu enquanto você fazia o processo.

## Quando gravar

Depois do PDD aprovado, no mesmo momento em que você grava o `playwright codegen` (docs/recordings/):
faça o processo **inteiro, uma vez, como o robô faria**, no ambiente de homologação (ou produção só com
consulta, nunca alterando nada).

Inclua no mesmo arquivo, se der:
1. O login (do início, com a sessão deslogada)
2. Uma consulta com resultado e, se houver, a troca de página
3. Uma consulta **sem registros**
4. O download do relatório, se o processo tiver

## Como gravar

**Opção A: Playwright (recomendada, já instalado no projeto)**

```powershell
uv run playwright codegen --save-har=docs/requisicoes/consulta.har <url do sistema>
```

Faça o processo na janela que abrir: tudo que a página carregar é gravado sozinho, sem você fazer nada além
do processo. Termine **fechando a janela do navegador**: o .har só é gravado ao fechar (Ctrl+C no terminal
pode perder o arquivo). Depois rode o `resumir-har` (abaixo), que é um comando separado.
Se o sistema tiver muitas chamadas de outras origens, filtre: `--save-har-glob="**/api/**"`.

**Opção B: Edge/Chrome (quando o sistema só abre no navegador da empresa)**

1. Abra o sistema, aperte **F12** e vá na aba **Rede (Network)**.
2. Marque **Preservar log (Preserve log)** e, de preferência, **Desabilitar cache**.
3. Faça o processo do começo ao fim.
4. Clique com o botão direito na lista de requisições > **Salvar tudo como HAR com conteúdo**
   (nas versões novas: **Exportar HAR (sanitizado)**, que já tira cookies e Authorization e é suficiente)
   e salve em `docs/requisicoes/<nome>.har`.

## Depois de gravar

```powershell
uv run python -m core resumir-har docs/requisicoes/consulta.har
```

Gera `docs/requisicoes/consulta.resumo.md` com **só a estrutura**: métodos, caminhos, nomes dos parâmetros,
formato dos JSON (chaves e tipos), cookies de sessão (só o nome), CSRF e CAPTCHA. Nenhum valor.
É esse resumo que o Copilot lê, e ele pode ser versionado.

## Cuidados

- O **.har tem a sua sessão** (cookies, tokens) e **os dados reais da tela**. Ele não vai para o git
  (`.gitignore`), não é anexado em e-mail ou chamado e não deve ser aberto pelo Copilot.
- Apague o .har quando a análise e o desenvolvimento terminarem. Se precisar de novo, grave de novo.
- Use um usuário de teste/robô, nunca o seu usuário pessoal com acessos amplos, se possível.
