# 로컬 PNG → docs/ticker.png → git push (카페 대문은 Pages의 ticker.png URL 사용)
# 사용: .\push_ticker.ps1 C:\path\to\image.png
#       .\push_ticker.ps1   # 이미 복사된 docs\ticker.png 만 푸시

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
if ($args.Count -ge 1) {
    python scripts/push_ticker.py $args[0]
} else {
    python scripts/push_ticker.py
}
exit $LASTEXITCODE
