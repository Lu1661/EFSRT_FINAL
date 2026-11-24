param([int]$Puerto = 5060, [switch]$Https)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& $python -m libreria preparar --demo
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$argumentos = @('-m', 'libreria', 'servir', '--puerto', $Puerto)
if ($Https) { $argumentos += '--https' }
& $python @argumentos
exit $LASTEXITCODE
