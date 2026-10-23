# PurseShop: handoff

State on **2026-10-23 (1 Aban 1405)**, written so the work can go on in a new chat.

**A new chat should start here:** read this page, then [README.md](README.md) for how everything works,
[PLAN.md](PLAN.md) for the decisions and risks, and [LOADTEST.md](LOADTEST.md) for the server capacity.
This page is the short version, plus what isn't written down anywhere else.

## Where it stands

- **Staging is online at https://shop.nisatech.org** and runs **6d8de65**, deployed on 2026-10-23 (`main`
  is the same; the handoff commits after it change only this file): the client's answers (the shop is
  **ویوو** with WiWU's logo in the site's colours, the price, free post and Tipax on delivery, 4 to 6
  working days, the battery, the 72-hour warranty), the hero (opening with the man with the bag for 3 s,
  sharp on laptops, colour dots that jump to their poster), black and brown only (no silver), a picture
  of each bag in جزء به جزء instead of the 3D bag, the two-zipper bag at 16,500,000 toman with its own
  section, a pick-a-colour closing section, WiWU's coffee brown.
  - Open to everyone (no password, Amir's choice), but kept out of search engines (noindex).
  - SMS codes only go to the server log and payments are manual, so people can browse but can't finish
    an order. No orders yet.
  - Plain http redirects to https.
  - **HTTPS on the server itself** (2026-10-20): Arvan's proxy was off for every nisatech.org record, so
    browsers came straight to the server, and nginx answered https://shop.nisatech.org with nisatak.com
    (its only HTTPS site). The shop now has its own Let's Encrypt certificate (until 2027-01-18,
    certbot.timer renews it and reloads nginx) and works with the proxy on or off. Each deploy checks it
    (`remote-deploy.sh`; it passed on the 2026-10-21 deploys). Amir turned the proxy back on by
    2026-10-21 (the shop resolves to Arvan again, `server: ArvanCloud`).
  - **Panel accounts:** `amir` and `salar`, both superusers (Amir set the passwords himself on
    2026-10-19). Log in at `/panel/` (the store) or `/admin/` (Django, for the Owners/Staff groups).
- **The bag:** the WiWU Alpha fingerprint-lock clutch, sold as **«کیف دستی ویوو آلفا»** (WiWU as the
  brand in the specs and the search data), in **black and brown** (no silver: the client doesn't have
  it, 2026-10-21), both on sale at one price: **14,100,000 toman**, shipping from Dubai included (the client, 2026-10-20).
- **A second model:** WiWU's two-zipper **Phantom Pro** in black and brown, **16,500,000 toman** (Amir,
  2026-10-21 and 23; README, *The two-zipper model*): its pictures in جزء به جزء, its own section, checkout
  and orders. The panel (فروشگاه) has a switch at the top for which model the colours and fields are for.
- **The home page, top to bottom** (README, *Look* and *The hero and the 3D bag*):
  1. **Hero:** a campaign page. Five pictures over the whole first screen, one at a time: Amir's photo
     of the man with the bag first, for 3 s (2026-10-21), then posters of the bag alone, all turned the
     same way (black, black and brown side by side as mirror images, his plate photo, brown), with a large line, the
     price and a compact buy button at the bottom; no thumbnails (2026-10-20). The header lies over it,
     see-through. Colour dots.
  2. **جزء به جزء:** a picture of each bag (Alpha black and brown, two-zipper black and brown), each with its
     price and opening its checkout, the Alpha's parts listed beside them with a tab per side. The 3D bag
     was here until 2026-10-23 (Amir: pictures instead); its code stays, unused (README).
  3. **The lock** (dark), the hold-to-unlock demo; **specs** with the size drawn over a centimetre mat;
     **buying** with the sample bill; **FAQ**; **pick a colour** (the bags side by side, each opening
     checkout in its colour; it replaced the green band); the footer.
- **Store features:** checkout with an SMS code, card-to-card payment with a unique amount per order,
  "I've paid" review, the payment timer, shipping, returns, staff panel, SMS templates, SEO, colours
  (each with a photo shown at checkout), a page cache.
