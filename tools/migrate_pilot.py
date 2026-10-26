#!/usr/bin/env python3
"""One-time migration of the wiki pilot pages into fact-bound Astro entries.

For each pilot page of the live wiki:
  - every figure (dollar amount, percent, number + counted noun) becomes a
    token {{fact:ID}} bound to a cg-facts fact, when a public CANON or
    DOCUMENTED row about the page's subject prints that same figure;
  - a figure with no such row, or a retired one, is not printed: the sentence
    that carries it is cut, and the cut is logged for review;
  - person pages lose their hand-written header block; the Astro page renders
    it from cg-facts (name, public title, function line, short bio).

Writes:
  <out>/entries/<slug>.json      Astro content entries (head + body, tokenized)
  <out>/facts/<subject>.yaml     facts to add to cg-facts (each with its rows)
  <out>/report.json              bound and cut figures per page

    python3 migrate_pilot.py --wiki <cg-wiki checkout> --facts <cg-facts> --out <dir>
"""
from __future__ import annotations

import argparse
import glob
import html
import json
import os
import re
import unicodedata

import yaml

PILOT = [
    # wiki path, kind, subject (cg-facts slug), subject row scope
    ("jesse-fowler", "person", "jesse-fowler", {"partners": ["JF", "CG"]}),
    ("alex-prince", "person", "alex-prince", {"partners": ["AP", "CG"]}),
    ("jimmy-khounlavong", "person", "jimmy-khounlavong", {"partners": ["JK", "CG"]}),
    ("nick-scavio", "person", "nick-scavio", {"partners": ["NS", "CG"]}),
    ("robert-prochnow", "person", "robbie-prochnow", {"partners": ["RP", "CG"]}),
    ("work/lief-midtown-301-osborn", "project", "301-osborn", {"prefixes": ["JF-LIEF", "JK-LIEF", "CG-LIEF"], "names": ["Osborn", "Midtown"]}),
    ("work/fluidmapper", "project", "fluidmapper", {"prefixes": ["CG-FLU"], "names": ["Fluidmapper"]}),
    ("work/ghana-community", "project", "ghana", {"names": ["Ghana"]}),
    ("drive-for-the-dream", "project", "drive-for-the-dream", {"names": ["Drive for the Dream"]}),
    ("work/greensleeves-steakhouse", "project", "greensleeves", {"names": ["Greensleeves"]}),
    ("work/kanopi-estimating-engine", "project", "kanopi", {"prefixes": ["JF-KAN"], "names": ["Kanopi"]}),
    ("tellus-design-build", "project", "tellus", {"prefixes": ["JF-TEL"], "names": ["Tellus"]}),
    ("work/the-triangle-grand-avenue", "project", "triangle", {"names": ["Triangle"]}),
    ("xtrata", "project", "xtrata", {"prefixes": ["JF-STR"], "names": ["Xtrata", "Strata"]}),
    ("zen-aegis", "project", "zen-aegis", {"names": ["Zen Aegis"]}),
    ("work/alice-mushrooms", "project", "alice-mushrooms", {"names": ["Alice"]}),
]

NOUNS = (r"projects?|years?|homes|condominiums|stores|doors|people|employees|clients|units|"
         r"pages|rooms|sites|agents|tools|skills|elements|citations|findings|cities|countries|"
         r"states|offices|practices|locations|deals|companies|brands|SKUs|styles|accounts|"
         r"athletes|events|markets|parking stalls|stalls|SF|square feet|days|weeks|months|hours|"
         r"percent|times|stars|reviews|members|partners|properties|buildings|acres|beds|keys|"
         r"miles|students|kids|families|volunteers|teams|leagues|games|jobs|trades|subcontractors|"
         r"bids|sheets|drawings|line items|items|workflows|apps|users|visits|views|followers")
NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
FIG = re.compile(
    r"\$\s?" + NUM + r"(?:\s?(?:K|M|B|MM)\b|\s(?:thousand|million|billion)\b)?(?:\+|-plus)?"
    r"|\b" + NUM + r"\s?%"
    r"|\b" + NUM + r"\+?\s+(?:" + NOUNS + r")\b")
