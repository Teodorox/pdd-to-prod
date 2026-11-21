/*
  Monitoramento central dos robôs (MySQL 5.7+). Criar UMA vez no banco de monitoramento (não por robô).
  As tabelas robo_execucao, robo_evento e robo_heartbeat são gravadas pelos robôs (core/monitor.py).
  A robo_cadastro é mantida pela equipe: diz quais robôs DEVERIAM estar vivos e quem acionar.

  Horários: os robôs gravam a hora local da VM. VMs e servidor de banco precisam estar no mesmo fuso
  e sincronizados (NTP do domínio).
*/

CREATE TABLE robo_execucao (
    id_execucao      VARCHAR(36)   NOT NULL PRIMARY KEY,
    robo             VARCHAR(100)  NOT NULL,
    vm               VARCHAR(100)  NOT NULL,
    inicio           DATETIME      NOT NULL,
    fim              DATETIME      NULL,
    status           VARCHAR(20)   NOT NULL,  -- em_andamento | sucesso | com_erros | interrompida | falha
    itens_concluidos INT           NULL,
    itens_erro       INT           NULL,
    itens_pulados    INT           NULL,
    registros        INT           NULL,      -- linhas extraídas e entregues
    dry_run          TINYINT(1)    NOT NULL,
    mensagem         VARCHAR(1000) NULL,
    INDEX ix_robo_execucao_robo_inicio (robo, inicio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE robo_evento (
    id          BIGINT        NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_execucao VARCHAR(36)   NULL,
    robo        VARCHAR(100)  NOT NULL,
    vm          VARCHAR(100)  NOT NULL,
    momento     DATETIME      NOT NULL,
    tipo        VARCHAR(30)   NOT NULL,  -- inicio | item_ok | item_erro | item_critico | fim | falha
                                         -- nao_iniciada | perdida | timeout | processo_erro
    item_id     VARCHAR(200)  NULL,
    mensagem    VARCHAR(1000) NULL,
    INDEX ix_robo_evento_robo_momento (robo, momento),
    INDEX ix_robo_evento_momento (momento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE robo_heartbeat (
    robo             VARCHAR(100) NOT NULL PRIMARY KEY,
    vm               VARCHAR(100) NOT NULL,
    ultimo_sinal     DATETIME     NOT NULL,
    situacao         VARCHAR(20)  NOT NULL,  -- aguardando | executando | removido
    proxima_execucao DATETIME     NULL,
    agenda           VARCHAR(200) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE robo_cadastro (
    robo        VARCHAR(100) NOT NULL PRIMARY KEY,  -- = AUTOMACAO_NOME do .env
    vm          VARCHAR(100) NOT NULL,
    area        VARCHAR(100) NULL,
    responsavel VARCHAR(100) NULL,
    ativo       TINYINT(1)   NOT NULL DEFAULT 1     -- 0 = desligado de propósito, não alerta
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

/*
  Saúde de cada robô ativo. alerta NULL = tudo certo. Usada pelo Power BI.
  Limites (ajuste aqui, valem para todos): 15 min de folga depois do horário previsto e sem sinal durante
  a execução (3 heartbeats de 5 min); 6 h para execução travada.
  O robô só dá sinal quando a tarefa agendada roda (Agendador de Tarefas): entre execuções, o que se cobra
  é que a próxima execução prevista comece.
*/
CREATE OR REPLACE VIEW vw_robo_saude AS
SELECT
    c.robo,
    c.vm,
    c.area,
    c.responsavel,
    h.situacao,
    h.ultimo_sinal,
    TIMESTAMPDIFF(MINUTE, h.ultimo_sinal, NOW()) AS minutos_sem_sinal,
    h.proxima_execucao,
    u.inicio    AS ultima_inicio,
    u.fim       AS ultima_fim,
    u.status    AS ultima_status,
    u.registros AS ultima_registros,
    u.mensagem  AS ultima_mensagem,
    CASE
        WHEN h.robo IS NULL                                         THEN 'NUNCA_DEU_SINAL'
        WHEN h.situacao = 'removido'                                THEN 'AGENDAMENTO_REMOVIDO'
        WHEN h.situacao = 'aguardando'
             AND TIMESTAMPDIFF(MINUTE, h.proxima_execucao, NOW()) > 15 THEN 'NAO_INICIOU'
        WHEN h.situacao = 'executando'
             AND TIMESTAMPDIFF(MINUTE, h.ultimo_sinal, NOW()) > 15  THEN 'SEM_SINAL'
        WHEN u.status = 'em_andamento'
             AND TIMESTAMPDIFF(MINUTE, u.inicio, NOW()) > 360       THEN 'EXECUCAO_TRAVADA'
        WHEN u.status IN ('falha', 'interrompida', 'com_erros')     THEN 'ULTIMA_EXECUCAO_FALHOU'
    END AS alerta
FROM robo_cadastro c
LEFT JOIN robo_heartbeat h ON h.robo = c.robo
LEFT JOIN robo_execucao u ON u.id_execucao = (
    SELECT e.id_execucao FROM robo_execucao e
    WHERE e.robo = c.robo AND e.dry_run = 0
    ORDER BY e.inicio DESC LIMIT 1
)
WHERE c.ativo = 1;
