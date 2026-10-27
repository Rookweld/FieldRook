# Jury demo page (static, read-only)

`index.html` is a single self-contained file rendering one real captured
FieldRook incident (`inv-cd61de02c190`: demo-worker failure, live
`muse-spark-1.3` investigation, approved recovery, `VERIFIED_RESOLVED`).
It makes zero network calls: the data is inlined, there is no backend, no
execution path, and no credentials.

## Publish (requires explicit authorization — do NOT deploy yet)

Any static host works. GitHub Pages example:

1. In the GitHub repo: Settings → Pages → Deploy from branch → `master`,
   folder `/docs` (or a dedicated `gh-pages` branch containing only
   `docs/jury-demo/` content at its root).
2. Share the resulting URL with a note that it is a recorded demonstration.

## Regenerate

Re-run the Scenario B rehearsal, capture
`GET /api/investigations/{id}` to `recorded.json`, sanitize (no usernames,
paths, tokens, or private tasks), and rebuild the page from it. Keep the
RECORDED DEMONSTRATION banner: this page must never be mistaken for the
live application.