- **Checks:** `manage.py test shop` runs 47 tests and they pass; `npx tsc --noEmit` and `npm run build`
  pass; desktop and phone checked in headless Edge on the live site after the deploy.
- **Repo:** branch `main`, **no remote**. It exists only in `E:\Work\Nisatech\PurseShop` and in the
  deploy bare repo on the server. Three worktrees under `.claude/worktrees/`:
  - `3d-logo-wiwu-model-5ec558` (2026-10-19 and 20): **WiWU's logo on the 3D bag's plate** (see *The 3D
    model*), the client's answers, the hero's posters and the logo in the site's colours; merged into
    `main` and deployed. Its dev servers run on 8032/5182 (`logo-backend`,
    `logo-frontend` in its `.claude/launch.json`).
  - `hero-slider-3d-model-a5edb7` (this work), merged into `main`; it has the 3D tools' venv
    (`.venv-3d`), which the main checkout lacks.
  - `admin-panel-purchases-transactions-c63290`, another chat's, still at aa852c2 with an uncommitted
    edit to PLAN.md. Not merged; ask Amir what it is before touching it.

## Waiting on Amir

1. **The questions for the client** (below): he sends them and brings back the answers.
2. **Deploy go-ahead**, whenever there is new work (only on his word).
3. **Arvan's proxy (the cloud icon) for nisatech.org**: it was off for every record on 2026-10-20; the
   shop's is back on (2026-10-21). Told him the other records (nisatech.org, contech, pd, ops) need it
   on too: they have no HTTPS of their own on the server, so without it their https addresses show
   nisatak.com's site behind a certificate warning.

## Waiting on the client

The questions are on Amir's Claude doc **«پرسش‌ها از کارفرما»**
(https://claude.ai/artifact/QVALnWKusT2ptTdpxA5dWV, private until he shares it; it exports to PDF, and
he was given a PDF of it). Ten questions after Amir's edits:

1. the site's name; 2. material and size; 3. how the bag opens with a flat battery; 4. what's in the
box; 5. warranty and returns; 6. shipping prices, from which city, how fast; 7. who runs the orders
(panel accounts, contact details for the site); 8. full-size photo originals, plus the bottom, the far
end and a lock close-up for the 3D model; 9. launch date, advertising, expected visitors at peak; 10. the
price, with a launch campaign.

**Answered on 2026-10-20** (through Amir; on the site via migration 0004):
- **1. Name:** the shop is WiWU, «ویوو», with WiWU's own logo (PLAN.md risk R5: the client's call).
- **3. Battery:** a full charge takes 5 to 10 minutes and lasts about a month; a power bank will do.
- **5. Warranty:** 72 hours, replacement if the fingerprint lock fails or the zipper sticks, the shop
  paying the shipping. Returns stay 7 working days (the law), postage on the buyer.
- **6. Shipping:** the post (Pishtaz) is free; Tipax is paid by the buyer on delivery (پس‌کرایه);
  4 to 6 working days. Shipping from Dubai is in the price.
- **10. Price:** 14,100,000 toman (Amir wrote «۱۴.۱۰۰»). No launch campaign named yet.
Still open: 2, 4, 7, 8, 9.

It ends with a **cost estimate** for a campaign of about 10 days: server 2 to 3 million toman, SMS
(Kavenegar) 1 to 1.5 million, about 3 to 4.5 million in all. Amir set those figures. On 2026-10-20 he
asked for quotes to give the client, with a server that won't fall over at scale and works for visitors on
a VPN. Screenshots in `media/quotes/` (not in git): Arvan's calculator per size (Tehran, standard cores,
25 GB SSD, one IPv4), their server price list and CDN plans, Kavenegar's plans and their OTP FAQ.

