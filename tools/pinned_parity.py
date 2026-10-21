#!/usr/bin/env python3
"""http_parity with each side pinned to an IP: <host> <ipA> <ipB> <paths>. Same fields as http_parity.py."""
import re, hashlib, http.client, socket, ssl, sys, urllib.parse
KEYS = ('content-type', 'x-robots-tag', 'cache-control', 'x-frame-options')
class Pinned(http.client.HTTPSConnection):
    def __init__(self, host, ip):
        super().__init__(host, timeout=20, context=ssl.create_default_context()); self.ip = ip
    def connect(self):
        s = socket.create_connection((self.ip, 443), self.timeout)
        self.sock = self._context.wrap_socket(s, server_hostname=self.host)
def fetch(host, ip, path, method='GET'):
    c = Pinned(host, ip); c.request(method, path, headers={'User-Agent': 'cg-migration-parity/1'})
    r = c.getresponse(); body = re.sub(rb"<script type=\"module\" src=\"https://static.cloudflareinsights.com/beacon[^\n]*?</script>\n?", b"", r.read()); h = {k.lower(): v for k, v in r.getheaders()}
    loc = h.get('location', '')
    if loc.startswith('http'): loc = urllib.parse.urlsplit(loc)._replace(scheme='', netloc='').geturl()
    return {'status': r.status, 'location': loc, 'sha1': hashlib.sha1(body).hexdigest()[:12] if r.status == 200 else '-',
            **{k: h.get(k, '').split(';')[0].strip() if k == 'content-type' else h.get(k, '') for k in KEYS}}
host, ia, ib, pf = sys.argv[1:5]
paths = [p.strip() for p in open(pf) if p.strip() and not p.startswith('#')]
bad = 0
for p in paths:
    m, _, rest = p.partition(' '); m, path = (m, rest) if rest else ('GET', p)
    ra, rb = fetch(host, ia, path, m), fetch(host, ib, path, m)
    d = [k for k in ra if ra[k] != rb[k]]
    if d: bad += 1; print('DIFF', p, {k: (ra[k], rb[k]) for k in d})
    else: print('ok  ', p, ra['status'], ra['location'] or ra['sha1'])
print(f'{len(paths) - bad} of {len(paths)} paths identical'); sys.exit(1 if bad else 0)
