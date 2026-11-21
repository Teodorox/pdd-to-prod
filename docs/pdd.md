# PDD: <nome do processo>

<!--
MODELO. Gere com /gerar-pdd a partir da transcrição em docs/transcricao/.
- Se a área tiver o modelo padrão de PDD, ajuste as seções abaixo para ficarem iguais às dele (mesma ordem e nomes).
- Ponto incerto NUNCA é inventado: escreva [DÚVIDA D-01] no lugar e registre a pergunta em docs/duvidas.md.
- Nada de dado real (CPF, conta, nome de cliente final, senha, URL com token). Use exemplos fictícios.
- Comentários como este são ignorados na exportação para Word.
Status: rascunho -> em_validacao (revisão interna) -> enviado (ao cliente) -> aprovado | reprovado
-->

**Status:** rascunho
**Versão:** 0.1
**Área solicitante:**
**Responsável no cliente:**
**Desenvolvedor:**
**Origem:** transcrição da reunião de dd/mm/aaaa

## 1. Histórico de versões

| Versão | Data | Autor | Alteração |
|---|---|---|---|
| 0.1 | dd/mm/aaaa | | Versão inicial gerada a partir da transcrição |

## 2. Visão geral

- **Objetivo:** <!-- uma frase: o que o robô faz e para quem -->
- **Dor atual:** <!-- o que a área faz hoje manualmente, quanto tempo leva, quais erros acontecem -->
- **Benefício esperado:** <!-- horas economizadas, prazo, qualidade -->

## 3. Escopo

**Dentro do escopo:**
-

**Fora do escopo:**
-

## 4. Sistemas e acessos

| Sistema | Uso no processo | Ambiente de homologação? | Tipo de login | Usuário do robô | Tem API? |
|---|---|---|---|---|---|
| | | | usuário/senha, SSO, certificado, 2FA | | |

## 5. Processo atual (AS-IS)

<!-- Como a pessoa faz hoje, passo a passo, citando telas e decisões -->
1.

## 6. Processo automatizado (TO-BE)

<!-- Passo a passo do robô. Uma linha por tela/ação. Indique o que é lido em cada tela. -->
1.

## 7. Entrada

- **Origem:** <!-- lista de agências/contratos num arquivo, parâmetro fixo, período (ex.: mês anterior), banco... -->
- **Formato e exemplo (fictício):**
- **Identificador único de cada consulta:** <!-- ex.: agência + competência. Garante não processar duas vezes -->

## 8. Dados extraídos (dicionário de dados)

| Campo | Tela/origem | Tipo | Obrigatório | Formato/exemplo (fictício) | Observação |
|---|---|---|---|---|---|
| | | texto, número, valor (R$), data | sim/não | | |

## 9. Saída

- **Destino:** <!-- arquivo em pasta de rede (CSV/Excel) | banco de dados (qual, tabela) | outro. Sugestão do desenvolvedor -->
- **Layout:** <!-- colunas e ordem; um arquivo por consulta ou consolidado -->
- **Nome do arquivo / tabela:**
- **Quem consome e como:**
- **Retenção:**

## 10. Regras de negócio

| ID | Regra |
|---|---|
| RN-01 | |

## 11. Exceções e tratamento

| ID | Situação | Tipo | O que o robô faz |
|---|---|---|---|
| EX-01 | Sistema fora do ar / lento | sistema | para, guarda evidências e notifica; tenta de novo na próxima execução |
| EX-02 | Consulta sem nenhum registro | negócio | <!-- grava arquivo vazio? notifica? --> |
| EX-03 | Total informado pela tela diferente do extraído | qualidade | para o item, não grava saída, notifica |

## 12. Controles de qualidade

<!-- Como provar que o dado está completo e correto. Ex.: total de registros da tela = linhas extraídas;
soma dos valores = total da tela; campos obrigatórios preenchidos -->
-

## 13. Agendamento e volume

- **Frequência e horário:**
- **Janela em que o sistema está disponível:**
- **Volume esperado (consultas por execução, linhas por consulta):**
- **Prazo para a saída estar disponível:**

## 14. Notificações

- **Quem recebe falhas:** <!-- e-mail, canal do Teams -->
- **Quem recebe o aviso de conclusão (se houver):**

## 15. Segurança e LGPD

- **Dados sensíveis envolvidos:**
- **Onde ficam as credenciais do robô:** cofre / variável de ambiente no servidor (nunca no código)
- **Quem pode acessar a saída e as evidências:**

## 16. Aprovação

| Enviado em | Aprovado/reprovado por | Data da resposta | Decisão | Referência do e-mail |
|---|---|---|---|---|
| | | | | |
