param(
    [string]$Version = '0.13.0'
)
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$testInstall = [IO.Path]::GetFullPath((Join-Path $workspaceRoot 'build/installer-check'))
$testData = [IO.Path]::GetFullPath((Join-Path $workspaceRoot 'build/installer-user-data'))
$reportPath = Join-Path $workspaceRoot 'build/installed-smoke.json'
if (-not $testInstall.StartsWith([IO.Path]::GetFullPath((Join-Path $workspaceRoot 'build')) + [IO.Path]::DirectorySeparatorChar)) {
    throw 'Installer test path is outside the workspace build folder.'
}
$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{317DB0EA-E901-48EA-AE3E-8197C9D100A5}_is1'
if (Test-Path -LiteralPath $uninstallKey) {
    throw 'A GK Tuner installation is already registered. Do not overwrite it during a packaging test.'
}
$installer = Join-Path $workspaceRoot "release/$Version/GK-Tuner-$Version-Setup-x64.exe"
$result = [ordered]@{ installed = $false; launched = $false; uninstalled = $false; user_data_preserved = $false; hardware_connections = 0 }
$env:GKTUNER_DATA_DIR = $testData
$env:QT_QPA_PLATFORM = 'windows'
$env:PYTHONPATH = ''
$env:PYTHONHOME = ''
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
New-Item -ItemType Directory -Path $testData -Force | Out-Null
Set-Content -LiteralPath (Join-Path $testData 'keep-my-settings.txt') -Value 'Uninstall must preserve user data.'
try {
    $install = Start-Process -FilePath $installer -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS',('/DIR="' + $testInstall + '"'),('/LOG="' + (Join-Path $workspaceRoot 'build/install-test.log') + '"')) -WindowStyle Hidden -Wait -PassThru
    if ($install.ExitCode -ne 0) { throw "Installer failed with code $($install.ExitCode)" }
    $result.installed = (Test-Path -LiteralPath (Join-Path $testInstall 'GK Tuner.exe')) -and (Test-Path -LiteralPath $uninstallKey)
    if (-not $result.installed) { throw 'Installed EXE/uninstall registration was not found.' }
    $check = Start-Process -FilePath (Join-Path $testInstall 'GK Tuner.exe') -ArgumentList @('--smoke-test',('"' + $reportPath + '"')) -WindowStyle Hidden -Wait -PassThru
    if ($check.ExitCode -ne 0) { throw "Installed app smoke check failed: $(Get-Content -LiteralPath $reportPath -Raw)" }
    $result.launched = (Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json).passed
} finally {
    $uninstaller = Join-Path $testInstall 'unins000.exe'
    if (Test-Path -LiteralPath $uninstaller) {
        $uninstall = Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/LOG="' + (Join-Path $workspaceRoot 'build/uninstall-test.log') + '"')) -WindowStyle Hidden -Wait -PassThru
        $deadline = [DateTime]::UtcNow.AddSeconds(15)
        while (((Test-Path -LiteralPath (Join-Path $testInstall 'GK Tuner.exe')) -or (Test-Path -LiteralPath $uninstallKey)) -and [DateTime]::UtcNow -lt $deadline) {
            Start-Sleep -Milliseconds 100
        }
        $result.uninstalled = -not (Test-Path -LiteralPath (Join-Path $testInstall 'GK Tuner.exe')) -and -not (Test-Path -LiteralPath $uninstallKey)
    }
    $result.user_data_preserved = Test-Path -LiteralPath (Join-Path $testData 'keep-my-settings.txt')
    $result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $workspaceRoot 'build/installer-result.json')
}
$result | ConvertTo-Json
if (-not ($result.installed -and $result.launched -and $result.uninstalled -and $result.user_data_preserved)) {
    throw 'Installer lifecycle verification failed.'
}
