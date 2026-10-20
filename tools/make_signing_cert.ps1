<#
.SYNOPSIS
    Creates or backs up the self-signed code-signing certificate of «Норма ОТ» (UX-15).

.DESCRIPTION
    Used while there is no purchased certificate. The signature does not remove the
    SmartScreen warning for ordinary users, but it lets a corporate IT department
    trust the publisher once (see docs/CODE_SIGNING.md).

    The private key stays in the current user's certificate store (Windows DPAPI
    protects it) and is never written to the repository. `-Backup` exports a
    password-protected .pfx; the password is typed by you and is not stored anywhere.

.PARAMETER Backup
    Export a password-protected .pfx copy of the existing certificate.

.PARAMETER OutDir
    Where the public .cer (and the backup .pfx) are written.
    Default: %USERPROFILE%\NormaOT_code_signing

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools\make_signing_cert.ps1
    powershell -ExecutionPolicy Bypass -File tools\make_signing_cert.ps1 -Backup
#>
[CmdletBinding()]
param(
    [switch]$Backup,
    [string]$OutDir = "$env:USERPROFILE\NormaOT_code_signing",
    [string]$Subject = "CN=NormaOT (Кривоносов Д.А.), O=NormaOT, C=RU",
    [int]$Years = 10
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert |
        Where-Object { $_.Subject -eq $Subject } |
        Sort-Object NotAfter -Descending | Select-Object -First 1

if ($Backup) {
    if (-not $cert) { Write-Error "Сертификат не найден — сначала запустите скрипт без -Backup." }
    $pfx = Join-Path $OutDir "NormaOT_CodeSigning_backup.pfx"
    Write-Host "Придумайте пароль для резервной копии закрытого ключа (нигде не сохраняется)."
    $pwd = Read-Host -AsSecureString "Пароль"
    Export-PfxCertificate -Cert $cert -FilePath $pfx -Password $pwd -ChainOption EndEntityCertOnly | Out-Null
    Write-Host "Резервная копия: $pfx"
    Write-Host "Храните её офлайн (флешка, сейф). Потеря ключа = корпоративным заказчикам придётся ставить новый сертификат."
    exit 0
}

if ($cert) {
    Write-Host "Сертификат уже есть, новый не создаётся."
} else {
    $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject $Subject `
        -FriendlyName "NormaOT code signing" -KeyAlgorithm RSA -KeyLength 3072 `
        -HashAlgorithm SHA256 -KeyExportPolicy Exportable `
        -NotAfter (Get-Date).AddYears($Years) -CertStoreLocation Cert:\CurrentUser\My `
        -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")
    Write-Host "Создан новый сертификат."
}

$cer = Join-Path $OutDir "NormaOT_CodeSigning.cer"
Export-Certificate -Cert $cert -FilePath $cer -Type CERT | Out-Null

Write-Host "Отпечаток (SHA-1) : $($cert.Thumbprint)"
Write-Host "Субъект           : $($cert.Subject)"
Write-Host "Действует до      : $($cert.NotAfter.ToString('dd.MM.yyyy'))"
Write-Host "Открытая часть    : $cer"
Write-Host "SHA-256 файла .cer: $((Get-FileHash $cer -Algorithm SHA256).Hash)"
Write-Host ""
Write-Host "Подписывать сборку:  `$env:NORMAOT_SIGN_THUMBPRINT = '$($cert.Thumbprint)'; tools\sign_build.ps1"
Write-Host "Резервная копия ключа: tools\make_signing_cert.ps1 -Backup"