| Arvan, Tehran | Per day | 10 days | 15 days | Peak (est.) | A campaign day |
| --- | --- | --- | --- | --- | --- |
| 2 cores / 4 GB | 65,540 | 655,400 | 983,100 | ~40 visits/s | ~300,000 visits |
| **4 cores / 8 GB** (recommended) | 112,080 | 1,120,800 | 1,681,200 | ~80 visits/s | ~600,000 visits |
| 8 cores / 16 GB | 205,160 | 2,051,600 | 3,077,400 | ~160 visits/s | ~1,200,000 visits |

- Toman; billed by the hour, resizable in minutes (start on 4, go to 8 if the campaign takes off).
  Capacity is a conservative estimate from LOADTEST.md (one old shared core: ~18 visits/s with nothing
  cached), assuming the page cache and Arvan caching the images and 3D model.
- **CDN:** Arvan's free plan is enough (unlimited traffic in and outside Iran, static caching, DDoS
  protection with a JS challenge). The "رشد" plan (3,000,000 a month) adds rate limits and a captcha.
- **VPN:** an Iranian server behind Arvan works on a VPN: Arvan serves visitors abroad too. Checked on
  2026-10-20: this PC's VPN exits in the US, and the staging site, 3D included, loads through it. If Iran's
  international link is cut, VPN users can't reach it, while visitors with the VPN off still can.
- **Kavenegar:** the Advanced plan is 600,000 toman a year (their FAQ says the OTP service needs it).
  The per-message price only shows in their panel; a Persian SMS costs about 12 to 20 toman (the
  regulator's ceiling is 116 rial on a postpaid SIM). About 5 SMS per order.
- **cartbecart** (their site, 2026-10-20): Max (unlimited cards and payments) 490,000 toman a month,
  440,000 a month paid 3 months at once, 420,000 for 6; Pro (3 cards, 500 payments a month) 390,000 /
  350,000 / 330,000. No fee per sale. The page only offers 3- and 6-month payment; PLAN.md's "440k a
  month" is the 3-month rate. Sent to Amir for the client the same day, with Kavenegar's.
- **Arvan's panel prices more than its calculator.** Amir's panel (2026-10-20, Tehran بامداد) offered
  **G6-Small5**, 4 vCPU / 4 GB / 75 GB SSD, at 1,386,240 rial a day: 2,079,360 toman for 15 days (the
  calculator's 4 cores / 4 GB: 1,256,100). C5-Medium1, 2 / 4 / 25 GB, 870,240 rial a day; C5-Medium2,
  4 / 8 / 75 GB, 1,800,480. An hourly server can't be deleted in its first 48 hours. Recommended to him:
  G6-Small5 with **Ubuntu 24.04**, as on staging (Python 3.12), not 26.04.

Older items the client still owes, from PLAN.md §11 (the earlier message, now mostly folded into the
doc): the cards and the card holder's name, cartbecart's Max plan with API access and a separate Android
phone, a Kavenegar account in their name, the Enamad details (mobile under their national ID, email,
business address), the `.ir` domain under their national ID.

## Next, in order

1. **Re-run the load test** (LOADTEST.md, *Running it again*) now the page has no 3D model to download
   (2026-10-23); the Arvan rule for `/models/*` it waited for isn't needed while the 3D bag is off.
2. **For the launch server**, recommended to Amir (not built): an Arvan cloud server in Tehran behind
   Arvan's CDN, **4 cores** for the campaign (Amir is looking at G6-Small5, 4 cores / 4 GB, Ubuntu 24.04;
   2026-10-20 quotes above; resize to 8 cores if needed),
   2 GB swap; gunicorn with about 2 workers per core × 4 threads (`--worker-class gthread`, in
   `deploy/systemd/purseshop.service`), so SMS and payment calls don't hold up pages. Today's shared server (1 core, 1 GB, three other sites) tops out around 18 visits a second
   without the Arvan rule (LOADTEST.md).
3. **On staging:** a test order end to end (the SMS code is in `journalctl -u purseshop`), then cancel it
   in the panel. Replace the sample card once the client sends theirs.
4. **Client answers:** the domain must belong to whoever applies for Enamad; with the shop named WiWU, the
   client needs a domain they can register (risk R5). Fill the card holder's name and the contact details
   before applying for Enamad.
5. **Hero photos:** the bag-only slides are made from WiWU's renders (no AI image tool here; the
   search for others is in `media/hero-candidates/`, not in git). Photos of the client's own brown bag
   would be better: run them through `tools/hero_slides.py` or add them as they are.
