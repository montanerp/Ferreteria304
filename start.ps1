<#
.SYNOPSIS
    Arranca la demo de la ferreteria (Telegram): levanta ngrok, sincroniza el
    webhook en .env y corre la app (behemot_framework) en el puerto 8000.

.DESCRIPTION
    Automatiza el arranque en Windows:
      1. (Opcional) Inicia Redis si redis-server.exe esta presente.
      2. Inicia ngrok http 8000 (si no hay uno corriendo ya).
      3. Lee la URL publica desde la API local de ngrok (http://127.0.0.1:4040).
      4. Actualiza TELEGRAM_WEBHOOK_URL en .env con esa URL + /webhook.
      5. Fija PYTHONUTF8=1 (evita UnicodeEncodeError con emojis de startup).
      6. Levanta la app con el python del venv.

.EXAMPLE
    .\start.ps1
#>

[CmdletBinding()]
param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$envFile    = Join-Path $here ".env"
$python     = Join-Path $here ".venv\Scripts\python.exe"
$ngrokApi   = "http://127.0.0.1:4040/api/tunnels"
$redisDir   = Join-Path $here "redis"
$redisExe   = Join-Path $redisDir "redis-server.exe"
$redisCli   = Join-Path $redisDir "redis-cli.exe"

# --- Validaciones basicas --------------------------------------------------
if (-not (Test-Path $envFile)) { throw "No se encontro .env en $here" }
if (-not (Test-Path $python))  { throw "No se encontro el venv en $python (crea uno: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt)" }

# --- 0. Asegurar que Redis (memoria de conversaciones) este corriendo ------
if (Test-Path $redisExe) {
    $redisUp = $false
    if (Test-Path $redisCli) {
        try { if ((& $redisCli ping 2>$null) -eq "PONG") { $redisUp = $true } } catch {}
    }
    if ($redisUp) {
        Write-Host "Redis ya estaba corriendo (PONG)." -ForegroundColor Yellow
    } else {
        Write-Host "Iniciando Redis (redis-server.exe) ..." -ForegroundColor Cyan
        Start-Process -FilePath $redisExe -WindowStyle Minimized
        Start-Sleep -Seconds 2
        if ((Test-Path $redisCli) -and ((& $redisCli ping 2>$null) -eq "PONG")) {
            Write-Host "Redis listo (PONG)." -ForegroundColor Green
        } else {
            Write-Host "ADVERTENCIA: Redis no respondio PONG. La app correra sin memoria persistente." -ForegroundColor Red
        }
    }
} else {
    Write-Host "AVISO: no hay redis-server.exe en $redisDir. La demo corre sin memoria persistente (opcional)." -ForegroundColor Yellow
}

# --- 1. Asegurar que ngrok este corriendo ----------------------------------
function Get-NgrokUrl {
    try {
        $resp = Invoke-RestMethod -Uri $ngrokApi -TimeoutSec 3
        $tunnel = $resp.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1
        if ($null -eq $tunnel) { $tunnel = $resp.tunnels | Select-Object -First 1 }
        return $tunnel.public_url
    } catch {
        return $null
    }
}

$publicUrl = Get-NgrokUrl
if ($publicUrl) {
    Write-Host "ngrok ya estaba corriendo: $publicUrl" -ForegroundColor Yellow
} else {
    Write-Host "Iniciando ngrok http $Port ..." -ForegroundColor Cyan
    Start-Process -FilePath "ngrok" -ArgumentList "http", "$Port" -WindowStyle Minimized

    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 1
        $publicUrl = Get-NgrokUrl
        if ($publicUrl) { break }
    }
    if (-not $publicUrl) {
        throw "ngrok no expuso un tunel a tiempo. Revisa http://127.0.0.1:4040"
    }
    Write-Host "ngrok listo: $publicUrl" -ForegroundColor Green
}

$webhookUrl = "$publicUrl/webhook"

# --- 2. Sincronizar URLs publicas (ngrok) en .env ---------------------------
$lines = Get-Content $envFile
$foundTg = $false
$newLines = foreach ($line in $lines) {
    if ($line -match '^\s*TELEGRAM_WEBHOOK_URL\s*=') {
        $foundTg = $true
        "TELEGRAM_WEBHOOK_URL=$webhookUrl"
    } elseif ($line -match '^\s*HANDOFF_CALLBACK_URL\s*=') {
        "HANDOFF_CALLBACK_URL=$publicUrl"
    } else {
        $line
    }
}
if (-not $foundTg) { $newLines += "TELEGRAM_WEBHOOK_URL=$webhookUrl" }

Set-Content -Path $envFile -Value $newLines -Encoding utf8
Write-Host "TELEGRAM_WEBHOOK_URL actualizado -> $webhookUrl" -ForegroundColor Green
if ($newLines -match '^\s*HANDOFF_CALLBACK_URL\s*=') {
    Write-Host "HANDOFF_CALLBACK_URL actualizado -> $publicUrl" -ForegroundColor Green
}

# --- 3. Levantar la app -----------------------------------------------------
$env:PYTHONUTF8 = "1"
Write-Host "Levantando la demo de ferreteria en el puerto $Port (Ctrl+C para detener)..." -ForegroundColor Cyan
& $python (Join-Path $here "main.py")
