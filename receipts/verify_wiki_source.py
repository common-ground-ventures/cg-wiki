"""Fail if a rebuild or a direct target edit differs from the reviewed source manifest."""
from pathlib import Path
import argparse,hashlib,json,subprocess

def verify(root,manifest,tracked=False):
    root=Path(root);m=json.loads(Path(manifest).read_text(encoding='utf-8'));expected=m['files'];errors=[]
    for rel,wanted in expected.items():
        p=root/rel
        if not p.is_file():errors.append('missing: '+rel)
        elif hashlib.sha256(p.read_bytes()).hexdigest()!=wanted:errors.append('changed: '+rel)
    if tracked:
        paths=subprocess.check_output(['git','-C',str(root),'ls-files','-z']).decode().split('\0')
        ignored=lambda s:s in {'SITE.md','.gitignore'} or s.startswith(('receipts/','.github/'))
        for rel in paths:
            if rel and rel not in expected and not ignored(rel):errors.append('unmanaged: '+rel)
    else:
        for p in root.rglob('*'):
            if p.is_file() and p.relative_to(root).as_posix() not in expected:errors.append('extra: '+p.relative_to(root).as_posix())
    return errors
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('manifest');p.add_argument('--tracked',action='store_true');a=p.parse_args();errors=verify(a.root,a.manifest,a.tracked)
    if errors:raise SystemExit('\n'.join(errors))
    print('PASS: every managed file matches the source manifest')
