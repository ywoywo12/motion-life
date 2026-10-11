param([string]$Dest = 'C:\MotionLife-Server')
$ProgressPreference = 'SilentlyContinue'
$stt = Join-Path $Dest 'stt'
# Visual C++ runtime (needed by the voice engine)
$sys = Join-Path $env:windir 'System32'
if (-not ((Test-Path (Join-Path $sys 'msvcp140.dll')) -and (Test-Path (Join-Path $sys 'vcruntime140_1.dll')))) {
  Write-Host '      installing Microsoft Visual C++ runtime...'
  try { winget install -e --id Microsoft.VCRedist.2015+.x64 --accept-source-agreements --accept-package-agreements --silent | Out-Null } catch {}
  if (-not (Test-Path (Join-Path $sys 'vcruntime140_1.dll'))) {
    try { Invoke-WebRequest 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile "$env:TEMP\vc_redist.x64.exe"; Start-Process "$env:TEMP\vc_redist.x64.exe" -ArgumentList '/install','/quiet','/norestart' -Wait } catch { Write-Host '      VC++ runtime download failed:' $_.Exception.Message }
  }
}
New-Item -ItemType Directory -Force $stt | Out-Null
if (-not (Test-Path (Join-Path $stt 'whisper-server.exe'))) {
  Write-Host '      downloading engine...'
  try {
    Invoke-WebRequest 'https://github.com/ggml-org/whisper.cpp/releases/download/b4938/whisper-bin-x64.zip' -OutFile "$env:TEMP\wb.zip"
    Remove-Item -Recurse -Force "$env:TEMP\wb" -ErrorAction SilentlyContinue
    Expand-Archive -Force "$env:TEMP\wb.zip" "$env:TEMP\wb"
    Copy-Item -Force "$env:TEMP\wb\Release\*" $stt
  } catch { Write-Host '      ENGINE DOWNLOAD FAILED:' $_.Exception.Message }
}
$model = Join-Path $stt 'ggml-large-v3-turbo-q5_0.bin'
if (-not (Get-ChildItem $stt -Filter 'ggml-*.bin' -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 100MB -and $_.Name -notlike '*silero*' })) {
  $urls = @('https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin',
            'https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin')
  foreach ($u in $urls) {
    Write-Host '      downloading Arabic model from' ([uri]$u).Host '...'
    try { Start-BitsTransfer -Source $u -Destination "$model.part" -ErrorAction Stop } catch {
      try { Invoke-WebRequest $u -OutFile "$model.part" } catch { Write-Host '      failed:' $_.Exception.Message; continue } }
    if ((Get-Item "$model.part").Length -gt 100MB) { Move-Item -Force "$model.part" $model; break }
  }
}
$vad = Join-Path $stt 'ggml-silero-v5.1.2.bin'
if (-not (Test-Path $vad)) {
  foreach ($u in @('https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v5.1.2.bin','https://hf-mirror.com/ggml-org/whisper-vad/resolve/main/ggml-silero-v5.1.2.bin')) {
    try { Invoke-WebRequest $u -OutFile "$vad.part"; if ((Get-Item "$vad.part").Length -gt 100KB) { Move-Item -Force "$vad.part" $vad; Write-Host '      speech detector ready.'; break } } catch { Write-Host '      speech detector download failed (optional).' }
  }
}
# self-test of the engine (result saved for diagnosis)
$chk = Join-Path $Dest 'data\stt-check.txt'
New-Item -ItemType Directory -Force (Join-Path $Dest 'data') | Out-Null
try {
  $p = Start-Process -FilePath (Join-Path $stt 'whisper-server.exe') -ArgumentList '--help' -WorkingDirectory $stt -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$chk.out" -RedirectStandardError "$chk.err"
  "exit=$($p.ExitCode)`r`n" + (Get-Content "$chk.out" -Raw) + (Get-Content "$chk.err" -Raw) | Set-Content -Encoding UTF8 $chk
  if ($p.ExitCode -eq 0) { Write-Host '      engine self-test OK.' } else { Write-Host '      engine self-test FAILED (exit' $p.ExitCode ')' }
} catch { "start failed: $($_.Exception.Message)" | Set-Content -Encoding UTF8 $chk; Write-Host '      engine self-test FAILED:' $_.Exception.Message }
Get-ChildItem $stt | Select-Object Name, Length | Out-String | Add-Content -Encoding UTF8 $chk
if ((Test-Path (Join-Path $stt 'whisper-server.exe')) -and (Get-ChildItem $stt -Filter 'ggml-*.bin' | Where-Object { $_.Length -gt 100MB })) { Write-Host '      voice engine ready.' }
else { Write-Host '      Voice engine NOT installed (download blocked?). Everything else works. Send a photo of this window.' }
