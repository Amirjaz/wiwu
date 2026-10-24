# PurseShop: load test, 2026-10-18 (and the shop's own server, 2026-10-24)

**The shop's own server, 2026-10-24** (its section below): on 4 cores, as it runs now (9 plain gunicorn
workers, no gunicorn access log), the page cache serves the home page about 850 times a second and
checkout renders about 190 times a second, with no errors up to 128 simultaneous clients. That is far beyond the campaign estimates further
down (6–12 views a second at a spike). The 2026-10-18 test of the old shared server follows.

**Question:** can the store take about 500 buyers a day, around 50,000 page views or more, and on what
server?

**Short answer:** the current server handles that volume on an ordinary day. A sudden spike would fill
its one CPU and slow every site on it. That's a big rush, for example a popular Instagram post sending
more than about 18 visitors a second for a few minutes. Three changes give it plenty of room; one is
already in the code (the page cache), and two need Amir or the server admin (below).

## The server

The store shares the Nisatech server with nisatech.org, nisatak.com and contech:

- **CPU and memory:** 1 vCPU (an older Xeon) and 1 GB RAM, with about 0.5 GB of swap already in use.
- **Load:** almost idle before the test (load average 0.05).
- **App:** gunicorn with 3 workers, behind nginx, with ArvanCloud in front.

## What was run

Both ran live, during the day (2026-10-18, about 10:14–10:20 UTC), at Amir's request.

1. **Through ArvanCloud, from the office PC** (`tools/loadtest/ramp.mjs`). The mix was 70% home page,
   15% checkout, 10% order lookup and 5% a policy page. Each simultaneous visitor makes requests
   back to back with no pause, in 30-second steps, ramping up. The test stops itself at the first errors.
2. **On the server, straight to nginx** (`tools/loadtest/origin.py`). This finds the ceiling for pages
   and for the 3D model. The load tool runs on the same CPU, so these numbers are a floor.

During both, `tools/loadtest/monitor.sh` logged two things every 5 s: the server's CPU and memory, and
how fast the other three sites answered.

## Results

**Through ArvanCloud** (limited by the office VPN, about 360 KB/s; the errors were dropped connections
on the PC side, not server errors):

| Simultaneous visitors | Requests/s | Median | 95% under | Server CPU |
| --- | --- | --- | --- | --- |
| 1 | 1.3 | 0.72 s | 1.05 s | ~10% |
| 2 | 2.9 | 0.65 s | 0.79 s | ~15% |
| 10 | 10.8 | 0.66 s | 0.89 s | 45–60% |

Response times stayed flat; most of the 0.65 s is the network between the PC and Arvan.

**On the server** (no network in the way):

| Request | Max/s | Median at max | CPU per request |
| --- | --- | --- | --- |
| A page (home, checkout, lookup) | ~36 | 26 ms with 1 client, queueing above | ~26 ms |
| The phone 3D model (311 KB), gzipped by nginx | ~35 | 26 ms with 1 client | ~28 ms |

- **At full load:** the CPU was at 100%, and the server returned no errors.
- **Memory:** didn't change.
- **The other sites:** went from about 1 ms to about 0.2 s while the CPU was full.

## What 50,000 views a day means

| | Views/s |
| --- | --- |
| Average over the day | 0.6 |
| A busy evening hour (about 10% of the day) | 1.4 |
| A campaign spike (10–20× the average for a few minutes) | 6–12 |

- **One visit costs about 55 ms of CPU:** the page (26 ms) plus the 3D model (28 ms). That's because
  ArvanCloud doesn't cache the model today (`x-cache: BYPASS`).
- **At that cost, the one CPU tops out at about 18 visits/s.** That's enough for the average and a busy
  hour, and tight for a spike.
- **Traffic:** the model alone would also send about 13 GB a day from the server.

## Fixes, in order

1. **Cache the rendered pages** *(done in code, deployed with the next deploy).* The home and policy
   pages are kept for 60 s (`shop/pagecache.py`), and cleared whenever the product, colours, settings,
   cards, FAQ or pages change. That takes a page from about 26 ms of CPU to about 2 ms, so pages stop
   being the limit (an estimated 150+ a second).
2. **Have ArvanCloud cache `/models/`** *(Amir, in the Arvan panel for nisatech.org).* Add a caching
   rule for the path `/models/*`, cache everything, 7 days. Then check that `x-cache` reads `HIT` on
   the second request. The model then never reaches the server again: about 28 ms of CPU and 0.3 MB less
   per visit.
3. **Stop nginx gzipping the model** *(the server admin re-runs
   `sudo DOMAIN=penolinshop.com REDIRECT="www.penolinshop.com shop.nisatech.org" PANEL="panel.penolinshop.com" bash /home/amir/purseshop-deploy/server-setup.sh` after a fresh
   `scp -r deploy`).* `deploy/nginx/purseshop.conf` no longer lists it. Gzip saved only 18% for
   ~28 ms of CPU each time. This matters less once (2) is done, but it's free.

