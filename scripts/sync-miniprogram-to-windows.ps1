# 在 Windows PowerShell 上调用：从 WSL UNC 镜像到本机 NTFS。
# 日常更推荐在 WSL 里跑：bash scripts/sync-miniprogram-to-windows.sh
param(
  [string]$WslDistro = "Ubuntu-22.04",
  [string]$WslRepo = "/home/hayden/code/tenclip",
  [string]$Dst = "$env:USERPROFILE\code\tenclip-miniprogram"
)

$ErrorActionPreference = "Stop"

$repoWin = ($WslRepo -replace "/", "\").TrimStart("\")
$srcUnc = "\\wsl.localhost\$WslDistro\$repoWin\miniprogram"

Write-Host "SRC: $srcUnc"
Write-Host "DST: $Dst"

if (-not (Test-Path -LiteralPath $srcUnc)) {
  throw "Source not found: $srcUnc (is WSL running?)"
}

New-Item -ItemType Directory -Force -Path $Dst | Out-Null

robocopy $srcUnc $Dst /MIR /XD node_modules /XF project.private.config.json /NFL /NDL /NJH /NJS /nc /ns /np
if ($LASTEXITCODE -ge 8) {
  throw "robocopy failed with code $LASTEXITCODE"
}

$feed = Join-Path $Dst "pages\feed\index.wxml"
if (-not (Test-Path -LiteralPath $feed)) {
  throw "Sync incomplete: missing $feed"
}

Write-Host "OK. Open in WeChat DevTools:"
Write-Host "  $Dst"
exit 0
