param(
    [ValidatePattern('^(arm64-v8a|armeabi-v7a|x86_64)(,(arm64-v8a|armeabi-v7a|x86_64))*$')]
    [string]$Architectures = 'arm64-v8a,armeabi-v7a,x86_64',
    [switch]$CleanNative
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'android_native_command.ps1')
$repo = Split-Path -Parent $PSScriptRoot
$physicalRepo = (Resolve-Path -LiteralPath $repo).Path.TrimEnd('\')
# Android NDK tools require a path without spaces. Use Windows' existing short alias.
Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
using System.Text;
public static class AndroidBuildPath {
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    public static extern uint GetShortPathName(string path, StringBuilder buffer, uint size);
}
'@
$buffer = New-Object System.Text.StringBuilder 32768
if ([AndroidBuildPath]::GetShortPathName($repo, $buffer, 32768) -gt 0) {
    $repo = $buffer.ToString()
}
$mobile = Join-Path $repo 'frontend\mobile'
$localTools = Join-Path $repo '.cache\android'
if (!$env:JAVA_HOME) {
    $localJdk = Get-ChildItem -LiteralPath (Join-Path $localTools 'jdk') -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'bin\javac.exe') } |
        Select-Object -First 1
    if ($localJdk) { $env:JAVA_HOME = $localJdk.FullName }
}
if (!$env:ANDROID_HOME) { $env:ANDROID_HOME = $env:ANDROID_SDK_ROOT }
if (!$env:ANDROID_HOME) { $env:ANDROID_HOME = Join-Path $localTools 'sdk' }
if (!(Test-Path -LiteralPath (Join-Path "$env:JAVA_HOME" 'bin\javac.exe'))) {
    throw 'JDK 17+ is required. Set JAVA_HOME to its folder.'
}
if (!(Test-Path -LiteralPath (Join-Path $env:ANDROID_HOME 'platform-tools\adb.exe'))) {
    throw 'Android SDK is required. Set ANDROID_HOME to its folder.'
}
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:ANDROID_USER_HOME = Join-Path $localTools 'user'
$gradleCache = Join-Path $localTools 'gradle'
New-Item -ItemType Directory -Force -Path $gradleCache | Out-Null
$cacheDrive = $null
# Ninja's Windows path limit is lower than the React Native prefab header paths.
# Map only this workspace cache, then remove the alias after the build.
foreach ($letter in @('Z', 'Y', 'X', 'W', 'V')) {
    if (!(Get-PSDrive -Name $letter -ErrorAction SilentlyContinue)) {
        $cacheDrive = $letter + ':'
        Invoke-AndroidNative -FilePath 'subst.exe' -ArgumentList @($cacheDrive, $gradleCache)
        break
    }
}
if (!$cacheDrive) { throw 'A free drive letter V-Z is needed for the temporary Gradle cache alias' }
$previousGradleHome = $env:GRADLE_USER_HOME
$env:GRADLE_USER_HOME = $cacheDrive + '\'
Write-Output "Gradle cache alias: $cacheDrive"
$physicalSdk = (Resolve-Path -LiteralPath $env:ANDROID_HOME).Path
$sdkDrive = $null
# A space in the NDK path makes CMake shorten clang++.exe to CLANG_~1.EXE;
# Clang then links as a C driver and omits the C++ standard library.
foreach ($letter in @('Z', 'Y', 'X', 'W', 'V')) {
    if (!(Get-PSDrive -Name $letter -ErrorAction SilentlyContinue)) {
        $sdkDrive = $letter + ':'
        Invoke-AndroidNative -FilePath 'subst.exe' -ArgumentList @($sdkDrive, $physicalSdk)
        break
    }
}
if (!$sdkDrive) {
    & subst.exe $cacheDrive /d | Out-Null
    throw 'A second free drive letter V-Z is needed for the Android SDK alias'
}
$env:ANDROID_HOME = $sdkDrive + '\'
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
Write-Output "Android SDK alias: $sdkDrive"
$env:PATH = (Join-Path $env:JAVA_HOME 'bin') + ';' + $env:PATH
$previousCi = $env:CI
$previousTelemetry = $env:EXPO_NO_TELEMETRY
$env:CI = '1'
$env:EXPO_NO_TELEMETRY = '1'
Push-Location $mobile
try {
    $driveStamp = Join-Path $localTools 'gradle-drive.txt'
    $lastDrive = if (Test-Path -LiteralPath $driveStamp) { (Get-Content -LiteralPath $driveStamp -Raw).Trim() } else { '' }
    if ($CleanNative -or $lastDrive -ne ($cacheDrive + '|' + $sdkDrive)) {
        # CMake embeds absolute prefab paths; regenerate only known generated directories.
        foreach ($relativeDir in @('node_modules\expo-modules-core\android\.cxx',
                'frontend\mobile\android\app\.cxx',
                'node_modules\react-native-safe-area-context\android\.cxx',
                'node_modules\react-native-svg\android\.cxx')) {
            $target = Join-Path $physicalRepo $relativeDir
            if (Test-Path -LiteralPath $target) {
                $resolved = (Resolve-Path -LiteralPath $target).Path
                if (!$resolved.StartsWith($physicalRepo + '\', [System.StringComparison]::OrdinalIgnoreCase) -or
                        (Split-Path -Leaf $resolved) -ne '.cxx') {
                    throw "Unsafe generated cache path: $resolved"
                }
                Remove-Item -LiteralPath $resolved -Recurse -Force
            }
        }
        Set-Content -LiteralPath $driveStamp -Value ($cacheDrive + '|' + $sdkDrive) -Encoding Ascii
    }
    Invoke-AndroidNative -FilePath 'node' -ArgumentList @((Join-Path $repo 'node_modules\expo\bin\cli'), 'prebuild', '--platform', 'android', '--no-install')
    $sdkProperty = $env:ANDROID_HOME.Replace('\', '\\').Replace(':', '\:')
    Set-Content -LiteralPath 'android\local.properties' -Value ("sdk.dir=" + $sdkProperty) -Encoding Ascii
    [xml]$manifest = Get-Content -LiteralPath 'android\app\src\main\AndroidManifest.xml' -Raw
    $androidNamespace = 'http://schemas.android.com/apk/res/android'
    if ($manifest.manifest.application.GetAttribute('usesCleartextTraffic', $androidNamespace) -ne 'true') {
        throw 'Generated Android manifest does not enable the LAN HTTP API'
    }
    Push-Location 'android'
    try {
        Invoke-AndroidNative -FilePath '.\gradlew.bat' -ArgumentList @('--gradle-user-home', $env:GRADLE_USER_HOME, ':app:assembleRelease', "-PreactNativeArchitectures=$Architectures", '--no-daemon', '--max-workers=2', '--console=plain')
    } finally { Pop-Location }
    $destination = Join-Path $repo 'dist\android'
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    $apk = Join-Path $destination 'DriverMonitor.apk'
    Copy-Item -LiteralPath 'android\app\build\outputs\apk\release\app-release.apk' -Destination $apk -Force
    $metadata = [ordered]@{
        artifact = 'DriverMonitor.apk'
        package = 'com.da2.drivermonitor'
        architectures = $Architectures.Split(',')
        sha256 = (Get-FileHash -LiteralPath $apk -Algorithm SHA256).Hash.ToLowerInvariant()
        bytes = (Get-Item -LiteralPath $apk).Length
        signing = 'Expo template debug key; internal testing only'
    }
    $metadata | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $destination 'build.json') -Encoding UTF8
    Write-Output "APK: $apk"
    Write-Output "SHA256: $($metadata.sha256)"
} finally {
    Pop-Location
    $env:CI = $previousCi
    $env:EXPO_NO_TELEMETRY = $previousTelemetry
    $env:GRADLE_USER_HOME = $previousGradleHome
    & subst.exe $cacheDrive /d | Out-Null
    & subst.exe $sdkDrive /d | Out-Null
    $env:ANDROID_HOME = $physicalSdk
    $env:ANDROID_SDK_ROOT = $physicalSdk
}
