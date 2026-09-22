param([int]$Port = 8794)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
& "$repoRoot/.venv/Scripts/python.exe" "$repoRoot/main.py" --cpu --listen 127.0.0.1 --port $Port --disable-auto-launch --disable-api-nodes --disable-all-custom-nodes --whitelist-custom-nodes agent_art_bridge --extra-model-paths-config "$PSScriptRoot/paths.yaml"
exit $LASTEXITCODE
