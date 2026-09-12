// The image saves itself (docs/RESEARCH-WORKFLOW.md §4). Open the photograph's own URL in a new tab and run this in it with
// the file name filled in (the name tools/fetches.py list printed): the tab fetches its own bytes and hands them to the
// browser as a download; the call returns the byte count and the content type. One download per tab, as for a page.
(function (name) {
  return fetch(location.href).then(r => r.blob()).then(b => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(b); a.download = name;
    document.body.appendChild(a); a.click();
    return {bytes: b.size, type: b.type};
  });
})("FILENAME.jpg");
