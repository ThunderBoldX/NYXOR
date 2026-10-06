$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../installer/processes.ps1')
$root = "C:\Program Files (x86)\NYXOR's app"
$fixtures = @(
    [pscustomobject]@{ProcessId=1;ExecutablePath="$root\NYXOR.exe"},
    [pscustomobject]@{ProcessId=2;ExecutablePath="$root\resources\engine\nyxor-engine.exe"},
    [pscustomobject]@{ProcessId=3;ExecutablePath="$root\NYXOR-Windows-Setup.exe"},
    [pscustomobject]@{ProcessId=4;ExecutablePath="$root\Uninstall NYXOR.exe"},
    [pscustomobject]@{ProcessId=5;ExecutablePath="$root-backup\NYXOR.exe"},
    [pscustomobject]@{ProcessId=6;ExecutablePath='C:\Other\NYXOR.exe'},
    [pscustomobject]@{ProcessId=$PID;ExecutablePath="$root\NYXOR.exe"},
    [pscustomobject]@{ProcessId=7;ExecutablePath=$null},
    [pscustomobject]@{ProcessId=8;ExecutablePath="$($root.ToLowerInvariant())\nyxor.EXE"}
)
$found = @(Select-NyxorProcesses -Processes $fixtures -Root $root)
if (($found.ProcessId -join ',') -ne '1,2,8') { throw 'Incorrect process selection' }
if (@(Select-NyxorProcesses -Processes @() -Root $root).Count) { throw 'Empty selection failed' }
if (@(Select-NyxorProcesses -Processes $fixtures -Root $root -InstallerId 1).ProcessId -contains 1) { throw 'Installer PID was not excluded' }
Write-Output 'Installer path checks passed: exact app/engine only; setup, uninstaller, sibling paths, self and missing paths excluded.'
