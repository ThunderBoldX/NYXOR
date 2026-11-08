param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$desktopRoot = Split-Path $PSScriptRoot -Parent
$coreRoot = Join-Path (Split-Path $desktopRoot -Parent) 'core'
# Some bundled Python distributions supply an adjacent SSL distrust list.
$sslDenylist = & $Python -c "import pathlib, ssl; print(pathlib.Path(ssl.__file__).with_name('codex-rejected-cas.pem'))"
$extraData = @()
if (Test-Path -LiteralPath $sslDenylist -PathType Leaf) { $extraData = @('--add-data', "$sslDenylist;.") }
& $Python -m PyInstaller @extraData --noconfirm --clean --onedir --console --name nyxor-engine --paths $coreRoot --collect-submodules nyxor --collect-submodules aiohttp --collect-all rich --collect-submodules yarl --hidden-import nyxor_core --hidden-import nyxor_miner --hidden-import nyxor_channels --hidden-import nyxor_campaigns --hidden-import nyxor_points --hidden-import nyxor_rewards --hidden-import nyxor_player --hidden-import constants --hidden-import version --add-data "$coreRoot/nyxor/locales;locales" --distpath "$desktopRoot/engine" --workpath "$desktopRoot/build" --specpath "$desktopRoot/build" "$desktopRoot/backend.py"
if ($LASTEXITCODE -ne 0) { throw 'Engine build failed' }
