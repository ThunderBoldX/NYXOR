param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$desktopRoot = Split-Path $PSScriptRoot -Parent
$coreRoot = Join-Path (Split-Path $desktopRoot -Parent) 'core'
& $Python -m PyInstaller --noconfirm --clean --onedir --console --name nyxor-engine --paths $coreRoot --collect-submodules nyxor --collect-submodules aiohttp --collect-all rich --collect-submodules yarl --hidden-import nyxor_core --hidden-import nyxor_miner --hidden-import nyxor_channels --hidden-import nyxor_campaigns --hidden-import nyxor_points --hidden-import nyxor_rewards --hidden-import nyxor_player --hidden-import constants --hidden-import version --add-data "$coreRoot/nyxor/locales;locales" --distpath "$desktopRoot/engine" --workpath "$desktopRoot/build" --specpath "$desktopRoot/build" "$desktopRoot/backend.py"
if ($LASTEXITCODE -ne 0) { throw 'Engine build failed' }
