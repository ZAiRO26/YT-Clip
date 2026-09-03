[CmdletBinding()]
param (
    [string]$Title = "Select Video File",
    [string]$Filter = "Video Files (*.mp4;*.mkv;*.mov;*.webm;*.avi;*.flv;*.ts;*.m4v)|*.mp4;*.mkv;*.mov;*.webm;*.avi;*.flv;*.ts;*.m4v|All Files (*.*)|*.*",
    [string]$InitialDirectory = ""
)

Add-Type -AssemblyName System.Windows.Forms

$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = $Title
$dialog.Filter = $Filter
if ($InitialDirectory -and (Test-Path $InitialDirectory)) {
    $dialog.InitialDirectory = $InitialDirectory
}
$dialog.CheckFileExists = $true
$dialog.CheckPathExists = $true

# Create an invisible top-most form to force the dialog in front of all application windows
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
    Write-Output "SELECTED:$($dialog.FileName)"
} else {
    Write-Output "CANCELLED"
}
