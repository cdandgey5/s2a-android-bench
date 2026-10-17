<#
  The ONE elevated step of the plan (docs/DAY-0.md §5, specs/environments.md §5).
  Started by `abb sandbox setup` through a UAC prompt; never run it by hand unless that command
  tells you to. Reads its parameters from a JSON file (no secrets in it); the sandbox user's
  password is read from Windows Credential Manager (service "abb") through the harness venv's
  keyring module and never appears on any command line.

  Steps: create/refresh the local user (ADSI: password never expires, cannot be changed, member of
  Users only), reset ACL inheritance at ABB_HOME and the code checkout, apply the static denies and
  read+execute grants from config/sandbox.yaml, deny writes to C:\Users\<user>, add the outbound
  firewall block rule applied to that principal, enable long paths. Writes a JSON result file.
#>
param([Parameter(Mandatory = $true)][string]$ParamsFile)
$ErrorActionPreference = 'Stop'
$P = Get-Content -Raw -LiteralPath $ParamsFile | ConvertFrom-Json
$steps = [ordered]@{}
function Step([string]$name, [scriptblock]$body) {
    try { & $body; $steps[$name] = 'ok' } catch { $steps[$name] = "FAILED: $($_.Exception.Message)" }
}
function Icacls([string[]]$a) {
    $out = & "$env:SystemRoot\System32\icacls.exe" @a 2>&1
    if ($LASTEXITCODE -ne 0) { throw "icacls $($a -join ' ') -> $LASTEXITCODE $out" }
}

$user = $P.user
$pw = & $P.venv_python -I -c "import keyring,sys; sys.stdout.write(keyring.get_password('abb', '$user') or '')"
if (-not $pw) { throw "no password for $user in Credential Manager; run 'abb sandbox setup' (non-elevated) again" }

Step 'user' {
    $computer = [ADSI]"WinNT://$env:COMPUTERNAME,computer"
    $existing = $null
    try { $existing = [ADSI]"WinNT://$env:COMPUTERNAME/$user,user"; $null = $existing.Name } catch { $existing = $null }
    if ($existing -and $existing.Path) {
        $existing.SetPassword($pw)
        $u = $existing
    } else {
        $u = $computer.Create('User', $user)
        $u.SetPassword($pw)
        $u.SetInfo()
        $u.Put('Description', 'abb benchmark sandbox user (no network; reads ABB_HOME\tools only)')
    }
    # ADS_UF_DONT_EXPIRE_PASSWD | ADS_UF_PASSWD_CANT_CHANGE | ADS_UF_NORMAL_ACCOUNT
    $u.Put('UserFlags', 0x10000 -bor 0x40 -bor 0x200)
    $u.SetInfo()
    # BUILTIN\Users resolved from its SID, so a localized group name works too
    $usersName = (New-Object Security.Principal.SecurityIdentifier('S-1-5-32-545')).Translate([Security.Principal.NTAccount]).Value.Split('\')[-1]
    $users = [ADSI]"WinNT://$env:COMPUTERNAME/$usersName,group"
    $isMember = @($users.Invoke('Members') | ForEach-Object { $_.GetType().InvokeMember('Name', 'GetProperty', $null, $_, $null) }) -contains $user
    if (-not $isMember) { $users.Add("WinNT://$env:COMPUTERNAME/$user,user") }
}
Remove-Variable pw
$sid = (New-Object Security.Principal.NTAccount("$env:COMPUTERNAME\$user")).Translate([Security.Principal.SecurityIdentifier]).Value

Step 'inheritance' {
    foreach ($root in $P.reset_inheritance) {
        Icacls @($root, '/inheritance:r', '/grant:r', "$($P.harness_user):(OI)(CI)F", '/grant:r', '*S-1-5-18:(OI)(CI)F', '/grant:r', '*S-1-5-32-544:(OI)(CI)F')
    }
}
Step 'deny' {
    foreach ($d in $P.deny) {
        if (Test-Path -LiteralPath $d -PathType Container) { Icacls @($d, '/deny', "*${sid}:(OI)(CI)F") }
        elseif (Test-Path -LiteralPath $d) { Icacls @($d, '/deny', "*${sid}:F") }
    }
}
Step 'rx' {
    foreach ($d in $P.rx) {
        if (Test-Path -LiteralPath $d -PathType Container) { Icacls @($d, '/grant:r', "*${sid}:(OI)(CI)RX") }
        elseif (Test-Path -LiteralPath $d) { Icacls @($d, '/grant:r', "*${sid}:RX") }
    }
}
Step 'profile_deny_write' {
    foreach ($d in $P.deny_write_dirs) {
        if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
        Icacls @($d, '/deny', "*${sid}:(OI)(CI)(W,WA,WD,AD,DC)")
    }
}
Step 'firewall' {
    Get-NetFirewallRule -DisplayName $P.firewall_rule -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    New-NetFirewallRule -DisplayName $P.firewall_rule -Direction Outbound -Action Block -Profile Any `
        -LocalUser "O:LSD:(A;;CC;;;$sid)" -Description 'abb: block all outbound traffic of the sandbox user (loopback stays open for the proxy)' | Out-Null
}
Step 'long_paths' {
    Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -Value 1 -Type DWord
}

$result = [ordered]@{ finished_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'); user = $user; sid = $sid; steps = $steps }
$result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $P.result_path -Encoding utf8
if ($steps.Values | Where-Object { $_ -ne 'ok' }) { exit 1 } else { exit 0 }
