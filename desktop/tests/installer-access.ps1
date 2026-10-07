param([Parameter(Mandatory=$true)][string]$TestRoot, [string]$NativeCheckExe = '')
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../.local/installer-tests'))
$resolved = [IO.Path]::GetFullPath($TestRoot)
if (!$resolved.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Permission fixtures must stay inside .local/installer-tests'
}
$null = New-Item -ItemType Directory -Path $resolved -Force
$script = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../installer/processes.ps1'))
$powershell = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
function Check-Access([string]$Directory, [int]$Expected) {
    $env:NYXOR_INSTALL_TARGET = $Directory
    & $powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $script -Mode Access
    if ($LASTEXITCODE -ne $Expected) { throw "Unexpected folder access result: $LASTEXITCODE instead of $Expected" }
}
Check-Access $resolved 0
Check-Access (Join-Path $resolved 'not-created-yet/NYXOR') 0
if (@(Get-ChildItem -LiteralPath $resolved -Filter '.nyxor-access-*' -Force).Count) { throw 'Access probe was not removed' }
if (Test-Path -LiteralPath (Join-Path $resolved 'not-created-yet')) { throw 'Fresh-install access check created directories' }
$denied = Join-Path $resolved 'protected-install'
$null = New-Item -ItemType Directory -Path $denied
$savedAcl = [IO.Directory]::GetAccessControl($denied)
try {
    $acl = [IO.Directory]::GetAccessControl($denied)
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $rule = [Security.AccessControl.FileSystemAccessRule]::new($sid,
        [Security.AccessControl.FileSystemRights]::CreateFiles, [Security.AccessControl.AccessControlType]::Deny)
    $acl.AddAccessRule($rule)
    [IO.Directory]::SetAccessControl($denied, $acl)
    Check-Access $denied 4
    if ($NativeCheckExe) {
        Write-Output 'Starting compiled permission guard fixture.'
        $env:NYXOR_ACCESS_FIXTURE = $denied
        # Use CreateProcess for this headless fixture, as the integration
        # harness does, instead of ShellExecute and its interactive prompts.
        $start = [Diagnostics.ProcessStartInfo]::new($NativeCheckExe, '/S')
        $start.UseShellExecute = $false
        $start.CreateNoWindow = $true
        $start.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
        $process = [Diagnostics.Process]::Start($start)
        Write-Output "Compiled fixture process: $($process.Id)"
        if (!$process.WaitForExit(10000)) {
            $process.Kill()
            throw 'Compiled setup permission check did not exit in silent mode'
        }
        if ($process.ExitCode -ne 1) { throw 'Compiled setup did not stop at the folder permission guard' }
        if (@(Get-ChildItem -LiteralPath $denied -Force).Count) { throw 'Blocked setup changed the protected fixture' }
    }
} finally {
    [IO.Directory]::SetAccessControl($denied, $savedAcl)
}
Write-Output 'Folder access checks passed: writable, fresh parent, protected folder and probe cleanup.'
