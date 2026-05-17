param(
  [string]$FeedList = ".\rss-feeds.json",
  [string]$OutputPath = ".\Intel Production\rss-candidates.json",
  [int]$Days = 7
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not [System.IO.Path]::IsPathRooted($FeedList)) { $FeedList = Join-Path $root $FeedList }
if (-not [System.IO.Path]::IsPathRooted($OutputPath)) { $OutputPath = Join-Path $root $OutputPath }

function Get-TextValue {
  param($Node, [string]$Name)
  $child = $Node.SelectSingleNode("*[local-name()='$Name']")
  if ($child) { return ([string]$child.InnerText).Trim() }
  return ""
}

function Get-LinkValue {
  param($Node)
  $origLink = $Node.SelectSingleNode("*[local-name()='origLink']")
  if ($origLink) { return ([string]$origLink.InnerText).Trim() }
  $canonical = $Node.SelectSingleNode("*[local-name()='link'][@rel='canonical'][@href]")
  if ($canonical) { return ([string]$canonical.href).Trim() }
  $alternate = $Node.SelectSingleNode("*[local-name()='link'][@rel='alternate'][@href]")
  if ($alternate) { return ([string]$alternate.href).Trim() }
  $rssLink = Get-TextValue $Node "link"
  if ($rssLink) { return $rssLink }
  $atomLink = $Node.SelectSingleNode("*[local-name()='link'][@href]")
  if ($atomLink) { return ([string]$atomLink.href).Trim() }
  return ""
}

function Parse-DateValue {
  param([string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) { return $null }
  try { return [DateTimeOffset]::Parse($Value).DateTime } catch { return $null }
}

function Suggest-PIRs {
  param([string]$Text)
  $t = $Text.ToLowerInvariant()
  $pirs = New-Object System.Collections.Generic.List[int]

  if ($t -match "\b(energy|ercot|grid|electric|electricity|power|pipeline|lng|oil|gas|ot|ics|industrial control|refinery|substation)\b") { $pirs.Add(1); $pirs.Add(2); $pirs.Add(3) }
  if ($t -match "\b(bank|banking|payment|payments|fintech|swift|crypto|cryptocurrency|ofac|fincen|treasury|financial)\b") { $pirs.Add(4); $pirs.Add(6) }
  if ($t -match "\b(north korea|dprk|lazarus|it worker|laptop farm)\b") { $pirs.Add(5); $pirs.Add(12) }
  if ($t -match "\b(hospital|healthcare|patient|medical|clinic|hhs|hc3|medical device)\b") { $pirs.Add(7); $pirs.Add(8); $pirs.Add(9) }
  if ($t -match "\b(defense|aerospace|dib|export control|intellectual property|ip theft|china|prc|espionage)\b") { $pirs.Add(10); $pirs.Add(11) }
  if ($t -match "\b(russia|russian|ransomware|extortion|access broker|botnet)\b") { $pirs.Add(13) }
  if ($t -match "\b(iran|iranian|proxy|hacktivist|ddos|defacement)\b") { $pirs.Add(14) }
  if ($t -match "\b(artificial intelligence|ai|data center|data centers|cloud|gpu|model)\b") { $pirs.Add(15) }
  if ($t -match "\b(election|elections|voting|voter|county government)\b") { $pirs.Add(16) }

  return @($pirs | Select-Object -Unique)
}

function Limit-Text {
  param([string]$Value, [int]$Max = 500)
  if ([string]::IsNullOrWhiteSpace($Value)) { return "" }
  $clean = [System.Net.WebUtility]::HtmlDecode($Value)
  $clean = (($clean -replace "<[^>]+>", " ") -replace "\s+", " ").Trim()
  if ($clean.Length -le $Max) { return $clean }
  return $clean.Substring(0, $Max) + "..."
}

function Get-SummaryValue {
  param($Node, [string]$Title, [string]$Source)
  $summary = Get-TextValue $Node "description"
  if (-not $summary) { $summary = Get-TextValue $Node "summary" }
  if (-not $summary) { $summary = Get-TextValue $Node "content" }
  if (-not $summary) { $summary = Get-TextValue $Node "encoded" }
  $clean = Limit-Text $summary 700
  if ($clean) { return $clean }
  return "RSS item from $Source. The feed did not provide a summary, so review the linked article before promotion: $Title"
}

function Resolve-FinalUrl {
  param([string]$Url)
  if ([string]::IsNullOrWhiteSpace($Url)) { return "" }
  if ($Url -notmatch "^https?://") { return "" }
  $needsResolve = $Url -match "feeds\.|feedproxy|rssing|/link/|utm_|trk=|redirect|click"
  if (-not $needsResolve) { return $Url }
  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 15 -MaximumRedirection 5 -Headers @{ "User-Agent" = "LibertyCTI-RSS-Collector/1.0" }
    $final = $response.BaseResponse.ResponseUri.AbsoluteUri
    if ($final -match "^https?://") { return $final }
  } catch {}
  return $Url
}