6. **The two-zipper bag's photos:** its pictures are a reseller's tan render recoloured
   (`tools/phantom_photos.py`); photos of the client's own bags would be better.
7. **cartbecart:** once the client's Max account opens their API docs, finish `backend/shop/payments.py`
   (`TODO(cartbecart docs)`): field names and unit, checking each deposit, whether orders must be
   registered first. Until then `PAYMENT_PROVIDER=manual`.
8. **Kavenegar:** the client's account and API key, with the 11 templates in README → *SMS*.
9. **Go live, then Enamad:** PLAN.md §8 and phase 2 in §9. One real 14.1M payment end to end, then refund it.
10. **3D, if wanted back:** see *The 3D model* below and README (it's off the page since 2026-10-23).

## What Amir asks for, and how he reacts

- **Deliverables first, fast.** When he asks for something to send (questions, a PDF), give that file
  at once and keep chat short; long silent work in between frustrates him. He writes in English to us
  and Persian to the client; client-facing text is Persian.
- **Rich, not AI-looking.** He rejected a calm "shop window" design as "too simple" for the "instrument"
  look (README, *Look*). Avoid template patterns: cream and gold, an eyebrow label on every section,
  three equal cards, plain minimal pages. **Each section looks different** as you scroll.
- **The hero:** photos as the background with the text on top (he sent a Pinterest pin of a full-bleed
  landscape with a floating pill menu and centred text). Of three designs built on that (centred poster,
  campaign page, frosted panel) he kept the **campaign page**. He didn't like a photo beside the text.
- **The 3D bag** lived in جزء به جزء until 2026-10-23, when he asked for a picture of each bag instead. If
  it comes back, never: a white glow or a circular fade around it, an edge fade, wheel zoom, or a view
  that cuts the bag at the stage's edges.
- **Phones:** he reviews on the live site on his phone. An older layout was "mid".
- **Persian must join properly:** Vazirmatn for text; Vazir Code only for figures and Latin
  (`unicode-range`). A self-hosted font without ی ک گ پ broke words apart on his phone.
- **Photos:** he agreed to use WiWU's own studio photos (found on resellers' pages) on the site.

## Running it locally

- **Setup:** README → *Running it locally*. Ports: Django `127.0.0.1:8030`, Vite `127.0.0.1:5180`
  (8000 is Contech).
