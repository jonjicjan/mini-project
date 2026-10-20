param(
    [Parameter(Mandatory = $true)][string]$InputDocx,
    [Parameter(Mandatory = $true)][string]$OutputPdf
)
$ErrorActionPreference = 'Stop'
$sourcePath = (Resolve-Path -LiteralPath $InputDocx).Path
$pdfPath = [System.IO.Path]::GetFullPath($OutputPdf)
if ([System.IO.Path]::GetExtension($sourcePath) -ne '.docx') {
    throw 'The source must be a DOCX file.'
}
if ([System.IO.Path]::GetExtension($pdfPath) -ne '.pdf') {
    throw 'The output must be a PDF file.'
}
New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($pdfPath)) | Out-Null
$word = $null
$document = $null
try {
    # Own a new automation instance; never attach to the user's active Word instance.
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $word.Documents.Open($sourcePath, $false, $true, $false)
    $document.Repaginate()
    $document.ExportAsFixedFormat($pdfPath, 17)
    [ordered]@{
        renderer = 'Microsoft Word'
        version = $word.Version
        build = $word.Build
        pages = $document.ComputeStatistics(2)
        source = $sourcePath
        pdf = $pdfPath
    } | ConvertTo-Json
}
finally {
    try {
        if ($null -ne $document) {
            $document.Close([ref]0)
            [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) | Out-Null
        }
    }
    finally {
        if ($null -ne $word) {
            $word.Quit([ref]0)
            [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) | Out-Null
        }
    }
}
