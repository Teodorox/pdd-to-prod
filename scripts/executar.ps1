<#
.SYNOPSIS
    Roda o robô uma vez, agora (fora da agenda). Útil para testar ou repor uma execução perdida.
.EXAMPLE
    .\scripts\executar.ps1            # como em produção (HEADLESS do .env)
    .\scripts\executar.ps1 -Visivel   # abre o navegador na tela, mais devagar, para acompanhar
    .\scripts\executar.ps1 -DryRun    # navega e extrai, mas não grava a saída nem o estado
#>
param(
    [switch]$Visivel,
    [switch]$DryRun
)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..")

if ($Visivel) {
    $env:HEADLESS = "false"
    if (-not $env:SLOW_MO_MS) { $env:SLOW_MO_MS = "300" }
}
if ($DryRun) { $env:DRY_RUN = "true" }

& .venv\Scripts\python.exe -m projeto.main
exit $LASTEXITCODE
