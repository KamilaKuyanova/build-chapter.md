# Озвучка голосом Windows (OneCore: Microsoft Pavel, Irina) с метками слов. Работает в обычном PowerShell 5.1, без установки.
# Вход: -Job файл JSON {voice, fallback, rate, phrases:[...], out}. Выход: phrase_NNN.wav и words.json.
param([string]$Job)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $type) { $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op)); $t.Wait(); $t.Result }
$j = Get-Content -Raw -Encoding UTF8 $Job | ConvertFrom-Json
$s = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$all = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices
$v = $all | Where-Object { $_.DisplayName -eq $j.voice } | Select-Object -First 1
if (-not $v) { $v = $all | Where-Object { $_.DisplayName -eq $j.fallback } | Select-Object -First 1 }
if (-not $v) { throw "нет голоса $($j.voice) и запасного $($j.fallback)" }
$s.Voice = $v
$s.Options.SpeakingRate = [double]$j.rate
$s.Options.IncludeWordBoundaryMetadata = $true
$s.Options.AppendedSilence = 'Min'
$words = @()
for ($i = 0; $i -lt $j.phrases.Count; $i++) {
  $st = Await ($s.SynthesizeTextToStreamAsync($j.phrases[$i])) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
  $r = New-Object Windows.Storage.Streams.DataReader($st.GetInputStreamAt(0))
  $null = Await ($r.LoadAsync([uint32]$st.Size)) ([uint32])
  $b = New-Object byte[] $st.Size
  $r.ReadBytes($b)
  [IO.File]::WriteAllBytes((Join-Path $j.out ('phrase_{0:000}.wav' -f $i)), $b)
  $w = @()
  foreach ($tr in $st.TimedMetadataTracks) { if ($tr.Id -eq 'SpeechWord') { foreach ($c in $tr.Cues) { $w += @{ t = $c.StartTime.TotalSeconds; w = $c.Text } } } }
  $words += , $w
}
ConvertTo-Json @{ voice = $v.DisplayName; words = $words } -Depth 6 | Out-File -Encoding utf8 (Join-Path $j.out 'words.json')
Write-Output $v.DisplayName
