param([string]$RepositoryRoot = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath($RepositoryRoot)
Get-Command ConvertFrom-Markdown -ErrorAction Stop | Out-Null
$documents = @('README.zh-CN.md','README.md','docs/STATUS.zh-CN.md','docs/STATUS.md','docs/USER_GUIDE.zh-CN.md','docs/USER_GUIDE.md')
$css = @'
:root{color-scheme:light;font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif;color:#20312b;background:#f5f4ef;line-height:1.75}
*{box-sizing:border-box}body{margin:0;padding:28px 18px}main{max-width:920px;margin:auto;background:#fff;padding:32px 40px;border:1px solid #dce3dc;border-radius:16px;overflow-wrap:anywhere}
h1{font-size:1.9rem;line-height:1.3;margin:0 0 18px}h2{font-size:1.35rem;line-height:1.4;margin:36px 0 14px;padding-top:10px;border-top:1px solid #e3e9e3}h3{font-size:1.1rem;margin-top:26px}p,ul,ol{margin:14px 0}li{padding-left:3px;margin:8px 0}a{color:#265d4b;text-underline-offset:3px}a:hover{color:#173c30}strong{font-weight:650}img{max-width:100%;height:auto;border-radius:6px}picture img{display:block}table{width:100%;border-collapse:collapse;margin:18px 0;font-size:.95rem}th,td{text-align:left;vertical-align:top;padding:10px 12px;border:1px solid #dce3dc}th{background:#eff4ee}td:first-child{min-width:95px}blockquote{margin:20px 0;padding:4px 16px;border-left:3px solid #a3b9a3;background:#f3f6f1}pre{max-width:100%;overflow:auto;background:#f3f5f1;padding:14px}code{font-size:.92em;white-space:break-spaces}summary{cursor:pointer;font-weight:600}details{margin:20px 0}.contents{padding:12px 16px;border:1px solid #dce3dc;background:#f7f8f4;border-radius:8px}.contents a{display:inline-block;margin:3px 15px 3px 0;font-size:.92rem}.contents-label{display:block;font-size:.9rem;font-weight:600;margin-bottom:5px}footer{max-width:920px;margin:14px auto;color:#647269;font-size:.85rem}
@media(max-width:600px){body{padding:10px}main{padding:22px 16px;border-radius:10px}h1{font-size:1.55rem}h2{font-size:1.2rem}th,td{padding:8px 7px;font-size:.9rem}td:first-child{min-width:0}ul,ol{padding-left:23px}}@media print{body{padding:0;background:#fff}main{border:0;padding:0;max-width:none}.contents{display:none}h2{break-after:avoid}img{max-height:90vh;object-fit:contain}tr{break-inside:avoid}}
'@
$written = @()
foreach ($relative in $documents) {
    $source = Join-Path $repo $relative
    $html = (ConvertFrom-Markdown -Path $source).Html
    $titleMatch = [regex]::Match($html, '<h1[^>]*>(.*?)</h1>', 'Singleline')
    if (-not $titleMatch.Success) { throw "Document has no title: $relative" }
    $title = [Net.WebUtility]::HtmlDecode(($titleMatch.Groups[1].Value -replace '<[^>]+>', ''))
    $zh = $relative.Contains('zh-CN')
    $language = if ($zh) { 'zh-CN' } else { 'en' }
    $tocTitle = if ($zh) { '按需要查看' } else { 'Jump to a section' }
    $names = @{}
    $toc = [Collections.Generic.List[string]]::new()
    $historyStart = $html.IndexOf('<details>')
    $html = [regex]::Replace($html, '<h([1-3])(?:\s+id="[^"]*")?>(.*?)</h\1>', {
        param($match)
        $level = $match.Groups[1].Value
        $label = [Net.WebUtility]::HtmlDecode(($match.Groups[2].Value -replace '<[^>]+>', ''))
        $base = (($label.ToLowerInvariant() -replace '[^\p{L}\p{Nd}\s_-]', '') -replace '\s+', '-').Trim('-')
        if (-not $base) { $base = 'section' }
        $id = $base
        if ($names.ContainsKey($base)) { $names[$base]++; $id = "$base-$($names[$base])" } else { $names[$base] = 0 }
        if ($level -eq '2' -and ($historyStart -lt 0 -or $match.Index -lt $historyStart)) {
            $toc.Add('<a href="#' + [Net.WebUtility]::HtmlEncode($id) + '">' + [Net.WebUtility]::HtmlEncode($label) + '</a>')
        }
        '<h' + $level + ' id="' + [Net.WebUtility]::HtmlEncode($id) + '">' + $match.Groups[2].Value + '</h' + $level + '>'
    }, 'Singleline')
    $html = [regex]::Replace($html, 'href="([^"#?]+)\.md([#?][^"]*)?"', {
        param($match)
        $target = $match.Groups[1].Value + '.md'
        if ($target -match '^https?://') { return $match.Value }
        $resolved = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $source) $target))
        $known = @($documents | ForEach-Object { [IO.Path]::GetFullPath((Join-Path $repo $_)) })
        if ($resolved -notin $known) { return $match.Value }
        'href="' + $match.Groups[1].Value + '.html' + $match.Groups[2].Value + '"'
    })
    if ($toc.Count -gt 0) {
        $at = $html.IndexOf('<h2')
        $nav = '<nav class="contents" aria-label="' + $tocTitle + '"><span class="contents-label">' + $tocTitle + '</span>' + ($toc -join '') + '</nav>'
        $html = $html.Insert($at, $nav)
    }
    $safeTitle = [Net.WebUtility]::HtmlEncode($title)
    $document = @"
<!doctype html>
<html lang="$language"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data: file:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; object-src 'none'; script-src 'none'"><title>$safeTitle</title><style>$css</style></head><body><main>$html</main><footer>Companion Type · Windows development documentation</footer></body></html>
"@
    $destination = [IO.Path]::ChangeExtension($source, '.html')
    [IO.File]::WriteAllText($destination, $document, [Text.UTF8Encoding]::new($false))
    $written += $destination
}
[pscustomobject]@{result='OFFLINE_DOCUMENTS_RENDERED';documents=$written;productBuildOrInstall=$false} | ConvertTo-Json -Depth 4
