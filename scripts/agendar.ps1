<#
.SYNOPSIS
    Agenda o robô no Agendador de Tarefas do Windows, a partir de AGENDA_* do .env.

.DESCRIPTION
    Cria (ou recria) a tarefa \Robos\robo-<AUTOMACAO_NOME>:
    - um gatilho por horário de AGENDA_HORARIOS, nos dias de AGENDA_DIAS;
    - roda com ou sem usuário logado, com a conta do robô;
    - se a VM estava desligada no horário, roda ao ligar (o core só executa se o atraso couber em
      AGENDA_TOLERANCIA_MIN; acima disso, notifica e não roda atrasado);
    - não abre uma segunda instância se a anterior ainda estiver rodando;
    - a ação é "python -m core execucao-agendada" na pasta do robô (timeout, sinal de vida, notificação).

    Mudou a agenda no .env? Rode "instalar" de novo: a tarefa é recriada com os novos horários.
    Não crie nem edite a tarefa à mão: o horário tem que ser o do .env (o core confere a cada disparo).

    instalar e remover precisam de PowerShell como administrador.

.EXAMPLE
    .\scripts\agendar.ps1 instalar   # pede a conta do robô (ex.: DOMINIO\usuario.robo) e a senha
    .\scripts\agendar.ps1 status
    .\scripts\agendar.ps1 remover
#>
param(
    [Parameter(Mandatory)][ValidateSet("instalar", "remover", "status")]
    [string]$Acao
)
$ErrorActionPreference = "Stop"
$raiz = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $raiz

$python = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Ambiente não instalado. Rode antes: .\scripts\instalar.ps1" }
if (-not (Test-Path .env)) { throw ".env não encontrado em $raiz" }

$linhaNome = Select-String -Path .env -Pattern '^\s*AUTOMACAO_NOME\s*=\s*(\S+)' | Select-Object -First 1
if (-not $linhaNome) { throw "Defina AUTOMACAO_NOME no .env (vira o nome da tarefa)" }
$nome = $linhaNome.Matches[0].Groups[1].Value
$tarefa = "robo-$nome"
$pastaTarefa = "\Robos\"
# Cópia da tarefa criada (sem senha): prova para a fase Produção e referência do que está agendado
$registro = Join-Path $raiz "agendamento\$tarefa.xml"

function Exigir-Administrador {
    $identidade = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $identidade.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Abra o PowerShell como administrador para $Acao o agendamento."
    }
}

function Buscar-Tarefa {
    Get-ScheduledTask -TaskPath $pastaTarefa -TaskName $tarefa -ErrorAction SilentlyContinue
}

switch ($Acao) {
    "instalar" {
        Exigir-Administrador
        Write-Host "Conferindo a agenda do .env..."
        & $python -m core agenda
        if ($LASTEXITCODE -ne 0) { throw "AGENDA_* inválida no .env" }
        $agenda = (& $python -m core agenda --json) | ConvertFrom-Json

        $acaoTarefa = New-ScheduledTaskAction -Execute $python -Argument "-m core execucao-agendada" -WorkingDirectory $raiz
        $gatilhos = foreach ($horario in $agenda.horarios) {
            $gatilho = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $agenda.dias -At $horario
            # Hora local (sem o "Z" de UTC que o cmdlet às vezes põe): 07:00 no .env = 07:00 no relógio da VM
            $gatilho.StartBoundary = (Get-Date $horario).ToString("yyyy-MM-ddTHH:mm:ss")
            $gatilho
        }
        # Limite do Windows acima do timeout do core: quem encerra (e notifica) é o core; isto é só a rede de proteção
        $config = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
            -ExecutionTimeLimit (New-TimeSpan -Minutes ([int]$agenda.timeout_min + 30)) `
            -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

        $conta = Get-Credential -Message "Conta que roda o robô (ex.: DOMINIO\usuario.robo). Precisa acessar a pasta de rede/banco da saída."
        if (-not $conta) { throw "Conta não informada." }
        Register-ScheduledTask -TaskPath $pastaTarefa -TaskName $tarefa -Action $acaoTarefa -Trigger $gatilhos `
            -Settings $config -User $conta.UserName -Password $conta.GetNetworkCredential().Password `
            -RunLevel Limited -Description "Robô $nome ($raiz). Agenda em AGENDA_* do .env; recrie com scripts\agendar.ps1 instalar." `
            -Force | Out-Null

        New-Item -ItemType Directory -Force (Split-Path $registro) | Out-Null
        [IO.File]::WriteAllText($registro, (Export-ScheduledTask -TaskPath $pastaTarefa -TaskName $tarefa), (New-Object Text.UTF8Encoding $false))
        Write-Host "Tarefa $pastaTarefa$tarefa criada. Acompanhe com: .\scripts\agendar.ps1 status"

        & $python -m core agendamento instalado
        # Não impede o agendamento (em DEV a tarefa pode ser criada para teste, antes da homologação)
        & $python -m core concluir-fase producao --obs "tarefa $tarefa agendada em $env:COMPUTERNAME"
        if ($LASTEXITCODE -ne 0) { Write-Warning "Tarefa criada, mas a fase Produção não foi registrada (motivo acima)." }
    }
    "remover" {
        Exigir-Administrador
        if (Buscar-Tarefa) {
            Unregister-ScheduledTask -TaskPath $pastaTarefa -TaskName $tarefa -Confirm:$false
            Write-Host "Tarefa $pastaTarefa$tarefa removida."
        } else {
            Write-Host "Tarefa $pastaTarefa$tarefa não existe."
        }
        if (Test-Path $registro) { Remove-Item $registro }
        & $python -m core agendamento removido
    }
    "status" {
        $atual = Buscar-Tarefa
        if (-not $atual) {
            Write-Host "Tarefa $pastaTarefa$tarefa não existe. Crie com: .\scripts\agendar.ps1 instalar"
        } else {
            $info = $atual | Get-ScheduledTaskInfo
            Write-Host "Tarefa ${pastaTarefa}${tarefa}: $($atual.State)"
            Write-Host "  Última execução: $($info.LastRunTime) (resultado $($info.LastTaskResult); 0 = sucesso)"
            Write-Host "  Próxima execução: $($info.NextRunTime)"
        }
        $status = Get-ChildItem $raiz -Filter "*.agenda.json" | Select-Object -First 1
        if ($status) { Get-Content $status.FullName -Encoding UTF8 } else { Write-Host "(nenhuma execução agendada ainda)" }
    }
}
