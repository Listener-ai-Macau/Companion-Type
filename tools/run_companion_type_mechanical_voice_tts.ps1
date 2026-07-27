# Generate a mechanical/SAPI speech WAV for Companion-Type minutes acceptance.
param(
  [Parameter(Mandatory = $true)][string]$OutWav,
  [Parameter(Mandatory = $true)][string]$Text,
  [string]$OutTranscript = ""
)

$ErrorActionPreference = "Stop"
$outDir = Split-Path -Parent $OutWav
if ($outDir -and -not (Test-Path $outDir)) {
  New-Item -ItemType Directory -Force -Path $outDir | Out-Null
}

Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
  # Prefer a clear English voice for deterministic mechanical speech.
  $voices = $synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo }
  $preferred = $voices | Where-Object { $_.Culture.Name -like "en-*" } | Select-Object -First 1
  if ($preferred) {
    $synth.SelectVoice($preferred.Name)
  }
  $synth.Rate = -1
  $synth.Volume = 100
  $synth.SetOutputToWaveFile($OutWav)
  $synth.Speak($Text)
}
finally {
  $synth.Dispose()
}

if (-not (Test-Path $OutWav)) {
  throw "TTS did not write $OutWav"
}

if (-not $OutTranscript) {
  $OutTranscript = [System.IO.Path]::ChangeExtension($OutWav, ".transcript.txt")
}
# Sidecar is the offline ASR stand-in bound to the spoken script (mechanical accept).
Set-Content -Path $OutTranscript -Value $Text -Encoding UTF8

Write-Output "tts_wav=$OutWav"
Write-Output "tts_transcript=$OutTranscript"
Write-Output "tts_bytes=$((Get-Item $OutWav).Length)"
