param(
    [switch]$Apply,
    [switch]$GeneratedOnly
)

$ErrorActionPreference = 'Stop'
$cleanupRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
$cleanupRootPrefix = $cleanupRoot + '\'
$cleanupAuditPath = Join-Path $cleanupRoot 'reports\project_cleanup.json'

function Get-CleanupHash([string]$Path) {
    # Read-only sharing also permits documents already opened by Word.
    $cleanupHashStream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    $cleanupHasher = [System.Security.Cryptography.SHA256]::Create()
    try { return ([System.BitConverter]::ToString($cleanupHasher.ComputeHash($cleanupHashStream))).Replace('-', '').ToLowerInvariant() }
    finally { $cleanupHashStream.Dispose(); $cleanupHasher.Dispose() }
}

function Assert-CleanupPath([string]$RelativePath, [switch]$AllowLeafLink) {
    $cleanupAbsolute = [System.IO.Path]::GetFullPath((Join-Path $cleanupRoot $RelativePath))
    if (-not $cleanupAbsolute.StartsWith($cleanupRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Cleanup path outside workspace: $cleanupAbsolute"
    }
    # Reject links in every existing ancestor rather than following them.
    $cleanupAncestor = $cleanupAbsolute
    while ($cleanupAncestor -ne $cleanupRoot) {
        if (Test-Path -LiteralPath $cleanupAncestor) {
            $cleanupItem = Get-Item -LiteralPath $cleanupAncestor -Force
            if (($cleanupItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -and -not ($AllowLeafLink -and $cleanupAncestor -eq $cleanupAbsolute -and -not $cleanupItem.PSIsContainer)) {
                throw "Cleanup path crosses a link: $cleanupAncestor"
            }
        }
        $cleanupAncestor = Split-Path -Parent $cleanupAncestor
    }
    return $cleanupAbsolute
}

$cleanupDefinitions = @()
if (-not $GeneratedOnly) {
    $cleanupDefinitions += @(
        @{path='DA2'; reason='Empty KiCad PCB and schematic; no components or nets; no project references'},
        @{path='test_yolo_face_detector'; reason='Inactive face-detector experiment; production uses YuNet and root classifier notebooks'},
        @{path='camera_classical\.venv'; reason='Old nested PC environment; active PC environment is the root .venv'},
        @{path='radxa_rock4d\python_runtime\models'; reason='Exact duplicate original checkpoints; shared runtime uses manifests'},
        @{path='radxa_rock4d\config'; reason='Unused classes.txt with reversed eye labels; runtime and conversion use the authoritative manifests'},
        @{path='models\eye_refined_v2'; reason='Unselected exported candidate; training reads feature caches and the v1 initializer, not these artifacts'},
        @{path='models\eye_refined_v3'; reason='Incomplete unsuccessful candidate containing only validation output'},
        @{path='.cache\uv-rknn\cache'; reason='Downloaded package cache; Linux SDK environment uses copied installed packages (UV_LINK_MODE=copy)'},
        @{path='.cache\uv-rknn\uv-x86_64-unknown-linux-gnu.tar.gz'; reason='Installer archive already extracted; the uv executable is retained'},
        @{path='.cache\uv-rknn\uv-x86_64-unknown-linux-gnu.tar.gz.sha256'; reason='Checksum sidecar for the removed extracted installer archive'},
        @{path='dist'; reason='Stale generated deployment ZIPs; rebuild from the selected model and current code'},
        @{path='reports\bundle_verification_onnx.json'; reason='Verification of the removed old ONNX ZIP'},
        @{path='reports\bundle_verification_rknn.json'; reason='Verification of the removed old RKNN ZIP'},
        @{path='kaggle_output\yolov10'; reason='Unused vendored YOLOv10 detector repository; both Python environments use installed packages'},
        @{path='kaggle_output\runs'; reason='Old YOLOv10 detection train/test results and weights, not the classifiers used by the current system'},
        @{path='kaggle_output\onnx_exports'; reason='Unused old YOLOv10 detector ONNX exports'},
        @{path='kaggle_output\yolov10n.pt'; reason='Unused detector initialization checkpoint; current notebooks use yolov8n-cls.pt'},
        @{path='kaggle_output\yolov8n.pt'; reason='Unused detection checkpoint; distinct from yolov8n-cls.pt'},
        @{path='kaggle_output\notebook2c9c1dd14e.log'; reason='Empty old notebook log'}
    )
    foreach ($cleanupOldQa in @('algorithm_theory_qa','architecture_qa','no_voice_qa','qa_pages','render_final','render_v2')) {
        $cleanupDefinitions += @{path="reports\reference_style\$cleanupOldQa"; reason='Superseded intermediate report render; current QA is system_design_scope'}
    }
    foreach ($cleanupOldRender in Get-ChildItem -LiteralPath (Join-Path $cleanupRoot 'reports\reference_style') -File -Force) {
        if ($cleanupOldRender.Name -match '^(page_\d+\.png|final_adjusted_\d+\.png|report_.+\.pdf|build_checks\.json|final_checks\.json|pdf_checks\.json|artifact\.md)$') {
            $cleanupDefinitions += @{path=$cleanupOldRender.FullName.Substring($cleanupRootPrefix.Length); reason='Superseded report render/check output; current PDF and QA retained'}
        }
    }
}

$cleanupDefinitions += @{path='reports\firmware_test.exe'; reason='Generated host firmware test executable; rebuilt by verify_release.py'}
$cleanupDefinitions += @{path='__pycache__'; reason='Regenerable Python bytecode'}
foreach ($cleanupCodeDir in @('driver_monitor','tools','tests','camera_classical','radxa_rock4d')) {
    foreach ($cleanupBytecode in Get-ChildItem -LiteralPath (Join-Path $cleanupRoot $cleanupCodeDir) -Directory -Filter '__pycache__' -Recurse -Force) {
        # The old environment is already a single removal target in phase one.
        if ($cleanupBytecode.FullName -notlike '*\camera_classical\.venv\*') {
            $cleanupDefinitions += @{path=$cleanupBytecode.FullName.Substring($cleanupRootPrefix.Length); reason='Regenerable Python bytecode'}
        }
    }
}

# Protect source, active/reference models, data, videos, and current deliverables.
$cleanupProtected = @{}
$cleanupProtectedFiles = @()
foreach ($cleanupKeptDir in @('driver_monitor','configs','scripts','esp32_buzzer','data_reviews','tests\fixtures','report_assets','models\eye_refined','models\eye_refined_v4','models\smile_refined','models\yawn_camera_refined')) {
    $cleanupProtectedFiles += Get-ChildItem -LiteralPath (Join-Path $cleanupRoot $cleanupKeptDir) -File -Recurse -Force | Where-Object { $_.Extension -notin @('.pyc','.pyo') }
}
$cleanupProtectedFiles += Get-ChildItem -LiteralPath (Join-Path $cleanupRoot 'models') -File -Force
$cleanupProtectedFiles += Get-ChildItem -LiteralPath (Join-Path $cleanupRoot 'reports') -File -Force | Where-Object { $_.Extension -in @('.avi','.docx','.pdf') -and $_.Name -notlike '~$*' }
$cleanupProtectedFiles += Get-ChildItem -LiteralPath (Join-Path $cleanupRoot 'reports\yawn_camera_check') -File -Force | Where-Object { $_.Extension -eq '.avi' -or $_.Name -like '*.timestamps.json' }
foreach ($cleanupKeptFile in @('camera_classical\best_eye.pt','camera_classical\best_yawn.pt','train_eye_classifier.ipynb','train_yawn_classifier.ipynb','requirements-host.lock.txt','requirements-runtime.txt','requirements-rknn-linux.lock.txt','.venv\pyvenv.cfg','.venv\Scripts\python.exe','.venv-rknn\pyvenv.cfg','BAO_CAO_DA2_HE_THONG_GIAM_SAT_TAI_XE.docx','reports\BAO_CAO_GIAM_SAT_BUON_NGU_HOAN_THIEN.md','reports\reference_style\system_design_scope\scope_audit.json')) {
    $cleanupProtectedFiles += Get-Item -LiteralPath (Join-Path $cleanupRoot $cleanupKeptFile) -Force
}
foreach ($cleanupProtectedFile in $cleanupProtectedFiles) {
    $cleanupProtected[$cleanupProtectedFile.FullName] = Get-CleanupHash $cleanupProtectedFile.FullName
}

$cleanupDataBefore = @{}
foreach ($cleanupDataDir in @('kaggle_output\data','data_collection','.cache\cew','.cache\genki','.cache\smiles','.cache\eye_refinement','.cache\eye_refinement_v2','.cache\eye_refinement_v4','.cache\yawn_refinement','.cache\yawn_camera_refinement')) {
    $cleanupDataFiles = @(Get-ChildItem -LiteralPath (Join-Path $cleanupRoot $cleanupDataDir) -File -Recurse -Force)
    $cleanupDataBefore[$cleanupDataDir] = @{files=$cleanupDataFiles.Count; bytes=[long](($cleanupDataFiles | Measure-Object -Property Length -Sum).Sum)}
}

if (-not $GeneratedOnly) {
    foreach ($cleanupDuplicateName in @('best_eye.pt','best_yawn.pt')) {
        $cleanupOriginal = Join-Path $cleanupRoot "camera_classical\$cleanupDuplicateName"
        $cleanupDuplicate = Join-Path $cleanupRoot "radxa_rock4d\python_runtime\models\$cleanupDuplicateName"
        if ((Test-Path -LiteralPath $cleanupDuplicate) -and ((Get-CleanupHash $cleanupOriginal) -ne (Get-CleanupHash $cleanupDuplicate))) {
            throw "Duplicate model differs from original: $cleanupDuplicate"
        }
    }
}

$cleanupEntries = @()
foreach ($cleanupDefinition in $cleanupDefinitions) {
    $cleanupTarget = Assert-CleanupPath $cleanupDefinition.path
    if (-not (Test-Path -LiteralPath $cleanupTarget)) { continue }
    foreach ($cleanupProtectedPath in $cleanupProtected.Keys) {
        if ($cleanupProtectedPath -eq $cleanupTarget -or $cleanupProtectedPath.StartsWith($cleanupTarget + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Removal would include a protected file: $cleanupProtectedPath"
        }
    }
    $cleanupChildren = @(Get-ChildItem -LiteralPath $cleanupTarget -Recurse -Force)
    $cleanupLeafLinks = @($cleanupChildren | Where-Object { ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 })
    if ($cleanupLeafLinks.Count -gt 0) {
        # uv's WSL cache has file reparse entries indexing its archive store.
        # Unlink these leaves first, without recursing or following targets.
        if ($cleanupDefinition.path -ne '.cache\uv-rknn\cache' -or ($cleanupLeafLinks | Where-Object { $_.PSIsContainer })) {
            throw "Removal target contains an unsupported link: $cleanupTarget"
        }
    }
    $cleanupTargetItem = Get-Item -LiteralPath $cleanupTarget -Force
    $cleanupTargetFiles = if ($cleanupTargetItem.PSIsContainer) { @($cleanupChildren | Where-Object { -not $_.PSIsContainer }) } else { @($cleanupTargetItem) }
    $cleanupEntries += [pscustomobject]@{
        path=$cleanupDefinition.path.Replace('\','/'); absolute_path=$cleanupTarget;
        reason=$cleanupDefinition.reason; files=$cleanupTargetFiles.Count;
        bytes=[long](($cleanupTargetFiles | Measure-Object -Property Length -Sum).Sum);
        leaf_links=@($cleanupLeafLinks | ForEach-Object { $_.FullName.Substring($cleanupRootPrefix.Length) }); removed=$false
    }
}

if (-not $Apply) {
    $cleanupEntries | Select-Object path,files,bytes,reason | ConvertTo-Json -Depth 4
    exit 0
}

foreach ($cleanupEntry in $cleanupEntries) {
    # Recheck the final resolved absolute path immediately before each removal.
    $cleanupFinalPath = Assert-CleanupPath $cleanupEntry.path
    if ($cleanupFinalPath -ne $cleanupEntry.absolute_path) { throw 'Cleanup path changed' }
    foreach ($cleanupLeafLink in $cleanupEntry.leaf_links) {
        $cleanupLinkPath = Assert-CleanupPath -RelativePath $cleanupLeafLink -AllowLeafLink
        if (-not $cleanupLinkPath.StartsWith($cleanupFinalPath + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Link outside removal target' }
        Remove-Item -LiteralPath $cleanupLinkPath -Force
    }
    if (Get-ChildItem -LiteralPath $cleanupFinalPath -Recurse -Force | Where-Object { ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 }) { throw 'Link remains before recursive deletion' }
    Remove-Item -LiteralPath $cleanupFinalPath -Recurse -Force
    if (Test-Path -LiteralPath $cleanupFinalPath) { throw "Removal incomplete: $cleanupFinalPath" }
    $cleanupEntry.removed = $true
    Write-Output "Removed: $($cleanupEntry.path)"
}

foreach ($cleanupProtectedPath in $cleanupProtected.Keys) {
    if (-not (Test-Path -LiteralPath $cleanupProtectedPath) -or (Get-CleanupHash $cleanupProtectedPath) -ne $cleanupProtected[$cleanupProtectedPath]) {
        throw "Protected file changed: $cleanupProtectedPath"
    }
}
foreach ($cleanupDataDir in $cleanupDataBefore.Keys) {
    $cleanupDataFiles = @(Get-ChildItem -LiteralPath (Join-Path $cleanupRoot $cleanupDataDir) -File -Recurse -Force)
    $cleanupDataBytes = [long](($cleanupDataFiles | Measure-Object -Property Length -Sum).Sum)
    if ($cleanupDataFiles.Count -ne $cleanupDataBefore[$cleanupDataDir].files -or $cleanupDataBytes -ne $cleanupDataBefore[$cleanupDataDir].bytes) {
        throw "Retained dataset changed: $cleanupDataDir"
    }
}
$cleanupPhases = @()
if (Test-Path -LiteralPath $cleanupAuditPath) {
    $cleanupExistingAudit = Get-Content -LiteralPath $cleanupAuditPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $cleanupPhases += @($cleanupExistingAudit.phases)
}
$cleanupPhases += [pscustomobject]@{
    utc=[DateTime]::UtcNow.ToString('o'); generated_only=[bool]$GeneratedOnly; entries=$cleanupEntries;
    protected_file_count=$cleanupProtected.Count; protected_sha256=$cleanupProtected;
    protected_files_unchanged=$true; retained_dataset_inventory=$cleanupDataBefore; retained_datasets_unchanged=$true
}
$cleanupAllEntries = @($cleanupPhases | ForEach-Object { $_.entries })
$cleanupAudit = [pscustomobject]@{
    workspace=$cleanupRoot; phases=$cleanupPhases;
    removed_targets=$cleanupAllEntries.Count;
    removed_files=[long](($cleanupAllEntries | Measure-Object -Property files -Sum).Sum);
    removed_bytes=[long](($cleanupAllEntries | Measure-Object -Property bytes -Sum).Sum)
}
$cleanupAudit | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $cleanupAuditPath -Encoding UTF8
Write-Output ("Removed files: " + $cleanupAudit.removed_files)
Write-Output ("Removed GiB: " + [math]::Round($cleanupAudit.removed_bytes / 1GB, 3))
Write-Output ("Audit: " + $cleanupAuditPath)
