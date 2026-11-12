param(
    [switch]$Cozy,
    [ValidateRange(1, 65535)]
    [int]$Port = 8766
)

$ErrorActionPreference = 'Stop'
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
    & .migration\local-preview-env\Scripts\python.exe -m uvicorn cozy_preview_api:app --app-dir app --host 127.0.0.1 --port $Port
    exit $LASTEXITCODE
}

& .migration\local-preview-env\Scripts\python.exe -m streamlit run app/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
