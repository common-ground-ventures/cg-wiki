# wiki.commonground.ventures

The Common Ground public wiki: a static site, 407 files (394 HTML pages), plus vercel.json (cleanUrls and 8 redirects).
Live today on Vercel project cg-wiki (team jesse-fowlers-projects), CLI-deployed.
Branch main = the exact files of the live production deployment (dpl_9Jm4MXZWs6Yy3QQAxMmiHdrNHJ9w), downloaded from Vercel 2026-10-19 and sha1-checked, 407 of 407.
Upstream: the wiki generator (~/Desktop/WIKI-REBUILD-2026-09-25/out/_build on the laptop) builds these pages. The generator stays local for now; only its output is the deployable.
Branch pending-build-2026-10-18 (laptop only, not pushed: this repo is public) = the local build that is newer than live (6 files). It goes live only on Jesse's go.

## How it builds and deploys (Cloudflare Workers static assets, after this PR merges and Jesse connects Workers Builds)
- No build step. The site is the files in this repo, served as-is by a Worker named cg-wiki with static assets only, no worker script (wrangler.jsonc, assets.directory is the repo root).
- .assetsignore keeps repo files (SITE.md, vercel.json, wrangler.jsonc, receipts/, .git) out of the upload and off the public site. Add any new repo-only file or folder there.
- _redirects holds the 8 legacy redirects copied from vercel.json (same 308 and 301 codes) plus 308s for index.html and .html URLs, which Vercel sends as permanent.
- html_handling is auto-trailing-slash because every canonical tag, sitemap entry and internal link in the wiki ends in a slash (/work/, /alex-prince/). not_found_handling is none: an unknown path is a plain 404.
- Workers Builds, connected to this repo: production branch main runs `npx wrangler deploy`; every other branch runs `npx wrangler versions upload` and gets its own preview URL; the preview command is `npx wrangler preview`. wrangler is not a package dependency, always `npx wrangler@4.147.0`. Nobody deploys from a laptop.
- vercel.json stays in place and Vercel stays live until the cutover is done (domain on Cloudflare, parity re-run on the custom domain).

## Local
`npx wrangler@4.147.0 dev --port 8791 --persist-to ../wrangler-state` then http://localhost:8791. Keep --persist-to outside the repo: the repo root is the assets folder, and wrangler state inside it makes the dev server reload in a loop.
Parity against live: `python3 tools/http_parity.py https://wiki.commonground.ventures http://127.0.0.1:8791 receipts/parity-paths.txt` (tool lives in the OPERATIONS cg-migration folder on Jesse's machines). Latest result: receipts/parity-2026-10-19-live-vs-local.txt.

## Review rules
- Infrastructure changes (wrangler.jsonc, _redirects, _headers, .assetsignore, vercel.json, build and deploy settings, DNS) stay open until Robbie (robbyproc87) reviews.
- Copy changes (page text, new pages) merge directly.
- Brand files (style.css, the visual engines, the footer credit) wait for Jimmy's code-owner sign-off.
- No direct pushes and no force pushes to main. Everything goes through a pull request.