With 1 and 2, the shared server should take several times the expected spike. Re-run the tests after
the next deploy to confirm (below).

**For the real launch on the client's domain:** if the budget allows, give the store its own small
server, 2 vCPU and 2 GB RAM, in an Iranian datacentre, behind ArvanCloud. Then a rush on the store
can't slow nisatech.org, nisatak.com or contech, and vice versa. With the fixes above it isn't
required for 50,000 views a day.

## The shop's own server, 2026-10-24

37.32.25.183: Arvan cloud, 4 vCPU, 4 GB RAM, 2 GB swap, nothing else on it. Measured on the server with
`tools/loadtest/bench.sh` (ApacheBench straight at a gunicorn port, no nginx or Arvan; one new connection
per request, as nginx makes them; 15 s per step), during the day with the site live and quiet. The live
service was measured as it was; each other setup ran as a second gunicorn on port 8031 beside it, as the
service's user, so the site wasn't touched until the choice was made. ab itself takes part of a core, so
these are a floor. Peaks over 1–128 simultaneous clients, and the 95th percentile at 64:

| gunicorn | Access log | Home (page cache), req/s | p95 at 64 | Checkout (rendered), req/s | p95 at 64 | Memory |
| --- | --- | --- | --- | --- | --- | --- |
| 3 sync workers (as it was, live) | on | ~800 | 109 ms | ~170 | 445 ms | ~170 MB |
| 9 sync (live, first install) | on | ~690–760 | 96 ms | ~157–166 | 425 ms | ~450 MB |
| **9 sync (live, as it runs now)** | **off** | ~830–860 | 86 ms | ~178–199 | 373 ms | ~450 MB |
| 5 sync (beside it) | off | ~1,070 | 72 ms | ~228 | 328 ms | ~270 MB |
| 9 sync (beside it) | off | ~880–920 | 90 ms | ~180–210 | 375 ms | ~440 MB |
| 4 workers × 4 threads, gthread (beside it) | off | ~510 | 407 ms | ~122 | 1,006 ms | ~230 MB |
| 8 workers × 4 threads, gthread (beside it) | off | ~530 | 265 ms | ~141 | 1,204 ms | ~450 MB |

**Mind the access log:** the live service wrote every request to the journal (`--access-logfile -`); the
setups run beside it didn't. At full CPU that log cost about 15–20% (journald's share), so compare rows
with the same log setting. Like for like, 9 workers serve about as many requests at full CPU as 3 did:
the CPU, not the number of workers, is the limit there. nginx already logs every request, so gunicorn's
own access log went (2026-10-24, Amir's go-ahead), and the live service matched the run beside it.

- **No errors** in any run; the CPU was full (90–100%) from 8 clients up with 5 or more workers.
- **Threads are slower here:** a page is rendered in Python start to finish, and Python's threads queue for
  one lock, so 4 or 8 threaded workers did about half the work of 5 plain ones, with much worse waits.
- **Why 9 workers:** not for speed at full CPU (see above) but for waiting. A checkout can wait up to
  20 s on cartbecart (`payments.TIMEOUT`, two calls) and an OTP up to 10 s on Kavenegar, and a plain worker
  does nothing else meanwhile: with 3, three buyers waiting on cartbecart held up every page; with 9 it
  takes nine. 5 was the fastest beside it, about 15% ahead of 9 at full CPU, a margin no expected spike
  comes near.
- **Per visit** the home page now costs about 1 ms of CPU from the cache and checkout about 5 ms (4 cores
  at ~200/s). Through Arvan, images are cached at the edge and the 3D model is gone (2026-10-23).

## Running it again

From `PurseShop/` (dev tools only; the scripts send a `purseshop-loadtest` user agent):

On the shop's own server (needs `apt-get install apache2-utils`; `bash bench.sh <port> <label> [clients]`):

```bash
scp tools/loadtest/bench.sh root@37.32.25.183:
ssh root@37.32.25.183 'bash bench.sh 8030 live "1 8 32 64 128"'
```

The 2026-10-18 tools (`origin.py` is one Python process, which runs out of steam before a 4-core server
does; `monitor.sh` also times the other sites of the old shared server):

```bash
node tools/loadtest/ramp.mjs https://penolinshop.com '[1,2,5,10,20,40]' 30
scp tools/loadtest/origin.py tools/loadtest/monitor.sh amir@37.32.25.183:
ssh amir@37.32.25.183 'nohup bash monitor.sh 140 > monitor.log 2>&1 & python3 origin.py html 1,2,4,8 15; python3 origin.py glb 1,2,4 15'
```

Run them when a short slowdown of the other sites is acceptable. `ramp.mjs` stops at 5+ errors over
2%, a 95th percentile over 4 s, or any 403/429/503 from Arvan.
