$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$synthType = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime]
$streamType = [Windows.Media.SpeechSynthesis.SpeechSynthesisStream, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime]
$voice = $synthType::AllVoices | Where-Object Language -eq 'pt-BR' | Select-Object -First 1
if (-not $voice) { throw 'Install a local pt-BR Windows voice to run this fixture.' }

$synth = $synthType::new()
try {
    $synth.Voice = $voice
    $operation = if ($env:WHISPER_DEMO_MODE -eq 'lookup') {
        $synth.SynthesizeSsmlToStreamAsync('<speak version="1.0" xml:lang="pt-BR">Regra pra classe social.<break time="1000ms"/>Regra pra forçar jogada.</speak>')
    } elseif ($env:WHISPER_DEMO_SYSTEM -eq 'vaesen') {
        $synth.SynthesizeTextToStreamAsync('Eu quero forçar a jogada.')
    } else {
        $synth.SynthesizeTextToStreamAsync('Eu quero saltar de um telhado para o outro.')
    }
    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and
            $_.GetParameters().Count -eq 1 -and
            $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
        } | Select-Object -First 1
    $task = $asTask.MakeGenericMethod($streamType).Invoke($null, @($operation))
    $speech = $task.GetAwaiter().GetResult()
    try {
        $stream = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($speech.GetInputStreamAt(0))
        try {
            $player = [System.Media.SoundPlayer]::new($stream)
            try {
                $player.Load()
                Write-Output 'READY'
                $command = [Console]::ReadLine()
                if ($command -notin @('play', 'repeat')) { throw 'Expected play or repeat on stdin.' }
                $player.PlaySync()
                if ($command -eq 'repeat') {
                    Start-Sleep -Milliseconds 1200
                    $player.PlaySync()
                }
                Start-Sleep -Seconds 2
            } finally {
                $player.Dispose()
            }
        } finally {
            $stream.Dispose()
        }
    } finally {
        $speech.Dispose()
    }
} finally {
    $synth.Dispose()
}