YEARISH = re.compile(r"^(?:19|20)\d\d\s")
# A sentence never crosses a structural tag; only inline formatting can sit inside one.
INLINE = r"(?:strong|em|b|i|u|sup|sub|small|abbr|code|mark|q|cite|time|wbr)"
BLOCK_OPEN = re.compile(r"<(?!/)(?!" + INLINE + r"\b)[a-zA-Z][^>]*>|</(?!" + INLINE + r"\b)[a-zA-Z][^>]*>")
BLOCK_CLOSE = BLOCK_OPEN


STOP = {"Common", "Ground", "Jesse", "Fowler", "The", "This", "That", "Their", "There", "With",
        "After", "Before", "Over", "Built", "Today", "When", "From", "Into", "About", "Each",
        "Every", "Most", "More", "Than", "Then", "They", "What", "Where", "Which", "While",
        "Development", "Construction", "Operating", "Brand", "Technology", "Capital"}
WSTOP = {"about", "after", "before", "their", "there", "which", "while", "where", "other", "these",
         "those", "being", "every", "first", "built", "years", "projects", "common", "ground",
         "jesse", "fowler", "would", "could", "should", "under", "through", "across", "within",
         "without", "since", "until", "still", "against", "between", "around", "percent", "million"}
CITE = re.compile(r"\[[A-Z]{1,3}\d{1,3}\]")


# Proposed copy: a retired figure replaced by the figure cg-facts approves, from
# the same source row. Preview only; each needs Jesse's go before any cutover.
TEL = ("over $300M of built work, and did about $480M in business across its 19 years",
       "more than $400M of built work across its 19 years",
       "Retired $300M and $480M (cg-facts RET-001, RET-005); JF-TEL-02 carries $400M+ built.")
REWRITES = {
    "jesse-fowler": [TEL],
    "tellus-design-build": [(
        "over $300M of built work, and did about $480M in business across",
        "more than $400M of built work across",
        "Retired $300M and $480M (cg-facts RET-001, RET-005); JF-TEL-02 carries $400M+ built.")],
    "jimmy-khounlavong": [
        ("a $1.2B-plus lifestyle business", "a $1B-plus lifestyle business",
         "Retired $1.2B (cg-facts RET-002: use $1B+)."),
        ("a $1.2B+ lifestyle business", "a $1B+ lifestyle business",
         "Retired $1.2B (cg-facts RET-002: use $1B+)."),
    ],
}


