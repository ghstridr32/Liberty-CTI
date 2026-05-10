param(
  [string]$Root = $PSScriptRoot
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$Originals = Join-Path $Root "assets\originals"
New-Item -ItemType Directory -Force -Path $Originals | Out-Null

$Targets = @(
  @{ Name = "liberty-cti-emblem.png"; Max = 512; Quality = 90 },
  @{ Name = "Texas-Cyber-Threat.png"; Output = "Texas-Cyber-Threat.jpg"; Max = 1100; Quality = 86 },
  @{ Name = "WHSR.png"; Output = "WHSR.jpg"; Max = 1200; Quality = 86 },
  @{ Name = "HKIA-Afghanistan.jpg"; Max = 1400; Quality = 82 },
  @{ Name = "luis-maldonado-headshot.jpg"; Max = 1200; Quality = 82 },
  @{ Name = "angie-maldonado-headshot.jpg"; Max = 1200; Quality = 82 },
  @{ Name = "angie-rose-garden.jpg"; Max = 1400; Quality = 82 },
  @{ Name = "Angie-aide-promo.jpg"; Max = 1400; Quality = 82 },
  @{ Name = "luis-maldonado-command.jpeg"; Max = 1200; Quality = 82 },
  @{ Name = "angie-maldonado-DSD.jpeg"; Max = 1200; Quality = 82 },
  @{ Name = "luis-maldonado-west-wing.jpeg"; Max = 1200; Quality = 82 },
  @{ Name = "luis-maldonado-white-house.jpeg"; Max = 1200; Quality = 82 },
  @{ Name = "maldonado-promotion-ceremony.jpeg"; Max = 1200; Quality = 82 },
  @{ Name = "angie-maldonado-POTUS.jpeg"; Max = 1200; Quality = 82 }
)

function Get-Encoder($MimeType) {
  [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() |
    Where-Object { $_.MimeType -eq $MimeType } |
    Select-Object -First 1
}

function Save-Jpeg($Bitmap, $Path, $Quality) {
  $Encoder = Get-Encoder "image/jpeg"
  $Params = New-Object System.Drawing.Imaging.EncoderParameters(1)
  $Params.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter(
    [System.Drawing.Imaging.Encoder]::Quality,
    [int64]$Quality
  )
  $Bitmap.Save($Path, $Encoder, $Params)
  $Params.Dispose()
}

foreach ($Target in $Targets) {
  $Path = Join-Path $Root $Target.Name
  if (-not (Test-Path -LiteralPath $Path)) {
    Write-Host "Skip missing $($Target.Name)"
    continue
  }

  $Backup = Join-Path $Originals $Target.Name
  if (-not (Test-Path -LiteralPath $Backup)) {
    Copy-Item -LiteralPath $Path -Destination $Backup
  }

  $OutputName = if ($Target.ContainsKey("Output")) { $Target.Output } else { $Target.Name }
  $OutputPath = Join-Path $Root $OutputName
  $Before = (Get-Item -LiteralPath $Path).Length
  $Image = [System.Drawing.Image]::FromFile($Path)
  try {
    $Scale = [Math]::Min(1.0, [double]$Target.Max / [Math]::Max($Image.Width, $Image.Height))
    $NewWidth = [Math]::Max(1, [int][Math]::Round($Image.Width * $Scale))
    $NewHeight = [Math]::Max(1, [int][Math]::Round($Image.Height * $Scale))

    $Bitmap = New-Object System.Drawing.Bitmap($NewWidth, $NewHeight)
    try {
      $Graphics = [System.Drawing.Graphics]::FromImage($Bitmap)
      try {
        $Graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
        $Graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $Graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
        $Graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $Graphics.DrawImage($Image, 0, 0, $NewWidth, $NewHeight)
      }
      finally {
        $Graphics.Dispose()
      }

      $Temp = "$OutputPath.tmp"
      $Ext = [System.IO.Path]::GetExtension($OutputPath).ToLowerInvariant()
      if ($Ext -eq ".jpg" -or $Ext -eq ".jpeg") {
        Save-Jpeg $Bitmap $Temp $Target.Quality
      }
      else {
        $Bitmap.Save($Temp, [System.Drawing.Imaging.ImageFormat]::Png)
      }
    }
    finally {
      $Bitmap.Dispose()
    }
  }
  finally {
    $Image.Dispose()
  }

  Move-Item -LiteralPath "$OutputPath.tmp" -Destination $OutputPath -Force
  $After = (Get-Item -LiteralPath $OutputPath).Length
  $Saved = [Math]::Round(($Before - $After) / 1MB, 2)
  Write-Host "$($Target.Name) -> $OutputName`: $([Math]::Round($Before/1KB,0)) KB -> $([Math]::Round($After/1KB,0)) KB (saved $Saved MB)"
}
