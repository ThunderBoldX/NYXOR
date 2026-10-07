param([ValidateSet('Check', 'Close', 'Access')][string]$Mode = 'Check')
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Select-NyxorProcesses {
    param([object[]]$Processes, [string]$Root, [int]$InstallerId = 0)
    $base = [IO.Path]::GetFullPath($Root)
    $allowed = @(
        [IO.Path]::GetFullPath((Join-Path $base 'NYXOR.exe')),
        [IO.Path]::GetFullPath((Join-Path $base 'resources/engine/nyxor-engine.exe'))
    )
    @($Processes | Where-Object {
        $candidate = $_
        $candidate.ProcessId -ne $PID -and $candidate.ProcessId -ne $InstallerId -and $candidate.ExecutablePath -and
        @($allowed | Where-Object { [string]::Equals($_, $candidate.ExecutablePath, [StringComparison]::OrdinalIgnoreCase) }).Count -gt 0
    })
}

# Dot-sourcing allows the path-selection rules to be checked without stopping processes.
if ($MyInvocation.InvocationName -eq '.') { return }

try {
    $root = [Environment]::GetEnvironmentVariable('NYXOR_INSTALL_TARGET', 'Process')
    if ([string]::IsNullOrWhiteSpace($root)) { throw 'Missing installation directory' }
    $root = [IO.Path]::GetFullPath($root)
    if ($Mode -eq 'Access') {
        # Check the selected directory, or its nearest existing parent for a
        # fresh install, before launching any old uninstaller. The random
        # probe is removed by Windows when its handle closes.
        $directory = $root
        while (!(Test-Path -LiteralPath $directory -PathType Container)) {
            $parent = [IO.Directory]::GetParent($directory)
            if ($null -eq $parent) { throw 'No existing installation parent' }
            $directory = $parent.FullName
        }
        $probe = Join-Path $directory ('.nyxor-access-' + [Guid]::NewGuid().ToString('N') + '.tmp')
        try {
            $stream = [IO.FileStream]::new($probe, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write,
                [IO.FileShare]::None, 1, [IO.FileOptions]::DeleteOnClose)
            $stream.Dispose()
            exit 0
        } catch [UnauthorizedAccessException] {
            Write-Output 'Administrator permissions are required to update this installation folder.'
            exit 4
        }
    }
    $appFile = Join-Path $root 'NYXOR.exe'
    $engineFile = Join-Path $root 'resources/engine/nyxor-engine.exe'
    $installerId = 0
    $null = [int]::TryParse([Environment]::GetEnvironmentVariable('NYXOR_INSTALLER_PID', 'Process'), [ref]$installerId)
    # A fresh install cannot have a process mapped from either executable.
    if (!(Test-Path -LiteralPath $appFile) -and !(Test-Path -LiteralPath $engineFile)) {
        if ($Mode -eq 'Check') { exit 1 } else { exit 0 }
    }
    $matches = @(Select-NyxorProcesses -Processes @(Get-CimInstance Win32_Process) -Root $root -InstallerId $installerId)
    if ($Mode -eq 'Check') { if ($matches.Count) { exit 0 } else { exit 1 } }
    if (!$matches.Count) { exit 0 }

    # Ask a new shell to request a graceful exit from the installed instance.
    if (@($matches | Where-Object { [string]::Equals($_.ExecutablePath, $appFile, [StringComparison]::OrdinalIgnoreCase) }).Count) {
        try {
            $quit = Start-Process -FilePath $appFile -ArgumentList '--quit-for-update' -WindowStyle Hidden -PassThru
            $null = $quit.WaitForExit(4000)
        } catch { }
        $deadline = [DateTime]::UtcNow.AddSeconds(12)
        do {
            $matches = @(Select-NyxorProcesses -Processes @(Get-CimInstance Win32_Process) -Root $root -InstallerId $installerId)
            if (!$matches.Count) { exit 0 }
            Start-Sleep -Milliseconds 250
        } while ([DateTime]::UtcNow -lt $deadline)
    }

    # Older shells or orphan engines have no graceful endpoint. Recheck the
    # exact image path and PID before touching each process; never use a folder prefix.
    foreach ($candidate in $matches) {
        $current = @(Get-CimInstance Win32_Process -Filter "ProcessId=$($candidate.ProcessId)")
        $verified = @(Select-NyxorProcesses -Processes $current -Root $root -InstallerId $installerId)
        if ($verified.Count -and [string]::Equals($verified[0].ExecutablePath, $candidate.ExecutablePath, [StringComparison]::OrdinalIgnoreCase)) {
            Stop-Process -Id $candidate.ProcessId -Force -ErrorAction Stop
        }
    }
    Start-Sleep -Milliseconds 300
    if (@(Select-NyxorProcesses -Processes @(Get-CimInstance Win32_Process) -Root $root -InstallerId $installerId).Count) { exit 3 }
    exit 0
} catch {
    # Distinguish an inspection/permission error from a running application.
    Write-Output 'Windows could not inspect or close NYXOR processes.'
    exit 2
}
