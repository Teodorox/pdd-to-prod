# Passo a passo: robô novo, do zero até a produção

Para quem vai criar um robô de extração com o padrão `automacao-core`. Os comandos estão na ordem em que são usados.

**Antes de começar (uma vez por máquina):** `uv`, `git`, VS Code com GitHub Copilot e acesso ao servidor Git do time.
Nos comandos, troque `<servidor-git>/<grupo>` pelo endereço real e `extracao-test` pelo nome do robô.

## Parte 1: criar o projeto

1. **No servidor Git** (GitHub, GitLab...), crie um projeto **vazio** com o nome do robô (ex.: `extracao-test`), sem README.

2. **Crie a pasta do robô** no ambiente de dev e entre nela:
   ```powershell
   mkdir C:\rpa\extracao-test
   cd C:\rpa\extracao-test
   ```

3. **Inicie o projeto Python:**
   ```powershell
   uv init --bare
   ```

4. **Instale o padrão** (o `automacao-core`, do repositório Git):
   ```powershell
   uv add "automacao-core @ git+https://<servidor-git>/<grupo>/pdd-to-prod.git@v1.0.0"
   ```
   Se a saída for em Excel ou banco: `automacao-core[excel]`, `automacao-core[banco]` ou `automacao-core[excel,banco]`.

5. **Gere a estrutura do robô:**
   ```powershell
   uv run automacao iniciar
   ```
   Cria `projeto/`, `docs/`, `tests/`, `scripts/`, `.github/` (prompts do Copilot), `.env.example` e `GUIA.md`.

6. **Instale as dependências:**
   ```powershell
   uv sync
   ```

7. **Ligue ao servidor Git e faça o primeiro commit:**
   ```powershell
   git init
   git remote add origin https://<servidor-git>/<grupo>/extracao-test.git
   git add -A
   git commit -m "Estrutura inicial do robô"
   git push -u origin main
   ```

8. **Crie o `.env`** e preencha `AUTOMACAO_NOME` e `BASE_URL` (endereço do sistema). Se o time usa um cofre de credenciais, as senhas vêm dele; no `.env` entram só as que não estão no cofre.
   ```powershell
   copy .env.example .env
   ```

9. **Prepare a máquina** (Python, dependências e Chromium da pasta de rede):
   ```powershell
   .\scripts\instalar.ps1 -Navegadores \\servidor\caminho\ms-playwright
   ```

10. **Confira se tudo funciona.** Os testes do exemplo precisam passar:
    ```powershell
    uv run pytest
    ```

11. **Abra o painel de fases** e deixe-o numa aba do navegador (ele se atualiza sozinho):
    ```powershell
    uv run python -m core fases --abrir
    ```

## Parte 2: documentação (PDD)

12. **Salve a fonte do PDD.** Siga o caso **A** ou o **B**. As pastas das duas opções ficam fora do git, porque têm dados do cliente.

    - **A. Call com o cliente:** salve a transcrição em `docs/transcricao/`.
    - **B. O cliente já mandou o PDD ou o passo a passo em Word:** salve o `.docx` em `docs/documento_cliente/` e converta:
      ```powershell
      uv run python -m core importar-documento docs/documento_cliente/pdd_cliente.docx
      ```
      - Sai o `pdd_cliente.md`, com o texto na ordem do Word.
      - As imagens vão para `docs/screenshots/` (`pdd_cliente_01.png`, `_02`...), cada uma marcada no lugar exato do texto. É assim que o Copilot sabe a qual passo pertence cada tela.
      - Veio em PDF? Peça o Word ao cliente. Se não houver, abra o PDF no Word, salve como `.docx` e confira o resultado antes de converter.

13. **No Copilot (modo Agent)**, rode `/gerar-pdd` e indique a fonte: a transcrição ou o `.md` do passo 12.
    - Ele preenche `docs/pdd.md` e lista em `docs/duvidas.md` o que não ficou claro.
    - Mesmo com o PDD do cliente pronto, ele reescreve o conteúdo nas seções do padrão. O que faltar (destino da saída, consulta sem registros, volume, horário) vira dúvida.