function Test-LibertyRelevance {
  param([string]$Text, [string]$Category, [int[]]$PIRs)
  $t = $Text.ToLowerInvariant()
  if ($Category -eq "Texas / Regional") {
    return ($t -match "\b(cyber|breach|ransomware|ercot|grid|power|energy|oil|gas|lng|pipeline|hospital|healthcare|bank|payment|defense|military|data center|data centers|cloud|critical infrastructure|port|ports|water|telecom|election|elections|voting|emergency management|disaster response)\b")
  }
  return (($PIRs.Count -gt 0) -or ($t -match "\b(cyber|security|infrastructure|ransomware|breach|malware|espionage|sanction|sanctions|taiwan|ukraine|middle east|iran|iranian|china|prc|russia|russian|north korea|dprk|ercot|grid|hospital|healthcare|bank|payment|defense|aerospace|data center|data centers|cloud|artificial intelligence|supply chain|critical infrastructure|port|ports|water|telecom|election|elections|voting|oil|gas|lng|pipeline|ot|ics)\b"))
}

if (-not (Test-Path -LiteralPath $FeedList)) {
  throw "Feed list not found: $FeedList"
}

$feeds = Get-Content -LiteralPath $FeedList -Raw -Encoding UTF8 | ConvertFrom-Json
$cutoff = (Get-Date).AddDays(-1 * $Days)
$items = New-Object System.Collections.Generic.List[object]
$failures = New-Object System.Collections.Generic.List[object]

foreach ($feed in $feeds) {
  try {
    $response = Invoke-WebRequest -Uri $feed.url -UseBasicParsing -TimeoutSec 30
    [xml]$xml = $response.Content
    $nodes = @($xml.SelectNodes("//*[local-name()='item']"))
    if ($nodes.Count -eq 0) { $nodes = @($xml.SelectNodes("//*[local-name()='entry']")) }

    foreach ($node in $nodes) {
      $title = Get-TextValue $node "title"
      $url = Resolve-FinalUrl (Get-LinkValue $node)
      $summary = Get-SummaryValue $node $title ([string]$feed.name)
      $dateText = Get-TextValue $node "pubDate"
      if (-not $dateText) { $dateText = Get-TextValue $node "published" }
      if (-not $dateText) { $dateText = Get-TextValue $node "updated" }
      $published = Parse-DateValue $dateText

      if ($title -and $url -and $published -and $published -ge $cutoff) {
        $text = "$title $summary $($feed.name) $($feed.category)"
        $pirs = @(Suggest-PIRs $text)
        $isRelevant = Test-LibertyRelevance $text ([string]$feed.category) $pirs
        if (-not $isRelevant) { continue }
        $items.Add([pscustomobject]@{
          id = "rss-" + ([guid]::NewGuid().ToString("N"))
          title = $title
          url = $url
          source = [string]$feed.name
          category = [string]$feed.category
          published = $published.ToString("yyyy-MM-dd")
          summary = $summary
          suggestedPirIds = $pirs
          suggestedSector = if ($text -match "energy|ercot|grid|power|ot|ics") { "Energy" } elseif ($text -match "bank|payment|financial|crypto") { "Finance" } elseif ($text -match "hospital|health|medical") { "Healthcare" } elseif ($text -match "defense|aerospace|dib") { "Defense Industrial Base" } elseif ($text -match "data center|cloud|artificial intelligence| ai ") { "AI / Data Centers" } else { "Cross-Sector" }
        })
      }
    }
  } catch {
    $failures.Add([pscustomobject]@{
      source = [string]$feed.name
      url = [string]$feed.url
      error = Limit-Text $_.Exception.Message 500
    })
  }
}

$outDir = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }

$sortedItems = @($items.ToArray() | Sort-Object -Property @{Expression = { $_.published }; Descending = $true}, @{Expression = { $_.source }; Ascending = $true}, @{Expression = { $_.title }; Ascending = $true})

$payload = [ordered]@{
  generatedAt = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")
  windowDays = $Days
  itemCount = $items.Count
  failureCount = $failures.Count
  failures = @($failures.ToArray())
  items = @($sortedItems)
}

$payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Host "Wrote $($items.Count) RSS candidate(s) to $OutputPath"
if ($failures.Count -gt 0) {
  Write-Host "Feed failures: $($failures.Count). See failures in the JSON output."
}
