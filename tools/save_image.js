// The image saves itself (docs/RESEARCH-WORKFLOW.md §4). Open the photograph's own URL in a new tab and run this in it with the file
// name filled in (the name tools/fetches.py printed): the tab fetches its own bytes and hands them to the browser as a download, and
// the call returns one line: ok image <type> <bytes>B, or BLOCKED <why> (nothing saved: a challenge or a sign-in comes back as HTML).
// The call is awaited: the browser tool that runs the script returns an awaited value and gives {} for a promise still pending, so
// the bare call saves the image and returns no line.
await (async function (name) {
  let r, b;
  try { r = await fetch(location.href); b = await r.blob(); } catch (e) { return "BLOCKED fetch failed: " + e.message; }
  if (!r.ok) return "BLOCKED http " + r.status;
  if (!/^image\//.test(b.type)) return "BLOCKED not an image: " + (b.type || "no type");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(b); a.download = name;
  document.body.appendChild(a); a.click();
  return "ok image " + b.type + " " + b.size + "B";
})("FILENAME.jpg")
