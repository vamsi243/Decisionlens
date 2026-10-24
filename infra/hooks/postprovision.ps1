# Write the API address into the board's runtime config (web/public/config.json).
$ErrorActionPreference = "Stop"
$api = (azd env get-value SERVICE_API_URI).Trim()
New-Item -ItemType Directory -Force -Path "web/public" | Out-Null
@{ apiUrl = $api } | ConvertTo-Json -Compress | Set-Content -Encoding utf8NoBOM "web/public/config.json"
Write-Host "board will talk to $api"