14. **Revise o PDD** contra a fonte e responda as dúvidas na tabela (coluna Resposta, status `respondida`). Depois rode `/aplicar-respostas`. Repita até não sobrar dúvida.

15. **Rode `/preparar-envio-pdd`.** Ele gera o Word em `docs/envio/` e o texto do e-mail. **Envie ao cliente.**

16. **Quando o cliente responder**, rode `/registrar-aprovacao` e cole a resposta. Se for reprovado, o PDD volta para o passo 14.

17. **Salve o andamento no Git:**
    ```powershell
    git add -A; git commit -m "PDD aprovado"; git push
    ```

## Parte 3: análise técnica (navegador ou requests?)

18. **Copie o documento de boas práticas** de Python da área para `docs/padroes/`.

19. **Salve os prints das telas** em `docs/screenshots/`, numerados na ordem do fluxo (`01_login.png`, `02_consulta.png`...). Se vieram do documento do cliente (passo 12-B), eles já estão lá. A pasta não vai para o git, porque os prints costumam mostrar dados reais.

20. **Grave o fluxo** no ambiente de homologação:
    ```powershell
    uv run playwright codegen <url-do-sistema> --target python -o docs/recordings/fluxo.py --save-har=docs/requisicoes/fluxo.har
    ```
    - Abre uma janela do navegador. Faça nela **só o processo do PDD**: login, a consulta com resultado, a troca de página (se houver), uma consulta sem registros e o download (se houver).
    - Tudo é gravado sozinho: os cliques vão para o `fluxo.py` e todas as requisições da página vão para o `fluxo.har`.
    - **Termine fechando a janela do navegador.** Os arquivos só são gravados quando a janela fecha; se você interromper com Ctrl+C no terminal, pode perder o `.har`.
    - O `fluxo.py` guarda o usuário e a senha que você digitou, e o `.har` guarda a sua sessão. Nenhum dos dois vai para o git.

21. **Gere o resumo das requisições.** É um comando separado, rodado depois de fechar a janela:
    ```powershell
    uv run python -m core resumir-har docs/requisicoes/fluxo.har
    ```
    O resumo (`fluxo.resumo.md`) só tem a estrutura, sem dados reais, e é o que o Copilot lê. Apague o `.har` quando o robô estiver pronto.

22. **No Copilot**, rode `/analisar-tecnica`. Ele compara navegador, requests, híbrido e download, e grava a decisão em `docs/analise_tecnica.md`.
    - Se ele pedir insumos (outro `.har`, documentação da API, autorização do dono do sistema), entregue e rode de novo.
    - **Confirme a decisão no chat.** Sem a sua confirmação, o desenvolvimento fica travado.

## Parte 4: desenvolvimento

23. **Confira as travas.** As duas precisam passar:
    ```powershell
    uv run python -m core checar-pdd
    uv run python -m core checar-analise
    ```

24. **No Copilot**, rode `/nova-automacao`. Ele gera o robô seguindo o PDD, o motor escolhido e as boas práticas da área.

25. **Revise o código** e rode os testes e o lint:
    ```powershell
    uv run pytest
    uv run ruff check .
    uv run ruff format .
    ```

26. **No Copilot**, rode `/revisar-automacao`. Se o veredito for "pronto", ele registra o fim do desenvolvimento.

27. **Salve no Git:**
    ```powershell
    git add -A; git commit -m "Robô desenvolvido"; git push
    ```

## Parte 5: homologação

28. **Rode o robô sem gravar a saída**, vendo o navegador:
    ```powershell
    .\scripts\executar.ps1 -Visivel -DryRun
    ```

