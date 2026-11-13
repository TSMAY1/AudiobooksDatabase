param(
    [switch]$Cozy,
    [ValidateRange(1, 65535)]
    [int]$Port = 8766,
    [string]$HomeWiFiAddress
)

$ErrorActionPreference = 'Stop'
if ($HomeWiFiAddress -and -not $Cozy) {
    throw '-HomeWiFiAddress requires -Cozy.'
}

$listenAddress = '127.0.0.1'
if ($HomeWiFiAddress) {
    $parsedAddress = $null
    if (-not [System.Net.IPAddress]::TryParse($HomeWiFiAddress, [ref]$parsedAddress) -or
        $parsedAddress.ToString() -ne $HomeWiFiAddress -or
        $HomeWiFiAddress -notmatch '^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)') {
        throw 'Enter the private IPv4 address for the home network adapter. Use ipconfig to find it.'
    }
    $listenAddress = $HomeWiFiAddress
}

Set-Location (Split-Path $PSScriptRoot -Parent)
$env:DB_AUTH_MODE = 'azure_cli'
$env:DB_DRIVER = 'ODBC Driver 18 for SQL Server'
$env:DB_SERVER = 'sqlaudiobooks1541.database.windows.net'
$env:DB_NAME = 'free-sql-db-9991615'
$env:ASSET_STORAGE_BACKEND = 'azure'
$env:AZURE_STORAGE_ACCOUNT_NAME = 'staudiobooks1541'
$env:AZURE_STORAGE_CONTAINER = 'assets'
$env:AUTH_REQUIRED = 'false'
if ($Cozy) {
    $env:COZY_HOME_WIFI_ADDRESS = $HomeWiFiAddress
    if ($HomeWiFiAddress) {
        Write-Host "Open http://${listenAddress}:${Port}/ on your home Wi-Fi. Keep this window open while using the app."
    }
    & .migration\local-preview-env\Scripts\python.exe -m uvicorn cozy_preview_api:app --app-dir app --host $listenAddress --port $Port
    exit $LASTEXITCODE
}

& .migration\local-preview-env\Scripts\python.exe -m streamlit run app/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
