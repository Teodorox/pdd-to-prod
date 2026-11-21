# Análise técnica: <nome do processo>

<!--
MODELO. Gere docs/analise_tecnica.md com /analisar-tecnica, depois do PDD aprovado e antes do /nova-automacao.
- Decide o MOTOR do robô com base no PDD, nas telas, nas gravações e no resumo das requisições (.har).
- Status: pendente_insumos (falta material para decidir) -> decidida. Só a pessoa desenvolvedora confirma.
- Nunca copie valor real (CPF, conta, token, cookie) para cá: só nomes de campos, endpoints e tipos.
-->

**Status:** pendente_insumos
**Motor:** a_definir
**Data:** dd/mm/aaaa
**Desenvolvedor:**

<!-- Motor: navegador | http | hibrido | download -->

## 1. Insumos consultados

| Insumo | Arquivo | Situação |
|---|---|---|
| PDD aprovado | docs/pdd.md | |
| Telas | docs/screenshots/ | |
| Gravação do codegen | docs/recordings/ | |
| Resumo das requisições (.har) | docs/requisicoes/*.resumo.md | |
| Padrões da área | docs/padroes/ | |

## 2. O que o processo exige

<!-- Volume (consultas por execução, linhas por consulta), janela de execução, telas, paginação, downloads,
     tipo de login (usuário/senha, SSO, certificado, 2FA, CAPTCHA), ações que alteram o sistema. -->

## 3. Comparativo

Nota de 1 (ruim) a 5 (ótimo) para ESTE processo, com o motivo. Critérios em que não há informação: "?" e vira insumo pendente.

| Critério | Navegador (Playwright) | HTTP (requests) | Híbrido | Download |
|---|---|---|---|---|
| Desempenho (tempo por consulta, volume) | | | | |
| Consumo da máquina (CPU/memória, Chromium) | | | | |
| Autenticação viável (SSO, 2FA, CAPTCHA, token) | | | | |
| Navegação / dependência de JavaScript | | | | |
| Estabilidade (o que quebra quando o sistema muda) | | | | |
| Completude e conferência (total da tela/API) | | | | |
| Evidência em falha (print x resposta da API) | | | | |
| Segurança e conformidade (endpoint interno, termos, bloqueio por WAF) | | | | |
| Manutenção pelo time (padrão da área) | | | | |
| Instalação na VM (Chromium offline, proxy, certificado) | | | | |

## 4. Decisão

- **Motor escolhido:**
- **Por quê (3 a 5 linhas):**
- **Riscos e como o robô se protege:**
- **Endpoints ou telas usados:** <!-- método + caminho genérico (/api/contratos/{id}), ou o nome da tela -->

## 5. Insumos pendentes

<!-- O que a pessoa desenvolvedora precisa entregar para decidir ou para desenvolver. Um por linha, com onde salvar.
     Vazio quando Status = decidida. -->

| ID | Insumo | Como obter | Onde salvar |
|---|---|---|---|
