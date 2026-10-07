[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = 'Stop'
$launcher = Get-Command pyw.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$launcherArgs = '-3 '
if (-not $launcher) {
    $launcher = Get-Command pythonw.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    $launcherArgs = ''
}
if (-not $launcher) {
    throw 'Python 3 was not found. Install Python with tkinter and enable its launcher or add Python to PATH.'
}
$projectRoot = $PSScriptRoot
$clockPath = Join-Path $projectRoot 'clock.pyw'
if (-not (Test-Path -LiteralPath $clockPath -PathType Leaf)) {
    throw 'clock.pyw must be in the same directory as this script.'
}
$startup = [Environment]::GetFolderPath('Startup')
$name = -join [char[]](0x771F, 0x5B9E, 0x65F6, 0x95F4)   # "真实时间"
$lnkPath = Join-Path $startup ($name + '.lnk')
if ($PSCmdlet.ShouldProcess($lnkPath, 'Create or update desktop clock autostart shortcut')) {
    $ws = New-Object -ComObject WScript.Shell
    $lnk = $ws.CreateShortcut($lnkPath)
    $lnk.TargetPath = $launcher.Source
    $lnk.Arguments = $launcherArgs + '"' + $clockPath + '"'
    $lnk.WorkingDirectory = $projectRoot
    $lnk.IconLocation = $launcher.Source + ',0'
    $lnk.Description = 'Desktop clock showing a fixed time zone'
    $lnk.Save()
    Write-Output 'Autostart shortcut installed.'
}
