// The page saves itself (docs/RESEARCH-WORKFLOW.md §4). Run in the page's own tab with the file name filled in; the
// browser downloads the page's markup, scripts and styles removed, and the call returns the byte count and whether the
// parsers' markers are present. One download per tab: Chrome lets a page start one without a hand on it.
(function (name) {
  const doc = document.documentElement.cloneNode(true);
  doc.querySelectorAll("iframe, script, style, link, noscript").forEach(e => e.remove());
  const html = "<!-- saved from " + location.href + " -->\n" + doc.outerHTML;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([html], {type: "text/html"})); a.download = name;
  document.body.appendChild(a); a.click();
  return {bytes: html.length,
          memorial: /<body[^>]*\bid="memorial-summary"/.test(html), memorial_family: /member-family/.test(html),
          findagrave_search: /<body[^>]*\bid="memorial-list"/.test(html),
          familysearch: /documentInformationCitation/.test(html) && /ark:\/61903\/1:1:/.test(html),
          aad: /Access to Archival Databases \(AAD\)/.test(html)};
})("FILENAME.html");
