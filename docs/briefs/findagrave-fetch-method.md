# Find a Grave: fetch one cited memorial through the owner's browser, and find the cheap way

You are a dedicated session for one problem. Read `CLAUDE.md`, `MEMORY.md`, `docs/AUDIT-PROMPT.md` and `docs/DIRECTOR-HANDOVER.md` first. Another worker is editing the repository at the same time; you commit nothing and edit no repository file. Your output is a fetched page in `inbox/`, a scratch test, and a report that describes a method the next person can follow verbatim, with its cost measured.

## The problem

The tree file cites Find a Grave memorials for many people, and a memorial carries the person's dates, places and named relatives with relationships, which is the richest single page we fetch. Find a Grave forbids automation, so a memorial is fetched one at a time in the owner's own browser, user-initiated. The last attempt cloned the rendered page, compressed and base64-encoded it, and read it out through the model in 25,000-character slices: nine slices for a 645 KB page of which the memorial's own markup was 17% and an ad network's iframe 59%; about eleven minutes and tens of thousands of tokens per slice; abandoned after four. That method is dead. Find the one that costs one or two calls and no model transcription.

## The record

Noi Segawa Davidson, memorial 155014393, cited in the file on Noi Davidson (1929–2015), the owner's grandmother. Open only that memorial's page. Open no other page, run no search, click nothing but what the method below needs. Stop and report if the site shows a login, a consent wall you cannot dismiss with one click, a rate-limit page, or a captcha.

## Methods to try, in this order, measuring each

For each attempt record: the calls made, wall-clock minutes, bytes on disk, whether any text passed through the model, and whether the file carries `<body id="memorial-summary">` (the marker the parser claims a memorial by) and the memorial's fields and family links. Stop at the first method that works; still write down why the earlier ones failed.

1. **The page saves itself.** From the page's own script, in one call: take the document's markup, drop `iframe`, `script`, `style`, `link` and `noscript` elements from a clone, hand the result to the browser as a download named `findagrave-memorial-155014393.html`. The file lands in the browser's download folder; move it to `inbox/`. If Chrome asks where to save, say so and answer the dialog once if the tools allow; if a dialog blocks the extension, report it and go to the next method.
2. **The page fetches itself.** From the page's own script, one request for the page's own URL with the page's own cookies, then the same download of the response text. This gives the server's HTML rather than the rendered DOM, usually far smaller and without the ad payload. Confirm the marker and fields survive.
3. **The browser's own save.** Ctrl+S through the keyboard shortcut tools, HTML only, into the download folder, then move to `inbox/`. Report whether a dialog needed a hand.
4. **Visible text as a fallback.** The extension's page-text tool, saved as `text/plain`. Only if the three above fail; note that the parser does not read this shape and a text parser would be needed.

## The test

On a scratch catalog under a scratch `DATA_ROOT` (`DATA_ROOT=<scratch> --db <scratch>/tree.db`; copy `catalog/tree.db` there first): copy the fetched file into the scratch inbox, attach it to Noi Davidson's cemetery step through the screen's attach path (a scratch server on another port), and report the extraction (fields as written, personas with relations) and the matcher's proposals verbatim. Integrity and foreign keys. The live catalog and the repository's `archive/` are not touched; the real `inbox/` keeps the file for the owner.

## The report

One page: the method that worked as a numbered procedure anyone can repeat; a table of the attempts with minutes, calls, bytes and whether the model transcribed anything; the marker and field check; the scratch test rows; findings. The director folds the procedure into `docs/RESEARCH-WORKFLOW.md` §4 and briefs the worker for any parser change; you change no file in the repository.
