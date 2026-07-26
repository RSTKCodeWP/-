# Check available Python versions
Write-Host "=== Searching for Python installations ===" -ForegroundColor Green

# Check common installation paths
$pythonPaths = @(
    "C:\Python*",
    "C:\Program Files\Python*",
    "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python*"
)

$found = @()

foreach ($path in $pythonPaths) {
    $dirs = Get-ChildItem -Path $path -Directory -ErrorAction SilentlyContinue
    foreach ($dir in $dirs) {
        $pythonExe = Join-Path $dir.FullName "python.exe"
        if (Test-Path $pythonExe) {
            $version = & $pythonExe --version 2>&1
            $found += [PSCustomObject]@{
                Path = $pythonExe
                Version = $version
            }
        }
    }
}

# Check py launcher
Write-Host "`n=== Checking py launcher ===" -ForegroundColor Green
try {
    $pyVersions = py -0 2>&1 | Out-String
    Write-Host $pyVersions
} catch {
    Write-Host "py launcher not available" -ForegroundColor Yellow
}

# Display found Python installations
Write-Host "`n=== Found Python installations ===" -ForegroundColor Green
if ($found.Count -gt 0) {
    $found | Format-Table -AutoSize
} else {
    Write-Host "No Python installations found in common paths" -ForegroundColor Yellow
}

# Check current Poetry environment
Write-Host "`n=== Current Poetry environment ===" -ForegroundColor Green
poetry env info
