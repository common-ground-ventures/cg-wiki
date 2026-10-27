#!/usr/bin/env python3
"""Parity of the Astro build against a reference copy of the wiki.

    python3 tools/pilot_parity.py --ref <dir of the current site files> --new dist [--live https://wiki.commonground.ventures]

Every file outside the fact-bound pilot pages must be byte-identical. Each
pilot page is compared as a reader and a crawler see it: visible text, title,
meta description, JSON-LD, headings and links.
"""
import argparse, hashlib, json, os, re, sys, urllib.request
from html.parser import HTMLParser

PILOT = [l.strip() for l in open(os.path.join(os.path.dirname(__file__), "..", "src", "content", "wiki", "PILOT")).read().split()]


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.heads, self.links, self.ld, self.meta = [], [], set(), [], {}
        self.skip = self.inld = 0
        self.htag = None
        self.title = ""
        self.intitle = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script":
            if a.get("type") == "application/ld+json":
                self.inld = 1
            else:
                self.skip += 1
        elif tag == "style":
            self.skip += 1
        elif tag == "title":
            self.intitle = True
        elif tag == "meta" and a.get("content") and (a.get("name") or a.get("property")):
            self.meta[a.get("name") or a.get("property")] = a["content"]
        elif tag == "a" and a.get("href"):
            self.links.add(a["href"])
        elif re.fullmatch(r"h[1-4]", tag):
            self.htag = tag
            self.heads.append([tag, ""])

    def handle_endtag(self, tag):
        if tag == "script":
            if self.inld:
                self.inld = 0
            elif self.skip:
                self.skip -= 1
        elif tag == "style" and self.skip:
            self.skip -= 1
        elif tag == "title":
            self.intitle = False
        elif tag == self.htag:
            self.htag = None

    def handle_data(self, d):
        if self.inld:
            try:
                self.ld.append(json.loads(d))
            except ValueError:
                self.ld.append(d.strip())
            return
        if self.skip:
            return
        if self.intitle:
            self.title += d
        if self.htag:
            self.heads[-1][1] += d
        self.text.append(d)


def parse(html):
    p = Page()
    p.feed(html)
    words = re.sub(r"\s+", " ", " ".join(p.text)).strip()
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", words) if s.strip()]
    return {"title": p.title.strip(), "meta": p.meta, "ld": p.ld, "links": p.links,
            "heads": [(t, re.sub(r"\s+", " ", h).strip()) for t, h in p.heads],
            "words": words.split(), "sents": sents}


def strip_beacon(html):
    return re.sub(r"<!-- Cloudflare Pages Analytics -->.*?<!-- Cloudflare Pages Analytics -->|"
                  r"<script[^>]*src=\"https://static\.cloudflareinsights\.com/beacon\.min\.js[^\"]*\"[^>]*></script>\n?",
                  "", html, flags=re.S)


def files(root):
    out = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not d.startswith(".")]
        for fn in fns:
            if fn == ".git":
                continue
            p = os.path.join(dp, fn)
            out[os.path.relpath(p, root)] = p
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--live")
    ap.add_argument("--out")
    a = ap.parse_args()
    ignore = {"SITE.md", "vercel.json", "wrangler.jsonc", "cg-facts-baseline.json", ".assetsignore",
              ".gitignore", ".vercelignore"}
    ref = {k: v for k, v in files(a.ref).items() if k.split("/")[0] not in ("receipts", "public", "src", "tools", "node_modules", "dist") and k not in ignore}
    new = files(a.new)
    pilot_files = {p + "/index.html" for p in PILOT}
    lines, same, diff = [], 0, []
    for k in sorted(set(ref) | set(new)):
        if k in pilot_files:
            continue
        if k not in new or k not in ref:
            diff.append(f"{'missing in new' if k not in new else 'extra in new'}: {k}")
            continue
        if hashlib.sha256(open(ref[k], "rb").read()).digest() == hashlib.sha256(open(new[k], "rb").read()).digest():
            same += 1
        else:
            diff.append(f"bytes differ: {k}")
    lines.append(f"Pass-through files: {same} byte-identical, {len(diff)} different")
    lines += ["  " + d for d in diff]
    lines.append("")
    lines.append("Fact-bound pilot pages (reference vs Astro):")
    lines.append(f"  {'page':40} {'words':>11} {'sentences kept':>15} {'links':>9} {'headings':>9} title meta jsonld")
    totals = [0, 0, 0, 0]
    detail = {}
    for p in PILOT:
        k = p + "/index.html"
        r = parse(open(ref[k], encoding="utf-8").read())
        n = parse(open(new[k], encoding="utf-8").read())
        kept = sum(1 for s in r["sents"] if s in set(n["sents"]))
        totals[0] += len(r["sents"]); totals[1] += kept
        totals[2] += len(r["words"]); totals[3] += len(n["words"])
        lost = [s for s in r["sents"] if s not in set(n["sents"])]
        added = [s for s in n["sents"] if s not in set(r["sents"])]
        detail[p] = {"lost": lost, "added": added,
                     "links_lost": sorted(r["links"] - n["links"]), "links_added": sorted(n["links"] - r["links"]),
                     "heads_same": r["heads"] == n["heads"]}
        lines.append(f"  /{p+'/':39} {len(r['words']):>5}>{len(n['words']):<5} {kept:>6}/{len(r['sents']):<8} "
                     f"{len(n['links'] & r['links']):>4}/{len(r['links']):<4} {'same' if r['heads'] == n['heads'] else 'DIFF':>9} "
                     f"{'same' if r['title'] == n['title'] else 'DIFF':5} "
                     f"{'same' if r['meta'].get('description') == n['meta'].get('description') else 'DIFF':4} "
                     f"{'same' if r['ld'] == n['ld'] else 'DIFF'}")
    lines.append(f"  TOTAL sentences kept {totals[1]}/{totals[0]} ({totals[1] * 100 // max(totals[0], 1)}%), words {totals[2]} > {totals[3]}")
    if a.live:
        lines.append("")
        lines.append(f"Reference vs live {a.live} (Cloudflare analytics beacon stripped):")
        ok = 0
        for p in PILOT:
            req = urllib.request.Request(f"{a.live}/{p}/", headers={"User-Agent": "cg-wiki-parity/1", "Accept": "text/html"})
            live = strip_beacon(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
            refh = open(ref[p + "/index.html"], encoding="utf-8").read()
            same_live = live == refh
            ok += same_live
            if not same_live:
                lines.append(f"  differs: /{p}/")
        lines.append(f"  {ok}/{len(PILOT)} pilot pages: the reference equals what the live wiki serves today")
    report = "\n".join(lines) + "\n"
    print(report)
    if a.out:
        open(a.out, "w").write(report)
        json.dump(detail, open(a.out.replace(".txt", ".json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
