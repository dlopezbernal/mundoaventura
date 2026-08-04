<#
    scripts/dev.ps1 — Arranque de desarrollo (Windows PowerShell)
    =============================================================
    Levanta backend (FastAPI/uvicorn) y frontend (Vite) a la vez, cada uno en su
    propia ventana de PowerShell, usando el entorno reproducible de `uv`.

    Uso (desde la raíz del proyecto):
        .\scripts\dev.ps1              # backend + frontend
        .\scripts\dev.ps1 -Solo back  # solo backend
        .\scripts\dev.ps1 -Solo front # solo frontend

    Requisitos previos (una sola vez):
        uv sync                                   # dependencias del backend (.venv)
        cd frontend-react; npm install; cd ..     # dependencias del frontend
#>
[CmdletBinding()]
param(
    [ValidateSet("todo", "back", "front")]
    [string]$Solo = "todo"
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "No se encuentra 'uv' en el PATH. Instálalo: https://docs.astral.sh/uv/"
    exit 1
}

function Start-Backend {
    Write-Host "→ Backend en http://127.0.0.1:8000  (docs en /docs)" -ForegroundColor Cyan
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "Set-Location '$raiz'; uv run uvicorn backend.main:app --reload"
    )
}

function Start-Frontend {
    $front = Join-Path $raiz "frontend-react"
    if (-not (Test-Path (Join-Path $front "node_modules"))) {
        Write-Warning "Falta node_modules en frontend-react. Ejecuta: cd frontend-react; npm install"
    }
    Write-Host "→ Frontend en http://localhost:5173  (Vite)" -ForegroundColor Cyan
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "Set-Location '$front'; npm run dev"
    )
}

switch ($Solo) {
    "back"  { Start-Backend }
    "front" { Start-Frontend }
    "todo"  { Start-Backend; Start-Frontend }
}

Write-Host "Listo. Cada proceso corre en su propia ventana; ciérralas para parar." -ForegroundColor Green
