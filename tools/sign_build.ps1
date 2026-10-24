<#
.SYNOPSIS
    Authenticode-signs the built NormaOT EXE (UX-15).

.DESCRIPTION
    Run after `PyInstaller NormaOT_Reestr.spec`, before packing the zip.
    The certificate is never stored in the repository: pass its thumbprint from the
    certificate store (a USB token or HSM key works this way too) or a .pfx path.

    Signing is always timestamped, so the signature stays valid after the
    certificate expires.

.PARAMETER Thumbprint
    SHA-1 thumbprint of a code-signing certificate in Cert:\CurrentUser\My.
    Defaults to the NORMAOT_SIGN_THUMBPRINT environment variable.

.PARAMETER PfxPath
    Alternative to -Thumbprint: path to a .pfx file (outside the repository).

.PARAMETER PfxPassword
    Password for the .pfx as a SecureString. Defaults to NORMAOT_SIGN_PFX_PASSWORD.
    Never pass it as plain text on the command line - it lands in the shell history.

.PARAMETER Path
    File to sign. Default: dist\NormaOT_Reestr\NormaOT_Reestr.exe

.PARAMETER TimestampServer
    RFC 3161 timestamp server. Default: http://timestamp.digicert.com

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools\sign_build.ps1 -Thumbprint ABC123...

.EXAMPLE
    # No certificate yet - reports it and leaves the build unsigned (exit code 2)
    powershell -ExecutionPolicy Bypass -File tools\sign_build.ps1
#>
[CmdletBinding()]
param(
    [string]$Thumbprint = $env:NORMAOT_SIGN_THUMBPRINT,
    [string]$PfxPath,
    [System.Security.SecureString]$PfxPassword,
    [string]$Path = "dist\NormaOT_Reestr\NormaOT_Reestr.exe",
    [string]$TimestampServer = "http://timestamp.digicert.com",
    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"

function Show-Signature($file) {
    $sig = Get-AuthenticodeSignature -FilePath $file
    Write-Host "Статус подписи : $($sig.Status)"
    if ($sig.SignerCertificate) {
        Write-Host "Кому выдан     : $($sig.SignerCertificate.Subject)"
        Write-Host "Кем выдан      : $($sig.SignerCertificate.Issuer)"
        Write-Host "Действует до   : $($sig.SignerCertificate.NotAfter.ToString('dd.MM.yyyy'))"
    }
    if ($sig.TimeStamperCertificate) {
        Write-Host "Метка времени  : есть"
    } elseif ($sig.Status -ne 'NotSigned') {
        Write-Host "Метка времени  : НЕТ - подпись станет недействительной после истечения сертификата"
    }
    return $sig
}

if (-not (Test-Path $Path)) {
    Write-Error "Файл не найден: $Path. Сначала соберите EXE (PyInstaller NormaOT_Reestr.spec)."
}

if ($VerifyOnly) {
    Show-Signature $Path | Out-Null
    exit 0
}

# --- pick the certificate ---------------------------------------------------
$cert = $null
if ($PfxPath) {
    if (-not (Test-Path $PfxPath)) { Write-Error "Не найден .pfx: $PfxPath" }
    if (-not $PfxPassword -and $env:NORMAOT_SIGN_PFX_PASSWORD) {
        $PfxPassword = ConvertTo-SecureString $env:NORMAOT_SIGN_PFX_PASSWORD -AsPlainText -Force
    }
    $cert = if ($PfxPassword) {
        New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 $PfxPath, $PfxPassword
    } else {
        Get-PfxCertificate -FilePath $PfxPath
    }
} elseif ($Thumbprint) {
    $Thumbprint = $Thumbprint -replace '[^0-9A-Fa-f]', ''
    $cert = Get-ChildItem Cert:\CurrentUser\My, Cert:\LocalMachine\My -CodeSigningCert |
            Where-Object { $_.Thumbprint -eq $Thumbprint } | Select-Object -First 1
    if (-not $cert) { Write-Error "Сертификат с отпечатком $Thumbprint не найден (нужен сертификат подписи кода с закрытым ключом)." }
} else {
    Write-Warning @"
Сертификат подписи не задан - сборка останется НЕПОДПИСАННОЙ.
Windows SmartScreen будет предупреждать при запуске.
Задайте один из вариантов:
  `$env:NORMAOT_SIGN_THUMBPRINT = '<отпечаток>'   (сертификат в хранилище, в т.ч. на токене)
  tools\sign_build.ps1 -PfxPath C:\path\to\cert.pfx
Подробности и варианты получения сертификата - docs/CODE_SIGNING.md.
"@
    exit 2
}

if (-not $cert.HasPrivateKey) { Write-Error "У сертификата нет закрытого ключа - подписать нельзя." }

# --- sign -------------------------------------------------------------------
"Подписывается: $Path"
$result = Set-AuthenticodeSignature -FilePath $Path -Certificate $cert `
    -HashAlgorithm SHA256 -TimestampServer $TimestampServer -IncludeChain NotRoot
if ($result.Status -ne 'Valid' -and $result.Status -ne 'UnknownError') {
    Show-Signature $Path | Out-Null
    Write-Error "Подписание не удалось: $($result.Status) - $($result.StatusMessage)"
}

$sig = Show-Signature $Path
if (-not $sig.TimeStamperCertificate) {
    Write-Error "Нет метки времени (сервер $TimestampServer недоступен?) - пересоберите и подпишите заново."
}
if ($sig.Status -eq 'Valid') {
    "Готово: подпись действительна."
} else {
    Write-Warning "Подпись проставлена, но Windows ей не доверяет ($($sig.Status)). Для самоподписанного сертификата это нормально; для покупного проверьте цепочку."
}
