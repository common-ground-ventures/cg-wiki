# Wiki cutover gate G2: parity against the final commit (2026-10-21)

Run 2026-10-21 10:30 MST with tools/http_parity.py (no redirects followed; status, Location, body sha1, content-type, x-robots-tag, cache-control, x-frame-options).
- A: https://wiki.commonground.ventures (live, Vercel)
- B: https://cf-workers-static-cg-wiki.common-ground-ventures.workers.dev (Workers Builds preview of PR #1 head 0b1cc6d, the final commit)
- Paths: receipts/parity-paths.txt, 464 paths. Raw output: parity-2026-10-21-live-vs-final-preview-0b1cc6d.txt

Result: the same 54 differences as the e457720 receipt, path for path. Nothing new, nothing cleared.
- 410 paths differ only by the preview's x-robots-tag noindex (Cloudflare adds it on preview URLs; live sends none).
- 54 paths are redirect shape only: 23 Location and header differences, 18 header-only differences on redirects, 12 slash-less page URLs that live answers 200 and the Worker answers 307 to the slash form (same page), 1 status difference. These are the trailing-slash 307s and the index.html alias hops accepted for beta (Robbie, 10/20).
- Zero differences in any page body that is served at the same URL on both sides.

Indexing intent: live robots.txt is "Allow: /" with the sitemap, pages carry no robots meta and live sends no x-robots-tag. The branch adds no _headers, so production should send no x-robots-tag. Checked again on the real domain after cutover (G3).