def fold(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def slug(s):
    s = fold(s).lower().replace("$", "usd-").replace("%", "-pct").replace("+", "-plus")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


_DOL = re.compile(r"\$\s?((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s?(k|m|b|mm|thousand|million|billion)?\b", re.I)
_MULT = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mm": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}


def _canon_dollar(m):
    v = float(m.group(1).replace(",", "")) * _MULT.get((m.group(2) or "").lower(), 1)
    for unit, size in (("b", 1e9), ("m", 1e6), ("k", 1e3)):
        if v >= size and abs(round(v / size, 3) * size - v) < 0.5:
            return "$%s%s" % (("%.3f" % (v / size)).rstrip("0").rstrip("."), unit)
    return "$%s" % (("%.2f" % v).rstrip("0").rstrip("."))


def norm_fig(s):
    """One spelling per figure: $30 million = $30M, $75,000 = $75K, 92.8 percent = 92.8%."""
    s = html.unescape(s).replace("-plus", "+").replace(" ", " ").replace("~", "")
    s = _DOL.sub(_canon_dollar, s)
    s = re.sub(r"(\d)\s?percent\b", r"\1%", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip().lower()


def figure_regex(fig):
    """Match a figure in row text whatever its plus sign: "400 projects" is
    sourced by "400+ projects", "$1B+" by "$1B-plus"."""
    n = norm_fig(fig).replace("-plus", "").replace("+", "")
    m = re.match(r"(\$?\s?[\d,.]+(?:\s?(?:k|m|b|mm)\b|\s(?:thousand|million|billion)\b)?)(.*)$", n)
    num, rest = (m.group(1), m.group(2)) if m else (n, "")
    pat = re.escape(num).replace(r"\ ", r"\s?") + r"(?:\+|-plus)?" + re.escape(rest).replace(r"\ ", r"\s?")
    return re.compile(r"(?<![\d.,$])" + pat + r"(?![\d])", re.I)


class Rows:
    def __init__(self, facts_repo):
        self.rows = []
        for p in glob.glob(os.path.join(facts_repo, "rows", "*.json")):
            r = json.load(open(p))
            if r.get("status") in ("CANON", "DOCUMENTED") and r.get("public") is not False:
                r["_blob"] = norm_fig(" ".join(str(r.get(k, "")) for k in ("headline", "numbers", "phrasing", "story")))
                r["_meta"] = " ".join(str(r.get(k, "")) for k in ("headline", "entity", "era", "story"))
                self.rows.append(r)
        self.retired = [re.compile(e["pattern"]) for e in yaml.safe_load(
            open(os.path.join(facts_repo, "tools", "retired-figures.yaml")))]

    def in_scope(self, r, scope):
        if r["partner"] in scope.get("partners", []):
            return True
        if any(r["id"].startswith(p + "-") for p in scope.get("prefixes", [])):
            return True
        return any(n in r["_meta"] for n in scope.get("names", []))

    def source(self, fig, scope, sentence=""):
        """Public rows printing this figure that are about this claim: the row is
        in the page subject's scope, or it shares a proper noun with the sentence."""
        rx = figure_regex(fig)
        names = {w for w in re.findall(r"\b[A-Z][A-Za-z0-9&'.-]{3,}\b", sentence) if w not in STOP}
        words = {w for w in re.findall(r"[a-z][a-z-]{4,}", sentence.lower()) if w not in WSTOP}
        out = []
        for r in self.rows:
            if not rx.search(r["_blob"]):
                continue
            shared = words & set(re.findall(r"[a-z][a-z-]{4,}", r["_meta"].lower()))
            if self.in_scope(r, scope) or any(n in r["_meta"] for n in names) or len(shared) >= 2:
                out.append(r["id"])
        return sorted(out)

    def is_retired(self, fig):
        return any(rx.search(fig) for rx in self.retired)


def context(doc, pos):
    """'json' inside a JSON-LD script, 'attr' inside a tag, else 'text'."""
    s_open = doc.rfind('<script type="application/ld+json">', 0, pos)
    s_close = doc.rfind("</script>", 0, pos)
    if s_open > s_close:
        return "json"
    if doc.rfind("<", 0, pos) > doc.rfind(">", 0, pos):
        return "attr"
    return "text"


def tags_balanced(seg):
    stack = []
    for m in re.finditer(r"<(/?)([a-zA-Z0-9]+)[^>]*?(/?)>", seg):
        close, name, selfclose = m.group(1), m.group(2).lower(), m.group(3)
        if selfclose or name in ("br", "img", "meta", "link", "hr", "wbr"):
            continue
        if close:
            if not stack or stack[-1] != name:
                return False
            stack.pop()
        else:
            stack.append(name)
    return not stack


SENT_END = re.compile(r"(?<!\d)[.!?](?=\s|<|\"|$)|(?<=\d)[.!?](?=\s+[A-Z<]|<|\"|$)")


def cut_span(doc, pos, end, ctx):
    """Bounds of the sentence holding doc[pos:end] in its context."""
    if ctx == "text":
        lo_lim = max([m.end() for m in BLOCK_OPEN.finditer(doc, 0, pos)] or [0])
        m = BLOCK_CLOSE.search(doc, end)
        hi_lim = m.start() if m else len(doc)
    elif ctx == "attr":
        lo_lim = doc.rfind('"', 0, pos) + 1
        hi_lim = doc.find('"', end)
    else:
        lo_lim = doc.rfind('"', 0, pos) + 1
        hi_lim = doc.find('"', end)
        while doc[hi_lim - 1] == "\\":
            hi_lim = doc.find('"', hi_lim + 1)
    lo = lo_lim
    for m in SENT_END.finditer(doc, lo_lim, pos):
        lo = m.end()
    m = SENT_END.search(doc, end, hi_lim)
    hi = m.end() if m else hi_lim
    seg = doc[lo:hi]
    if ctx == "text" and not tags_balanced(seg):
        # The sentence crosses a tag boundary: take the whole block instead.
        lo, hi = lo_lim, hi_lim
        seg = doc[lo:hi]
        if not tags_balanced(seg):
            return None
    return lo, hi


def tokenize(doc, rows, scope, subject, facts, report):
    out, i = [], 0
    while True:
        changed = False
        for m in FIG.finditer(doc):
            raw = m.group(0)
            if YEARISH.match(raw) and not raw.startswith("$"):
                continue
            if doc[max(0, m.start() - 12):m.start()].endswith(("{{fact:", "{{fact-json:", "{{cited:")):
                continue
            ctx = context(doc, m.start())
            fig = html.unescape(raw).strip()
            span = cut_span(doc, m.start(), m.end(), ctx)
            sentence = html.unescape(re.sub(r"<[^>]+>", "", doc[span[0]:span[1]])) if span else ""
            if ctx == "text" and not rows.is_retired(fig):
                lo = max([b.end() for b in BLOCK_OPEN.finditer(doc, 0, m.start())] or [0])
                b = BLOCK_CLOSE.search(doc, m.end())
                if CITE.search(doc[lo:b.start() if b else len(doc)]):
                    # A third-party figure cited to a listed source on the page.
                    doc = doc[:m.start()] + "{{cited:%s}}" % raw + doc[m.end():]
                    report["cited"].append({"figure": fig, "sentence": re.sub(r"\s+", " ", sentence).strip()[:160]})
                    changed = True
                    break
            src = [] if rows.is_retired(fig) else rows.source(fig, scope, sentence)
            if src:
                fid = f"{subject}.{slug(fig)}"
                facts.setdefault(fid, {"id": fid, "value": fig, "rows": src[:3]})
                tok = "{{fact-json:%s}}" % fid if ctx == "json" else "{{fact:%s}}" % fid
                doc = doc[:m.start()] + tok + doc[m.end():]
                report["bound"].append({"figure": fig, "fact": fid, "rows": src[:3], "where": ctx})
            else:
                if not span:
                    report["unresolved"].append({"figure": fig, "where": ctx})
                    doc = doc[:m.start()] + "{{fact:UNRESOLVED." + slug(fig) + "}}" + doc[m.end():]
                else:
                    lo, hi = span
                    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", doc[lo:hi]))).strip()
                    report["cut"].append({"figure": fig, "why": "retired" if rows.is_retired(fig) else "no public row",
                                          "where": ctx, "sentence": text})
                    doc = doc[:lo] + doc[hi:]
            changed = True
            break
        if not changed:
            return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wiki", required=True)
    ap.add_argument("--facts", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = Rows(a.facts)
    os.makedirs(os.path.join(a.out, "entries"), exist_ok=True)
    os.makedirs(os.path.join(a.out, "facts"), exist_ok=True)
    reports, all_facts = {}, {}
    for path, kind, subject, scope in PILOT:
        t = open(os.path.join(a.wiki, path, "index.html"), encoding="utf-8").read()
        head = t[t.index("<head>") + 6:t.index("</head>")]
        body = t[t.index('<body class="cg-theme">') + len('<body class="cg-theme">'):t.index("<footer")]
        if kind == "person":
            body = re.sub(r'<section class="page-header">.*?</section>', "<!--person-hero-->", body, count=1, flags=re.S)
        rep = {"bound": [], "cut": [], "cited": [], "rewritten": [], "unresolved": []}
        for old_text, new_text, why in REWRITES.get(path, []):
            n = head.count(old_text) + body.count(old_text)
            if not n:
                raise SystemExit(f"{path}: rewrite target not found: {old_text[:60]}")
            head, body = head.replace(old_text, new_text), body.replace(old_text, new_text)
            rep["rewritten"].append({"from": old_text, "to": new_text, "why": why, "count": n})
        facts = all_facts.setdefault(subject, {})
        head = tokenize(head, rows, scope, subject, facts, rep)
        body = tokenize(body, rows, scope, subject, facts, rep)
        entry = {"path": path, "kind": kind, "subject": subject, "head": head.strip("\n"), "body": body.strip("\n")}
        with open(os.path.join(a.out, "entries", path.replace("/", "--") + ".json"), "w") as f:
            json.dump(entry, f, indent=1, ensure_ascii=False)
        reports[path] = rep
        print(f"{path}: bound {len(rep['bound'])}, cut {len(rep['cut'])}, unresolved {len(rep['unresolved'])}")
    for subject, facts in all_facts.items():
        if not facts:
            continue
        with open(os.path.join(a.out, "facts", subject + ".yaml"), "w") as f:
            f.write("# Facts the wiki prints for this subject. Each cites the public rows that\n"
                    "# carry the same figure. Added by the Astro wiki pilot migration 2026-10-26.\n")
            yaml.safe_dump({"subject": subject, "facts": sorted(facts.values(), key=lambda x: x["id"])},
                           f, sort_keys=False, allow_unicode=True, width=1000)
    json.dump(reports, open(os.path.join(a.out, "report.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