29. **Rode valendo**, com `DRY_RUN=false` e a saída apontando para um **destino de teste**:
    ```powershell
    .\scripts\executar.ps1
    ```
    Entregue o resultado para a área conferir.

30. **Quando a área validar**, rode `/registrar-homologacao` no Copilot e informe quem validou, quando e o quê.

31. **Salve no Git:**
    ```powershell
    git add -A; git commit -m "Homologado"; git push
    ```

## Parte 6: produção (na VM)

32. **Baixe o robô na VM.** É o projeto do robô, não o template:
    ```powershell
    cd C:\rpa
    git clone https://<servidor-git>/<grupo>/extracao-test.git
    cd extracao-test
    ```

33. **Crie e preencha o `.env` de produção.** Use `DRY_RUN=false`, o destino real e os horários:
    ```powershell
    copy .env.example .env
    ```
    ```ini
    AGENDA_DIAS=seg,ter,qua,qui,sex
    AGENDA_HORARIOS=07:00,13:30
    ```

34. **Prepare a VM:**
    ```powershell
    .\scripts\instalar.ps1 -Navegadores \\servidor\caminho\ms-playwright
    ```
    Se o motor for `http` (só requests), use `.\scripts\instalar.ps1 -SemNavegador`.

35. **Agende o robô** com PowerShell **como administrador**. O script pede a conta do robô (ex.: `DOMINIO\usuario.robo`) e a senha:
    ```powershell
    .\scripts\agendar.ps1 instalar
    ```
    - Ele cria a tarefa `\Robos\robo-<nome>` no **Agendador de Tarefas do Windows**, com os horários do `.env`, e registra a fase Produção.
    - **Não crie nem edite a tarefa à mão.** Para mudar o horário, altere o `.env` e rode o `agendar.ps1 instalar` de novo.

36. **Confira o agendamento:**
    ```powershell
    .\scripts\agendar.ps1 status
    ```
    Mostra a última execução, o resultado e a próxima execução. A tarefa também aparece no Agendador de Tarefas, na pasta `Robos`.

---

## No dia a dia

| Situação | O que fazer |
|---|---|
| Mudou o horário no `.env` | `.\scripts\agendar.ps1 instalar` (administrador) |
| A senha da conta do robô mudou | `.\scripts\agendar.ps1 instalar` (administrador) |
| Rodar agora, fora do horário | `.\scripts\executar.ps1` |
| Tirar o robô da agenda | `.\scripts\agendar.ps1 remover` (administrador). Não desative a tarefa no Agendador: ninguém fica sabendo na hora |
| VM desligada no horário | Roda sozinho quando a VM volta, se o atraso couber em `AGENDA_TOLERANCIA_MIN`. Acima disso, notifica e não roda atrasado |

## Quando sair uma versão nova do padrão

Para atualizar um robô que já existe:

1. **Suba a versão do pacote:**
   ```powershell
   uv add "automacao-core @ git+https://<servidor-git>/<grupo>/pdd-to-prod.git@v1.1.0"
   ```
2. **Renove os arquivos do padrão.** São trocados só prompts, scripts e instruções; o código do robô e o PDD ficam como estão:
   ```powershell
   uv run automacao atualizar
   ```
3. **Teste e suba:**
   ```powershell
   uv run pytest
   git add -A; git commit -m "Padrão v1.1.0"; git push
   ```

## Regras que valem o tempo todo

- **Não altere** `scripts/`, `.github/`, `GUIA.md`, `docs/passo_a_passo.md` nem `docs/modelos/` no robô. Melhorias vão para o template.
- **Nunca edite `docs/fases.json` à mão.** As fases são registradas pelos prompts e pelo `agendar.ps1`.
- **Nunca suba para o git** `.env`, `.har`, transcrições, o documento do cliente, prints, gravações do codegen ou evidências. O `.gitignore` já bloqueia esses arquivos.
- **Para saber onde o robô está:** `uv run python -m core fases --abrir`.