- **A second checkout** (a git worktree) runs beside the first: `VITE_PORT=5181` for Vite, and
  `VITE_DEV_SERVER=http://127.0.0.1:5181`, `PUBLIC_URL=http://127.0.0.1:8031` for Django
  (`runserver 127.0.0.1:8031`). Give it its own `npm ci` (Vite won't serve fonts through a link to another
  checkout's `node_modules`), and copy `backend/.env` and `db.sqlite3` in. The desktop app's preview
  pane reads `.claude/launch.json` in the checkout; it stops idle servers after a while, so check with
  `curl` and start them again.
- **SMS in development:** printed in the Django terminal; checkout and lookup also show the code.
- **Page cache:** off in development, so template edits show at once.
- **Panel logins** for local testing: `backend/dev-credentials.txt` (not in git; never paste it).
- **Not in git** (copy these when moving machines): `backend/.env`, `backend/db.sqlite3`,
  `backend/dev-credentials.txt`, `backend/private/`, the venvs, the unused AI attempts in `media/3d/ai/`.

## Checking the site in a browser

The scripts in `tools/dev/` run headless Microsoft Edge through patchright, loaded from the CodeGPT VS
Code extension (`~/.vscode/extensions/danielsanmedium.dscodegpt-*`). On another machine install that
extension, or `npm i patchright` and change the two lines that load it.

| Script | What it does |
| --- | --- |
| `sections.mjs <w> <h> <dir>` | Every home section and the other pages. `BASE=` for staging. |
| `phone.mjs <dir> [base]` | The phone: swiping the hero, the parts tabs with the 3D bag, the sections. |
| `bag-states.mjs <base> <dir>` | The 3D stage when it loads, when the model is blocked, without WebGL2. |
| `shots.mjs`, `orbits.mjs`, `overflow.mjs` | Each side and tapped part of the 3D bag; model close-ups; phone width. |

- **Local only:** the scripts pass `--disable-features=LocalNetworkAccessChecks,…`, or Edge blocks the
  page (8030) from loading Vite's modules (5180) and it comes out unstyled.
- **Colours:** to check them, click each `#parts [data-color-picker] [data-color]` and screenshot
  `[data-bag-stage]`; `--disable-3d-apis` shows the photo backup. (The checks on 2026-10-19 used ad-hoc
  versions of these; they're not in `tools/dev/`.)
- **The app's own browser pane** stops drawing while hidden: scroll-driven animations freeze and
  screenshots come out half-faded. Use the headless scripts.

## The 3D model

How it's built and checked: README, *The hero and the 3D bag* (steps 1 to 7). In short: an AI shape
(Hunyuan3D-2mv) from the client's three photos, fitted cameras, the photos baked on, the lock, zipper and
far end modelled from measurements, the front pulled taut. Colours are tints of the baked texture
(`setColor` in `bag3d/scene.ts`, `finish` in `details.ts`); a colour added in the panel tints it from its
swatch.

- **The brand plate** (2026-10-19) is modelled, not baked: `details.logo_plate` puts it on the finished
  front from its corners in the front photo (17.9 x 19 mm), `bake.painted_out` removes the photo's blurry
  plate first, and `bag3d/logo.ts` draws its face in the browser: WiWU's emblem (the tall hexagon round
  an i) and WIWU, traced from the logo on wiwu.com (`logo.png` on their Shopify CDN) and placed as on the
  plate in `black-front.jpg`. The small mipmaps are hand-drawn with a bolder, brighter logo so it still
  reads on phones, where the plate is about 25 pixels across. Pin 1 points at the plate from the side
  (a lead, as on the lock), so the number doesn't cover the logo.
- **xatlas is touchy:** it cuts this mesh into very small charts (1.6 to 2.2 vertices per triangle), and a
  small change to the geometry can add or save 100 KB on the desktop model. Rebuilding unchanged code
  gives the same bytes. Check the sizes after a rebuild.
- **Rebuild:** `.venv-3d/Scripts/python tools/build_model.py` (both models, about 2 minutes each;
  `desktop` for only `alpha.glb`). The venv: `py -3.12 -m venv .venv-3d && .venv-3d/Scripts/pip install
  -r tools/requirements.txt` (rembg's venv, `tools/requirements-rembg.txt`, only for new photo masks).
  `frontend/node_modules` must be installed (gltf-transform).
- **What would make it better:**
  - the texture from WiWU's sharp studio shots (`media/source-photos/wiwu/`) instead of the client's
    phone photos: each needs a camera (`KEYPOINTS`/`START` in `fit_cameras.py`, `FEATURE_WEIGHT` in
    `refine_cameras.py`, a mask; photos are assumed 960 x 1280), then `bake.py` weighting them first;
  - the lock traced again from `black-lock-end.webp` (about 500 px tall, against the client's 125):
    `MODULE` in `details.py`;
  - the bottom and the far end: no photo shows them (WiWU's either), so they are plain leather.
- **After a rebuild:** check every side and tapped part (`shots.mjs`): the bag and its shadow inside the
  stage, the pins on their parts. Pins are `views.PARTS` (snap with `window.__bag.debugSnap(at, normal)`
  through CDP); the lock's three come from `details.module` in the model's .json.
- **Order for new photos** (from `PurseShop/`; the last steps need the dev servers):

```bash
.venv-rembg/Scripts/python tools/photo_masks.py
.venv-3d/Scripts/python tools/fit_cameras.py
git show 0d3ba7a:media/3d/cameras.json > ../cameras-original.json
.venv-3d/Scripts/python tools/refine_cameras.py ../cameras-original.json
.venv-3d/Scripts/python tools/details.py
.venv-3d/Scripts/python tools/build_model.py
node tools/compare.mjs && .venv-3d/Scripts/python tools/dev/compose.py
```

## The site's photos

- **Hero:** `frontend/public/images/look/` (600, 1200 px), from two of Amir's photos and four bag-only
  posters (`tools/hero_slides.py` from WiWU's renders in `media/source-photos/wiwu/`, its docstring has the
  commands; the black render at the others' angle is made by `tools/black_render.py`) in `media/source-photos/look/` (`views.LOOK`: alt text and crop points for tall and wide
  screens). Amir's other four photos stay in `media/source-photos/look/`, off the site.
- **Logo:** WiWU's marks, traced, in the site's colours (`shop/wiwu_logo.html`: the text's colour, the
  i-dots green; Amir didn't want WiWU's navy, 2026-10-20). The favicon is the emblem on ink.
- **Product shots:** `front`, `back` and `side`, cut out of WiWU's studio photos by
  `tools/studio_images.py` (`media/source-photos/wiwu/`); the size drawing's `--cm` follows the front's
  proportions (`home.html`). `colors/<black|brown>.webp` (checkout, the 3D backup, pick a colour) are
  from `tools/color_photos.py`: WiWU's renders, both turned the same way (the black is their brown made
  black by `tools/black_render.py`).
- The client's own three phone photos and their cutouts (`media/cutouts`, `tools/web_images.py`) are
  what the 3D model was baked from; the site no longer shows them.

## Gotchas

- **Fonts for Persian.** Check that a served woff2 has ی ک گ پ before using it (fontTools, or render it).
  Fontsource's Readex Pro has none; Google's preview copy differs from it.
- **Page cache.** `shop/pagecache.py` empties it on `post_save`/`post_delete`. A queryset `.update()` and
  a migration's data changes send no signal: after a deploy whose migration changes content, run
  `manage.py shell -c "from django.core.cache import caches; caches['pages'].clear()"` on the server.
- **Cached files.** Images and models are cached a week (nginx, Arvan for images; Arvan keys on the full
  address). In production `{% asset %}` adds `?v=<content hash>`, so replacing a file under the same
  name is safe. Anything linked without `{% asset %}` (the link preview, the search data) isn't
  versioned: give a changed file a new name there.
- **A copied database** from the main checkout predates migration 0003 (`no such column:
  shop_color.photo`): run `manage.py migrate` on the copy.
- **Headless Edge hides page warnings:** patchright doesn't report `console.warn`, so a 3D bag that
  silently falls back to the photos shows nothing. Wrap `console.warn` through CDP
  (`Page.addScriptToEvaluateOnNewDocument`) to see why.
- **`seed_store` runs on every deploy**: it only adds what's missing. It used to set placeholder shipping
  fees whenever both were 0, which would have undone free post; that's gone (2026-10-20).
- **Tests and colours.** `seed_store` creates black and brown; the tests' `Base.setUp` deletes all
  but black, because they assume a store that asks no colour.
- **CSS layers.** A rule in `@layer components` loses to any Tailwind utility on the same element. The
  3D stage's state rules and the see-through header sit outside the layers, at the end of `site.css`.
- **The 3D loads late:** after the page's `load` and when `#parts` is near, so scripts that need it
  scroll there first. `window.__bag` (development only) is reachable through CDP `Runtime.evaluate` only.
- **Python on Windows:** prints cp1252, so set `PYTHONIOENCODING=utf-8`, or with `python -I` (which
  ignores that variable) pass `-X utf8`. It writes CRLF, as does `makemigrations`; the repo is LF.
  Write long scripts to a file rather than a bash heredoc.
- **`makemigrations --check`** reports an `Alter field claim_file on order` that predates this work.
- **Server over SSH:** `pkill -f <name>` through `ssh` matches its own command line and ends the session.
  The server's DNS can lag hours behind Arvan.
- **ArvanCloud:** with the shop's own certificate (2026-10-20) any origin protocol works; before it,
  over HTTPS Arvan reached nisatak.com. HTML is never cached by Arvan. Check where a name points with
  `nslookup <host> k.ns.arvancdn.ir`: the server's IP means the proxy is off, Arvan's means on.
- **A new HTTPS host on this server** needs its own certificate: nginx answers any name it has no
  HTTPS block for with nisatak.com, the first HTTPS site it loads and so its default
  (`server-setup.sh CERT=1` for the shop).
- **Plane:** create and edit items from a signed-in Plane tab in the browser pane with
  `fetch('https://api.plane.so/api/workspaces/nisatech/projects/c2c38e4a-3e34-4392-b506-19d3bc8d9724/issues/', {credentials: 'include', headers: {'X-CSRFToken': …}})`
  (the token from `https://api.plane.so/auth/get-csrf-token/`). PATCH `description_html` only while the
  item has no `description_binary` (nobody opened it in the editor). The API silently drops bodies with a
  Windows path or a sentence about the repo or GitHub. Done state `125b4e60-…`; Amir is `e6ccb4c5-…`
  (read both from the API).
- **Working time** for Plane comes from the session log's active time (gaps over 10 minutes are waiting).

## Working agreements

- **Commits:** one commit per task, plain message. **No Co-Authored-By line or any Claude attribution**,
  anywhere.
- **Deploys:** only on his explicit go-ahead. Work in a worktree goes onto `main` first (fast-forward),
  then `DOMAIN=shop.nisatech.org bash deploy/deploy.sh` from `PurseShop/` on a clean `main`. Before:
  tests and typecheck. After: every page 200 on the server and through Arvan, the changed files served
  fresh, a browser pass on the live site, the page cache emptied if a migration changed content, and a
  note here.
- **Plane:** every task is an item (project Nisatech, `NISA-*`, name starting "PurseShop: "), Done,
  assigned to Amir, first line `Estimate: X · Spent: Y`. Spent is measured working time rounded up (15m,
  30m, 1h, then the next full hour), **not tripled** (Amir, 2026-10-20: he had the last five tripled
  items put back to measured time); follow-up work adds to Spent with a breakdown. Redeploys go on
  NISA-69. Estimates: about a third of classic hours.
- **Credentials:** never repeated in chat or committed. Amir types passwords himself (sudo, panel
  accounts).

## Plane (Nisatech project, all Done, assigned to Amir)

| Item | What | Spent |
| --- | --- | --- |
| NISA-65 | Interview, cutouts and plan | 3h* |
| NISA-66 | Store core | 3h* |
| NISA-67 | 3D hero and scroll tour | 9h* (1h30m + 3h + 3h + 1h30m) |
| NISA-68 | Site design around the 3D bag, instrument look | 6h* (3h + 1h30m + 1h30m) |
| NISA-69 | Staging online at shop.nisatech.org, redeploys | 2h (30m + 15m + 15m + 15m + 15m + 15m + 15m) |
| NISA-70 | Load test of the live server, page cache | 30m |
| NISA-71 | Colours (panel, product page, checkout, orders) | 30m |
| NISA-72 | Phone layout (one-screen tour, roomier sections) | 15m |
| NISA-73 | Hero shows only the 3D bag (no ring, no glow, photos as backup) | 30m |
| NISA-75 | Hero as a photo campaign page, the 3D bag in the parts section | 2h |
| NISA-76 | Questions for the client, server and SMS costs | 30m |
| NISA-77 | WiWU name, brown and white colours, the 3D bag recoloured, studio photos | 1h |
| NISA-78 | WiWU logo on the 3D bag's brand plate | 1h |
| NISA-79 | The client's answers on the site (price, shipping, battery, warranty, WiWU name and logo) | 15m |
| NISA-80 | Server and SMS quotes for the client, traffic per server size | 30m |
| NISA-81 | Hero posters of the bag in each colour, the logo in the site's colours | 1h |
| NISA-82 | Hero sharp on laptops, colour dots to their poster, the 3D backup in the picked colour, pick-a-colour section | 1h |

\* Three times the measured time, at Amir's request. On 2026-10-20 he had the last
five tripled items (NISA-69, 75 to 78) put back to measured time; everything else is measured. NISA-74 is
another project's (Finance).

## Deploy history

| Date | Commit | What |
| --- | --- | --- |
| 2026-10-23 | 6d8de65 | A picture of each bag instead of the 3D bag in جزء به جزء (Alpha and two-zipper, black and brown, each with its price and checkout), the 3D island off the page (no three.js, no model download); the two-zipper bag at 16,500,000 toman (migration 0007, page cache emptied after it; backup `db-20261023-120433.sqlite3`, server time). The first run dropped its SSH connection after pushing the code; the second went through. Checked: the four pictures and their links, the two-zipper section and checkout, no 3D requests, desktop and phone in headless Edge |
| 2026-10-21 | bb910c7 | The two-zipper bag (WiWU Phantom Pro) in black and brown as a second model, added by `seed_store` with price 0, so off the site until a price is set in the panel; the panel's model switch; checkout and orders for it (no migration; page cache emptied; backup `db-20261021-131307.sqlite3`, server time). Checked: hidden on home, checkout for it falls back to the Alpha, its pictures and the new scripts match the build |
| 2026-10-21 | 82f2c89 | Hero opens with Amir's photo of the man with the bag for 3 s (counted from when it has loaded; the 3D bag starts only after the hero moves on, which had stretched it to 5 s); silver gone (migration 0006, page cache emptied after it; backups `db-20261021-114043.sqlite3` and the redeploy's, server time); the black-and-brown poster as mirror images; the closing section's grid follows the number of colours. The deploy's new HTTPS check passed. Arvan's proxy was back on |
| 2026-10-20 | 4b38735 | Server only, no app deploy: the shop's own HTTPS (Let's Encrypt via `server-setup.sh CERT=1`) after https://shop.nisatech.org showed nisatak.com with Arvan's proxy off; the deploy-time HTTPS check is in `remote-deploy.sh` from the next deploy |
| 2026-10-20 | 4563f06 | Hero on laptops: wide posters (up to 2560 px), Amir's photos at their own shape; hero colour dots jump to their poster; the 3D backup shows the picked colour and catches a 3D that draws nothing; pick-a-colour closing section; the brown is WiWU's coffee brown with gunmetal hardware (migration 0005, page cache emptied after it; backup `db-20261020-102414.sqlite3`, server time) |
| 2026-10-20 | b9f23f3 | The client's answers: shop «ویوو» with WiWU's logo in the site's colours, 14,100,000 toman, free post and Tipax on delivery, 4 to 6 working days, battery, 72-hour warranty; hero of four bag-only posters (black first) and two of Amir's photos, no thumbnails, a compact buy button (migration 0004, page cache emptied after it; backup `db-20261020-092929.sqlite3`, server time) |
| 2026-10-19 | f04fddb | WiWU's logo on the 3D bag's plate (emblem and name), pin 1 beside it, new models `?v=bccdb021` / `?v=9b666061` (no migration; backup `db-20261019-094240.sqlite3`, server time) |
| 2026-10-19 | ebc1158 | WiWU name, three colours, recoloured and taut 3D bag, studio photos, `?v=` addresses (migration 0003; backup `db-20261018-205907.sqlite3`, server time) |
| 2026-10-18 | 0911b3a | Campaign hero, 3D bag in جزء به جزء, colours, page cache (migration 0002; backup `db-20261018-164322.sqlite3`) |
| 2026-10-16 | 2f9ceb7 | Design review round: Vazirmatn, section grounds, phone menu, footer |
