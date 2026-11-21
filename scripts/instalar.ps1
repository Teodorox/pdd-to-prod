<#
.SYNOPSIS
    Prepara o robô nesta máquina: ambiente Python, navegador e validação do .env.
.EXAMPLE
    .\scripts\instalar.ps1
    .\scripts\instalar.ps1 -Navegadores \\servidor\rpa\ms-playwright   # VM sem acesso à internet
    .\scripts\instalar.ps1 -SemNavegador                               # robô com motor http (só requests)
.NOTES
    Extras (excel, banco) ficam na dependência do pyproject.toml: automacao-core[excel,banco].
#>
param(
    # Robô com motor http (docs/analise_tecnica.md): não precisa do Chromium
    [switch]$SemNavegador,
    # Pasta (normalmente de rede) com as pastas do Playwright (chromium-XXXX, chromium_headless_shell-XXXX).
    # Vazio = baixa da internet.
    [string]$Navegadores = ""
)
$ErrorActionPreference = "Stop"
$raiz = Resolve-Path "$PSScriptRoot\.."
Set-Location $raiz

function Copiar-Navegadores([string]$origem, [string]$destino) {
    # A versão do Chromium tem que ser exatamente a que o Playwright do uv.lock espera: pergunta a ele
    $saida = & uv run --frozen playwright install --dry-run chromium
    if ($LASTEXITCODE -ne 0) { throw "playwright install --dry-run falhou" }
    $pastas = $saida | Select-String 'Install location:\s*(.+)$' |
        ForEach-Object { Split-Path -Leaf $_.Matches[0].Groups[1].Value.Trim() }

    foreach ($pasta in $pastas) {
        $de = Join-Path $origem $pasta
        $para = Join-Path $destino $pasta
        # Só o Chromium é obrigatório. ffmpeg (gravação de vídeo) e winldd não são usados pelos robôs.
        if (-not (Test-Path $de)) {
            if ($pasta -like "chromium*") {
                throw ("Falta '$pasta' em $origem. Este robô usa essa versão do Chromium. Numa máquina com internet, " +
                    "com o mesmo uv.lock, rode: `$env:PLAYWRIGHT_BROWSERS_PATH='$origem'; uv run playwright install chromium")
            }
            Write-Warning "'$pasta' não está em $origem (opcional, seguindo sem ele)."
            continue
        }
        # O Playwright cria esse arquivo ao terminar a instalação: sem ele, a cópia anterior ficou pela metade
        if (Test-Path (Join-Path $para "INSTALLATION_COMPLETE")) {
            Write-Host "$pasta já está em $destino"
            continue
        }
        Write-Host "Copiando $pasta de $origem..."
        & robocopy $de $para /E /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy falhou ao copiar $pasta (código $LASTEXITCODE)" }
    }
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv não encontrado. Instale com: winget install astral-sh.uv  (ou veja https://docs.astral.sh/uv/) e abra um novo terminal."
}

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Warning ".env criado a partir do .env.example. Preencha credenciais, BASE_URL e AGENDA_* e rode este script de novo."
    exit 1
}

Write-Host "Instalando dependências (versões travadas no uv.lock)..."
& uv sync --frozen
if ($LASTEXITCODE -ne 0) { throw "uv sync falhou" }

$canal = (Select-String -Path .env -Pattern '^\s*CANAL_NAVEGADOR\s*=\s*(\S*)' | Select-Object -First 1)
if ($SemNavegador) {
    Write-Host "Sem navegador (motor http): o Chromium não é instalado."
} elseif ($canal -and $canal.Matches[0].Groups[1].Value) {
    Write-Host "Usando o navegador instalado na máquina: $($canal.Matches[0].Groups[1].Value)"
} else {
    # Dentro do projeto (e não no perfil do usuário): o serviço encontra com qualquer conta (core/browser.py)
    $destino = Join-Path $raiz "navegadores"
    $env:PLAYWRIGHT_BROWSERS_PATH = $destino
    if ($Navegadores) {
        Copiar-Navegadores $Navegadores $destino
    } else {
        Write-Host "Baixando o Chromium do Playwright para $destino..."
        & uv run --frozen playwright install chromium
        if ($LASTEXITCODE -ne 0) {
            throw "playwright install falhou. Sem internet? Use -Navegadores <pasta de rede com o Chromium>."
        }
    }
}

Write-Host "Conferindo a agenda do .env..."
& .venv\Scripts\python.exe -m core agenda
if ($LASTEXITCODE -ne 0) { throw "AGENDA_* inválida no .env" }

Write-Host ""
Write-Host "Pronto. Teste com: .\scripts\executar.ps1 -Visivel"
Write-Host "Depois agende (como administrador): .\scripts\agendar.ps1 instalar"
