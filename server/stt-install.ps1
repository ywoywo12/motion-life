param([string]$Dest = 'C:\MotionLife-Server')
$ProgressPreference = 'SilentlyContinue'
$stt = Join-Path $Dest 'stt'
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
if (-not (Get-ChildItem $stt -Filter 'ggml-*.bin' -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 100MB })) {
  $urls = @('https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin',
            'https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin')
  foreach ($u in $urls) {
    Write-Host '      downloading Arabic model from' ([uri]$u).Host '...'
    try { Start-BitsTransfer -Source $u -Destination "$model.part" -ErrorAction Stop } catch {
      try { Invoke-WebRequest $u -OutFile "$model.part" } catch { Write-Host '      failed:' $_.Exception.Message; continue } }
    if ((Get-Item "$model.part").Length -gt 100MB) { Move-Item -Force "$model.part" $model; break }
  }
}
if ((Test-Path (Join-Path $stt 'whisper-server.exe')) -and (Get-ChildItem $stt -Filter 'ggml-*.bin' | Where-Object { $_.Length -gt 100MB })) { Write-Host '      voice engine ready.' }
else { Write-Host '      Voice engine NOT installed (download blocked?). Everything else works. Send a photo of this window.' }
