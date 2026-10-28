function Invoke-AndroidNative {
    param([string]$FilePath, [string[]]$ArgumentList)
    Get-Command -Name $FilePath -ErrorAction Stop | Out-Null
    $previousPreference = $ErrorActionPreference
    try {
        # Windows PowerShell turns redirected native stderr into ErrorRecord objects.
        # Preserve warnings as plain log lines and decide failure from the process exit code.
        $ErrorActionPreference = 'Continue'
        & $FilePath @ArgumentList 2>&1 | ForEach-Object { $_.ToString() }
        $commandCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($commandCode -ne 0) { throw "$FilePath exited with code $commandCode" }
}
