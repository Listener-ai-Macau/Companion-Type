param([Parameter(Mandatory=$true)][string]$OutputWav)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Speech
$speaker=[System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
    $voice=$null
    foreach($candidate in $speaker.GetInstalledVoices()) {
        if($candidate.Enabled -and $candidate.VoiceInfo.Culture.Name.StartsWith('zh-')) { $voice=$candidate.VoiceInfo;break }
    }
    if($null -eq $voice){throw 'No installed Chinese SAPI voice; no silent substitute.'}
    $speaker.SelectVoice($voice.Name)
    $speaker.Rate=-1
    $format=[System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(16000,[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,[System.Speech.AudioFormat.AudioChannel]::Mono)
    $speaker.SetOutputToWaveFile($OutputWav,$format)
    $speaker.Speak('这是电脑合成的公开录音示例。周五下午三点，我们和小林核对演示内容。李明周五上午十点前发出材料，小林周五中午十二点前确认名单。设备预算还没决定，等演示之后再讨论。')
    [System.Console]::WriteLine('Computer generated Chinese WAV written; no speaker playback or microphone capture.')
} finally {$speaker.Dispose()}
