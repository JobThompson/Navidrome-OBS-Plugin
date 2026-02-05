Param(
  [switch]$Clean,
  [switch]$NoVenv,
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$VenvDir = Join-Path $ProjectRoot ".venv-build"
$SpecFile = Join-Path $ProjectRoot "navidrome_obs_overlay.spec"

function Invoke-Step([string]$Message, [scriptblock]$Block) {
  Write-Host "`n==> $Message"
  & $Block
}

if ($Clean) {
  Invoke-Step "Cleaning build outputs" {
    Remove-Item -Force -Recurse -ErrorAction SilentlyContinue (Join-Path $ProjectRoot "build")
    Remove-Item -Force -Recurse -ErrorAction SilentlyContinue (Join-Path $ProjectRoot "dist")
    Remove-Item -Force -Recurse -ErrorAction SilentlyContinue (Join-Path $ProjectRoot "__pycache__")
  }
}

if (-not (Test-Path $SpecFile)) {
  throw "Missing spec file: $SpecFile"
}

$Py = $Python
$Pip = $Python

if (-not $NoVenv) {
  if (-not (Test-Path $VenvDir)) {
    Invoke-Step "Creating build venv (.venv-build)" {
      & $Python -m venv $VenvDir
    }
  }

  $Py = Join-Path $VenvDir "Scripts\python.exe"
  $Pip = $Py
}

Invoke-Step "Upgrading pip" {
  & $Py -m pip install --upgrade pip
}

Invoke-Step "Installing runtime deps" {
  & $Py -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
}

Invoke-Step "Installing PyInstaller" {
  & $Py -m pip install pyinstaller
}

Invoke-Step "Building one-file exe" {
  & $Py -m PyInstaller --noconfirm --clean $SpecFile
}

$ExePath = Join-Path $ProjectRoot "dist\NavidromeOverlay.exe"
if (Test-Path $ExePath) {
  Write-Host "`nBuilt: $ExePath"
  Write-Host "Tip: Put your .env next to the exe (same folder)."
} else {
  Write-Warning "Build finished but exe not found at $ExePath"
}
