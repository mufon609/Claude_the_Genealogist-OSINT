// The page saves itself (docs/RESEARCH-WORKFLOW.md §4). Run in the page's own tab with the call tools/fetches.py printed for the
// page in place of ("FILENAME.html"): the file name, true to save a page of no known kind anyway, and the key, the plan steps the
// page was saved for, written as a second comment under the saved-from line (a page saved by hand gives no key and carries none).
// It waits up to 15 s for the page's own markup, saves the document with its iframes, scripts, styles, links and noscript removed as
// a download (a page that renders inside open shadow roots, archive.org's, whose plain copy is nearly empty, is serialized with its
// shadow roots as declarative shadow DOM), and returns one line: ok <kind> <bytes>B, BLOCKED signin | challenge,
// EMPTY <why>, or UNKNOWN <title> (not saved). Kinds: fs-search (FamilySearch results rows, or its "No Results"), fs-record,
// fg-memorial, fg-search, aad. One download per tab: Chrome lets a page start one without a hand on it. The call is awaited: the
// browser tool that runs the script returns an awaited value and gives {} for a promise still pending, so the bare call saves the
// page and returns no line.
await (async function (name, force, key) {
  const KINDS = {
    "fs-search": h => /<tr[^>]*\bdata-testid="\/ark:\/61903\/1:1:/.test(h) || />No Results Found</.test(h),
    "fs-record": h => /data-testid="documentInformationCitation"[\s\S]{0,400}?familysearch\.org\/ark:\/61903\/1:1:/.test(h),
    "fg-memorial": h => /<body[^>]*\bid="memorial-summary"/.test(h),
    "fg-search": h => /<body[^>]*\bid="memorial-list"/.test(h),
    "aad": h => /Access to Archival Databases \(AAD\)/.test(h)
  };
  const head = () => "<!-- saved from " + location.href + " -->\n" + (key ? "<!-- for steps " + key + " -->\n" : "");
  const snap = () => {
    const d = document.documentElement.cloneNode(true);
    d.querySelectorAll("iframe, script, style, link, noscript").forEach(e => e.remove());
    return head() + d.outerHTML;
  };
  const roots = () => { const out = []; const walk = r => r.querySelectorAll("*").forEach(e => { if (e.shadowRoot) { out.push(e.shadowRoot); walk(e.shadowRoot); } }); walk(document); return out; };
  const text = h => h.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  const deep = () => { const r = roots(); return r.length && document.documentElement.getHTML ? head() + "<html>" +
    document.documentElement.getHTML({shadowRoots: r}).replace(/<(script|style|iframe|noscript)\b[\s\S]*?<\/\1>|<link\b[^>]*>/gi, "") + "</html>" : null; };
  const block = () => document.querySelector("input[type=password]") ? "signin"
    : /just a moment|attention required|access denied|verify you are human|captcha/i.test(document.title) ||
      document.querySelector("#challenge-form, .cf-turnstile, iframe[src*='challenges.cloudflare'], iframe[src*='captcha']") ? "challenge" : null;
  const stop = Date.now() + 15000;
  let html, kind, b;
  for (;;) {
    html = snap(); if (text(html).length < 200) html = deep() || html;
    kind = Object.keys(KINDS).find(k => KINDS[k](html)); b = block();
    if (kind || b === "signin" || Date.now() > stop) break;
    await new Promise(r => setTimeout(r, 500));
  }
  if (!kind && b) return "BLOCKED " + b;
  if (!kind && !force) {
    const t = text(html);
    if (t.length < 200) return "EMPTY " + (/javascript/i.test(t) || document.querySelector("noscript") ? "no-script fallback" : "no content");
    return "UNKNOWN " + document.title.slice(0, 60) + " " + html.length + "B, not saved: true as the second argument saves it";
  }
  const blob = new Blob([html], {type: "text/html"}), a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click();
  return "ok " + (kind || "unknown") + " " + blob.size + "B" + (kind === "fg-memorial" && !/member-family/.test(html) ? ", no family block" : "");
})("FILENAME.html")
