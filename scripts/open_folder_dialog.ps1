[CmdletBinding()]
param (
    [string]$Description = "Select Destination Folder",
    [string]$SelectedPath = ""
)

Add-Type -AssemblyName System.Windows.Forms

$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = $Description
$dialog.ShowNewFolderButton = $true
if ($SelectedPath -and (Test-Path $SelectedPath)) {
    $dialog.SelectedPath = $SelectedPath
}

$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.Width = 1
$owner.Height = 1
$owner.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$owner.Show()
$owner.BringToFront()
$owner.Activate()

$result = $dialog.ShowDialog($owner)
$owner.Close()
$owner.Dispose()

if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output "SELECTED:$($dialog.SelectedPath)"
} else {
    Write-Output "CANCELLED"
}
