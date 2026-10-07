param(
    [string]$ReportPath = 'reports/BAO_CAO_GIAM_SAT_BUON_NGU_THEO_MAU.docx',
    [string]$PdfPath = 'reports/reference_style/report_render.pdf'
)
$ErrorActionPreference = 'Stop'
$reportResolved = (Resolve-Path -LiteralPath $ReportPath).Path
$reportPdf = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $PdfPath))
$wordReportApp = $null
$wordReportDocument = $null
try {
    $wordReportApp = New-Object -ComObject Word.Application
    $wordReportApp.Visible = $false
    $wordReportApp.DisplayAlerts = 0
    $wordReportApp.Options.UpdateLinksAtOpen = $false
    $wordReportDocument = $wordReportApp.Documents.Open($reportResolved, $false, $false)
    $wordReportDocument.UpdateStylesOnOpen = $false
    $wordReportDocument.Fields.Update() | Out-Null
    foreach ($reportToc in $wordReportDocument.TablesOfContents) {
        $reportToc.Update()
        $reportToc.Range.Font.Name = 'Times New Roman'
        $reportToc.Range.Font.Size = 12
        $reportToc.Range.ParagraphFormat.LineSpacingRule = 0
        $reportToc.Range.ParagraphFormat.SpaceAfter = 2
    }
    $wordReportDocument.Repaginate()
    $wordReportDocument.Fields.Update() | Out-Null
    $wordReportDocument.Save()
    $wordReportDocument.ExportAsFixedFormat($reportPdf, 17)
    Write-Output ('Pages: ' + $wordReportDocument.ComputeStatistics(2))
    Write-Output ('QA PDF: ' + $reportPdf)
} finally {
    if ($null -ne $wordReportDocument) {
        $wordReportDocument.Close(0)
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wordReportDocument)
    }
    if ($null -ne $wordReportApp) {
        $wordReportApp.Quit()
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wordReportApp)
    }
}
