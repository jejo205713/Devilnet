<#
PowerShell installer for Devilnet (Windows)
- Creates a virtual environment
- Installs dependencies from requirements.txt
- Runs initial training
- Prints command to start Devilnet
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot = Resolve-Path "$RepoRoot\.."
$RepoRoot = $RepoRoot.Path
$VenvDir = Join-Path $RepoRoot ".venv"
$ReqFile = Join-Path $RepoRoot "requirements.txt"
$TrainLog = Join-Path $RepoRoot "devilnet_train.log"

function Err([string]$msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }
function Info([string]$msg){ Write-Host "[INFO] $msg" -ForegroundColor Cyan }

# Add: robust OS detection without relying on $IsWindows / $PSVersionTable.OS
function Get-OSName {
	try {
		# Prefer RuntimeInformation (works across PowerShell versions)
		$ri = [System.Runtime.InteropServices.RuntimeInformation]
		if ($ri::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) { return 'Windows' }
		if ($ri::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Linux))   { return 'Linux' }
		if ($ri::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::OSX))     { return 'macOS' }
	} catch {
		# ignore and fall back
	}
	# Fallbacks
	if ($env:OS) { return $env:OS }
	try {
		$ver = [System.Environment]::OSVersion
		return ("{0} {1}" -f $ver.Platform, $ver.Version)
	} catch {
		return 'Unknown'
	}
}

try {
	Info "Starting Devilnet installer (PowerShell)..."

	# Check python
	$python = Get-Command python -ErrorAction SilentlyContinue
	if(-not $python){ Err "Python not found in PATH. Install Python 3.8+ and retry."; exit 2 }

	# Create venv
	if(-not (Test-Path $VenvDir)){
		Info "Creating virtual environment at $VenvDir"
		& python -m venv $VenvDir
	} else { Info "Virtualenv already exists at $VenvDir" }

	# Activate venv for this script
	$Activate = Join-Path $VenvDir 'Scripts\Activate.ps1'
	if(Test-Path $Activate){
		. $Activate
	} else { Err "Activate script not found: $Activate"; exit 3 }

	# Upgrade pip
	Info "Upgrading pip"
	python -m pip install --upgrade pip setuptools wheel | Out-Null

	# Check requirements file
	if(-not (Test-Path $ReqFile)){
		Err "Requirements file not found at $ReqFile"; exit 4
	}

	# Install requirements
	Info "Installing Python dependencies from $ReqFile"
	python -m pip install -r $ReqFile

	# Use helper for branching
	$osName = Get-OSName
	Info "Detected OS: $osName"
	if ($osName -like 'Windows*') {
		# Windows-specific actions
		try{ python -m pip install windows-curses } catch { }
	} elseif ($osName -like 'Linux*' -or $osName -like 'Ubuntu*') {
		# Linux-specific actions
		# ...existing code...
	} elseif ($osName -like 'macOS*') {
		# macOS-specific actions
		# ...existing code...
	} else {
		Info "Unrecognized OS '$osName' - proceeding with generic steps"
	}

	# Run training
	Info "Running initial model training (will log to $TrainLog)"
	& python -m devilnet --train *> $TrainLog 2>&1
	if($LASTEXITCODE -ne 0){ Err "Training failed (exit $LASTEXITCODE). Check $TrainLog"; exit 5 }

	Info "Training completed successfully. Log: $TrainLog"
	Write-Host "To start the interactive UI run:" -ForegroundColor Green
	Write-Host "  python -m devilnet --ui" -ForegroundColor Yellow
	Write-Host "To run headless monitoring:" -ForegroundColor Green
	Write-Host "  python -m devilnet --monitor" -ForegroundColor Yellow

	Write-Host "[INFO] Installer finished successfully." -ForegroundColor Green
} catch {
	Write-Host "[ERROR] Installer encountered an error: $($_.Exception.Message)" -ForegroundColor Red
	exit 1
} finally{
    try{ deactivate } catch { }
}
