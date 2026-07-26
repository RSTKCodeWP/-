# TerraForge Studio - Build Script for Windows
# Скрипт сборки TerraForge Studio для Windows

param(
    [string]$Target = "release",
    [switch]$SkipFrontend = $false
)

$ErrorActionPreference = "Stop"

Write-Host "🌍 TerraForge Studio - Build Script" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Check Node.js
Write-Host "📦 Checking Node.js..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    Write-Host "✅ Node.js version: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Node.js not found. Please install Node.js 18+" -ForegroundColor Red
    exit 1
}

# Check Rust
Write-Host "🦀 Checking Rust..." -ForegroundColor Yellow
try {
    $rustVersion = rustc --version
    Write-Host "✅ Rust version: $rustVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Rust not found. Please install Rust from https://rustup.rs" -ForegroundColor Red
    exit 1
}

# Build Frontend
if (-not $SkipFrontend) {
    Write-Host ""
    Write-Host "🔨 Building Frontend..." -ForegroundColor Yellow
    
    Set-Location frontend-new
    
    Write-Host "Installing dependencies..." -ForegroundColor Gray
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ npm install failed" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Building frontend..." -ForegroundColor Gray
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Frontend build failed" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✅ Frontend built successfully" -ForegroundColor Green
    
    Set-Location ..
} else {
    Write-Host "⏭️  Skipping frontend build" -ForegroundColor Gray
}

# Build Tauri
Write-Host ""
Write-Host "🚀 Building Tauri application..." -ForegroundColor Yellow

Set-Location frontend-new

if ($Target -eq "release") {
    Write-Host "Building RELEASE version..." -ForegroundColor Gray
    npm run tauri build
} else {
    Write-Host "Building DEBUG version..." -ForegroundColor Gray
    npm run tauri build -- --debug
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Tauri build failed" -ForegroundColor Red
    Set-Location ..
    exit 1
}

Set-Location ..

Write-Host ""
Write-Host "✅ Build completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "📦 Output files:" -ForegroundColor Cyan
Write-Host "   MSI Installer: frontend-new\src-tauri\target\release\bundle\msi\" -ForegroundColor White
Write-Host "   NSIS Installer: frontend-new\src-tauri\target\release\bundle\nsis\" -ForegroundColor White
Write-Host ""
