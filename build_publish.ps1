param(
  [string]$Root = $PSScriptRoot,
  [string]$OutDir = $(Join-Path $PSScriptRoot "dist")
)

$ErrorActionPreference = "Stop"

Push-Location $Root
try {
  if (Test-Path -LiteralPath $OutDir) {
    Get-ChildItem -LiteralPath $OutDir -Force |
      Where-Object { $_.Name -ne ".vercel" } |
      ForEach-Object {
        $PublishItem = $_.FullName
        try {
          Remove-Item -LiteralPath $PublishItem -Recurse -Force -ErrorAction Stop
        }
        catch {
          Write-Warning "Could not remove locked publish item: $PublishItem"
        }
      }
  }

  $env:PYTHONIOENCODING = "utf-8"
  $env:PYTHONDONTWRITEBYTECODE = "1"
  python sync_components.py --add-sentinels --write --no-backup
  python update_atb_archive.py --write
  python sync_components.py --write --no-backup
  python optimize_site.py
  powershell -ExecutionPolicy Bypass -File .\optimize_images.ps1

  New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
  New-Item -ItemType Directory -Force -Path (Join-Path $OutDir "assets") | Out-Null

  Get-ChildItem -File -Path $Root |
    Where-Object { $_.Extension -in ".html", ".xml", ".txt" -and $_.Name -notlike "*.bak" } |
    Copy-Item -Destination $OutDir

  $AtbSource = Join-Path $Root "atb"
  if (Test-Path -LiteralPath $AtbSource) {
    Copy-Item -LiteralPath $AtbSource -Destination (Join-Path $OutDir "atb") -Recurse -Force
  }

  $MembersSource = Join-Path $Root "members"
  if (Test-Path -LiteralPath $MembersSource) {
    Copy-Item -LiteralPath $MembersSource -Destination (Join-Path $OutDir "members") -Recurse -Force
  }

  foreach ($CleanUrlDir in @("legal", "terms", "privacy")) {
    $CleanUrlSource = Join-Path $Root $CleanUrlDir
    if (Test-Path -LiteralPath $CleanUrlSource) {
      Copy-Item -LiteralPath $CleanUrlSource -Destination (Join-Path $OutDir $CleanUrlDir) -Recurse -Force
    }
  }

  $RootSupportFiles = @("rss-feeds.json", "update_rss_collection.ps1", "install_rss_collection_task.ps1")
  foreach ($SupportFile in $RootSupportFiles) {
    $SupportPath = Join-Path $Root $SupportFile
    if (Test-Path -LiteralPath $SupportPath) {
      Copy-Item -LiteralPath $SupportPath -Destination $OutDir -Force
    }
  }

  $RssCandidates = Join-Path $Root "Intel Production\rss-candidates.json"
  if (Test-Path -LiteralPath $RssCandidates) {
    Copy-Item -LiteralPath $RssCandidates -Destination (Join-Path $OutDir "rss-candidates.json") -Force
    New-Item -ItemType Directory -Force -Path (Join-Path $OutDir "Intel Production") | Out-Null
    Copy-Item -LiteralPath $RssCandidates -Destination (Join-Path $OutDir "Intel Production\rss-candidates.json") -Force
  }

  do {
    $CopiedHtml = $false
    $HtmlRefs = New-Object System.Collections.Generic.HashSet[string]
    Get-ChildItem -File -Path $OutDir -Filter "*.html" | ForEach-Object {
      $Content = Get-Content -LiteralPath $_.FullName -Raw
      [regex]::Matches($Content, 'href="([^"]+\.html)"', 'IgnoreCase') | ForEach-Object {
        $Href = $_.Groups[1].Value
        if ($Href -notmatch '^(https?:)?//' -and $Href -notmatch '/' -and $Href -notmatch '\\') {
          [void]$HtmlRefs.Add($Href)
        }
      }
    }
    foreach ($HtmlRef in $HtmlRefs) {
      $DestinationHtml = Join-Path $OutDir $HtmlRef
      if (Test-Path -LiteralPath $DestinationHtml) {
        continue
      }
      $SourceHtml = Join-Path $Root $HtmlRef
      if (-not (Test-Path -LiteralPath $SourceHtml)) {
        $SourceHtml = Get-ChildItem -Path $Root -Recurse -File -Filter $HtmlRef |
          Where-Object { $_.FullName -notlike "*\Extra\*" -and $_.FullName -notlike "*\dist\*" } |
          Select-Object -First 1 -ExpandProperty FullName
      }
      if ($SourceHtml -and (Test-Path -LiteralPath $SourceHtml)) {
        Copy-Item -LiteralPath $SourceHtml -Destination $DestinationHtml -Force
        $CopiedHtml = $true
      }
    }
  } while ($CopiedHtml)

  $ImageRefs = New-Object System.Collections.Generic.HashSet[string]
  Get-ChildItem -File -Path $OutDir -Filter "*.html" | ForEach-Object {
    $Content = Get-Content -LiteralPath $_.FullName -Raw
    [regex]::Matches($Content, 'src="([^"]+\.(?:png|jpg|jpeg|svg))"', 'IgnoreCase') | ForEach-Object {
      $Src = $_.Groups[1].Value
      if ($Src -notmatch '^(https?:)?//' -and $Src -notmatch '/' -and $Src -notmatch '\\') {
        [void]$ImageRefs.Add($Src)
      }
    }
  }
  foreach ($ImageRef in $ImageRefs) {
    $SourceImage = Join-Path $Root $ImageRef
    if (Test-Path -LiteralPath $SourceImage) {
      try {
        Copy-Item -LiteralPath $SourceImage -Destination $OutDir -Force -ErrorAction Stop
      }
      catch {
        Write-Warning "Could not copy locked image: $ImageRef"
      }
    }
  }

  if (Test-Path -LiteralPath (Join-Path $Root "assets")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $OutDir "assets") | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $Root "assets") -Recurse -File |
      Where-Object { $_.FullName -notlike "*\assets\originals\*" } |
      ForEach-Object {
        $Relative = $_.FullName.Substring((Join-Path $Root "assets").Length).TrimStart("\")
        $Destination = Join-Path (Join-Path $OutDir "assets") $Relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
        try {
          Copy-Item -LiteralPath $_.FullName -Destination $Destination -Force -ErrorAction Stop
        }
        catch {
          Write-Warning "Could not copy locked asset: $Relative"
        }
      }
  }

  Get-ChildItem -LiteralPath $OutDir -Recurse -File -Filter "*.bak" |
    Remove-Item -Force

  Write-Host "Publish folder ready: $OutDir"
}
finally {
  Pop-Location
}
