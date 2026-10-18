"""Load test on the server itself, straight to nginx (no ArvanCloud): how many requests a second the
origin can serve, per kind of request, as simultaneous clients rise. Standard library only.
    python3 origin.py html 1,2,4,8 15
    python3 origin.py glb 1,2,4 15
The load generator shares the one CPU with the site, so the numbers are a floor, not a ceiling."""
import http.client
import sys
import threading
import time

KIND, STAGES, SECS = sys.argv[1], [int(n) for n in sys.argv[2].split(',')], float(sys.argv[3])
PATHS = {'html': ['/', '/', '/', '/checkout/', '/orders/'], 'glb': ['/models/alpha-mobile.glb']}[KIND]
HEADERS = {'Host': 'shop.nisatech.org', 'X-Forwarded-Proto': 'https', 'Accept-Encoding': 'gzip',
           'User-Agent': 'purseshop-loadtest/1 (Nisatech, origin)'}


def client(stats, until, lock):
    conn = http.client.HTTPConnection('127.0.0.1', 80, timeout=20)
    i = 0
    while time.time() < until:
        path = PATHS[i % len(PATHS)]
        i += 1
        t0 = time.perf_counter()
        try:
            conn.request('GET', path, headers=HEADERS)
            res = conn.getresponse()
            body = res.read()
            ms = (time.perf_counter() - t0) * 1000
            with lock:
                stats['lat'].append(ms) if res.status < 400 else None
                stats['err'] += res.status >= 400
                stats['bytes'] += len(body)
        except Exception:
            with lock:
                stats['err'] += 1
            conn.close()
            conn = http.client.HTTPConnection('127.0.0.1', 80, timeout=20)


print(f'{KIND}: users  req/s  p50ms  p95ms  maxms  errors  MB/s')
for users in STAGES:
    stats, lock = {'lat': [], 'err': 0, 'bytes': 0}, threading.Lock()
    until = time.time() + SECS
    t0 = time.perf_counter()
    threads = [threading.Thread(target=client, args=(stats, until, lock)) for _ in range(users)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    secs = time.perf_counter() - t0
    lat = sorted(stats['lat'])
    q = lambda p: lat[min(len(lat) - 1, int(len(lat) * p))] if lat else 0
    print(f'{time.strftime("%H:%M:%S")} {users:5} {(len(lat) + stats["err"]) / secs:6.1f} {q(.5):6.0f} {q(.95):6.0f}'
          f' {(lat[-1] if lat else 0):6.0f} {stats["err"]:7} {stats["bytes"] / secs / 1e6:5.2f}', flush=True)
    if stats['err'] > 5 or q(.95) > 4000:
        print('stopping')
        break
