#!/usr/bin/env bash
# Astro pilot plants: the build must refuse a missing fact id and a figure
# typed into a page, and must drop a person wiped from cg-facts. Each plant
# runs on a scratch copy; the repo is never touched.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0; FAIL=0

run() {  # $1 name, $2 expect (fail|pass), $3 python edit applied in the copy, $4 log pattern
  local dir; dir=$(mktemp -d)
  rsync -a --exclude /dist --exclude /.astro --exclude /.git "$ROOT/" "$dir/"
  ( cd "$dir" && python3 -c "$3" )
  out=$(cd "$dir" && npx astro build 2>&1); rc=$?
  if { [ "$2" = fail ] && [ $rc -ne 0 ]; } || { [ "$2" = pass ] && [ $rc -eq 0 ]; }; then
    if echo "$out" | grep -q "$4"; then PASS=$((PASS+1)); echo "PASS  $1"; echo "      $(echo "$out" | grep -m1 "$4" | sed 's/^ *//' | cut -c1-220)"
    else FAIL=$((FAIL+1)); echo "FAIL  $1: expected log '$4'"; echo "$out" | tail -5; fi
  else FAIL=$((FAIL+1)); echo "FAIL  $1: rc=$rc"; echo "$out" | tail -5; fi
  rm -rf "$dir"
}

EDIT_ENTRY='import json,sys
p="src/content/wiki/work--lief-midtown-301-osborn.json"; e=json.load(open(p))
e["body"]=e["body"].replace("{{fact:301-osborn.usd-3-85m}}", REPL, 1)
json.dump(e,open(p,"w"))'

run "clean build" pass "pass" "Complete!"
run "plant: missing fact id" fail "REPL='{{fact:301-osborn.usd-9-99m}}'
$EDIT_ENTRY" 'cites fact "301-osborn.usd-9-99m"'
run "plant: hand-typed figure" fail "REPL='\$3.85M'
$EDIT_ENTRY" "typed into the page"
run "plant: hand-typed count" fail 'import json
p="src/content/wiki/jesse-fowler.json"; e=json.load(open(p))
e["body"]=e["body"].replace("<h2>Overview</h2>", "<h2>Overview</h2><p>More than 450 projects.</p>", 1)
json.dump(e,open(p,"w"))' "typed into the page"
# A partner wiped from cg-facts: their facts leave the export, their page is
# not built, and a page still citing one of their facts fails. Mentions in
# plain text are the publish gate's job (WIPED-PERSON).
WIPE='import json
p="src/data/cg-facts/registry.json"; r=json.load(open(p))
r={k:v for k,v in r.items() if v["subject"]!="robbie-prochnow"}
json.dump(r,open(p,"w"))'
run "plant: wiped partner, page dropped" pass "$WIPE" "robert-prochnow/ not built"
run "plant: wiped partner, fact still cited" fail "$WIPE
import json
p='src/content/wiki/zen-aegis.json'; e=json.load(open(p))
e['body']=e['body'].replace('<h2>', '<p>{{fact:robbie-prochnow.usd-20m}}</p><h2>', 1)
json.dump(e,open(p,'w'))" 'cites fact "robbie-prochnow.usd-20m"' 
echo "pilot plants: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
