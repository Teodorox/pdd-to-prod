# Monitoramento central dos robôs

Cada robô grava no banco de monitoramento, além dos logs detalhados em arquivo na própria VM:

| Tabela | Quem grava | O que tem |
|---|---|---|
| `robo_execucao` | robô (`core/runner.py`) | Uma linha por execução: início, fim, status, itens ok/erro, registros extraídos |
| `robo_evento` | robô e execução agendada | Início, meio (um evento por item), fim e falha; horário perdido, timeout |
| `robo_heartbeat` | execução agendada (`core/agendador.py`) e `agendar.ps1` | Sinal ao começar, a cada 5 min durante e ao terminar a execução; ao criar ou remover a tarefa. Situação (aguardando, executando, removido) e próxima execução prevista |
| `robo_cadastro` | equipe, à mão | Quais robôs devem estar ativos, em qual VM, quem é o responsável |

A view `vw_robo_saude` junta tudo e diz, por robô, se há alerta:

| Alerta | Significa |
|---|---|
| `NUNCA_DEU_SINAL` | Está no cadastro, mas nunca foi agendado (`agendar.ps1 instalar` não rodou) ou está sem `MONITOR_URL` |
| `AGENDAMENTO_REMOVIDO` | Alguém removeu a tarefa com `agendar.ps1 remover` (intencional) |
| `NAO_INICIOU` | Passou 15 min do horário previsto e a execução não começou: VM desligada, tarefa desativada ou apagada à mão, senha da conta do robô vencida |
| `SEM_SINAL` | Execução em andamento sem sinal há mais de 15 min: VM caiu no meio, processo morto, banco inacessível pela VM |
| `EXECUCAO_TRAVADA` | Execução em andamento há mais de 6 h (o processo morreu sem fechar a execução) |
| `ULTIMA_EXECUCAO_FALHOU` | A última execução terminou com falha, erros ou interrompida |

## Implantação (uma vez)

1. O DBA roda o [ddl_mysql.sql](ddl_mysql.sql) no banco de monitoramento (MySQL 5.7+).
2. Crie um usuário de banco para os robôs com permissão só de `INSERT`/`UPDATE`/`SELECT` nas 3 tabelas gravadas pelos robôs.
3. Cadastre os robôs em `robo_cadastro` (`robo` = `AUTOMACAO_NOME` do `.env`).
4. Em cada robô, use o extra `banco` na dependência (`automacao-core[banco]`, que já traz o driver do MySQL) e preencha no `.env`:

```ini
MONITOR_URL=mysql+pymysql://usuario:senha@servidor:3306/monitoramento?charset=utf8mb4
MONITOR_HEARTBEAT_MIN=5
```

> Se o banco de monitoramento ficar fora do ar, os robôs **continuam rodando** e registram um aviso no log em arquivo. O painel mostra o problema como `NAO_INICIOU` ou `SEM_SINAL`.

> Cuidado: tarefa desativada no Agendador de Tarefas não avisa ninguém na hora. Ela aparece como `NAO_INICIOU` no horário seguinte. Para tirar um robô do ar de propósito, use `agendar.ps1 remover` (ou `ativo = 0` no cadastro).

## Painel (Power BI)

Conecte nas tabelas e na view (DirectQuery ou importação a cada 15 min). Páginas sugeridas:

- **Agora:** `vw_robo_saude` em tabela com formatação condicional por `alerta`, contadores por alerta e por VM.
- **Execuções:** `robo_execucao` filtrando `dry_run = 0`, com taxa de sucesso por robô/dia, duração (`fim - inicio`) e registros extraídos ao longo do tempo. Queda brusca de registros costuma indicar problema no sistema de origem.
- **Detalhe do robô:** linha do tempo de `robo_evento` (filtro por robô e `id_execucao`).
- **Capacidade:** execuções simultâneas por VM e por hora, para espaçar horários de robôs na mesma VM.

## Detalhe de uma falha

O banco tem só o resumo. O detalhe continua na VM do robô:
- `logs/<AUTOMACAO_NOME>.jsonl`: log completo
- `evidencias/<data>_<item>/`: tela, HTML e trace da falha
- `logs/agendamento.jsonl`: log das execuções agendadas (disparo, timeout, horário perdido)
- Agendador de Tarefas › `\Robos\robo-<AUTOMACAO_NOME>` › Histórico: se a tarefa disparou
