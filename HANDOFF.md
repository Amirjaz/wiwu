# PurseShop: handoff

State on **2026-10-18 (26 Mehr 1405)**, written so the work can go on in a new chat.

**A new chat should start here:** read this page, then [PLAN.md](PLAN.md) for the decisions, risks and
the message for the client, [README.md](README.md) for how everything works, and
[LOADTEST.md](LOADTEST.md) for the server capacity. This page is the short version, plus what isn't
written down anywhere else.

## Where it stands

- **Staging is online at https://shop.nisatech.org**, but it runs **2f9ceb7** (2026-10-16).
  - Open to everyone (no password, Amir's choice), but kept out of search engines (noindex).
  - SMS codes only go to the server log and payments are manual, so people can browse but can't finish
    an order.
  - Plain http redirects to https.
- **Local `main` is at 5ae128d, ahead of the server by work that isn't deployed yet:**
  - **colours** (8c41240): managed in the panel, with only black shown for now;
  - **the phone layout** (8c41240): the tour is one screen, with the stop cards swiped sideways;
  - **the page cache** (8c41240): the home and policy pages kept for 60 s, cleared on any content
    change;
  - **nginx no longer gzips the 3D models** (8c41240): this only applies when the admin re-runs the
    server setup;
  - **a 3D-only hero** (0881c7b): no white glow or ring, with the photos only as the backup.
- **Checks:** `manage.py test shop` runs 43 tests and they pass; `npx tsc --noEmit` and `npm run build`
  pass. Desktop and phone were checked in headless Edge (`tools/dev/`).
- **Repo:** one branch, `main`, and **no remote**. The repo exists only in `E:\Work\Nisatech\PurseShop`
  and in the deploy bare repo on the server. To continue on another machine, copy the folder (with
  the files under *Running it locally*) or push it to a private repo first.
- **Store features:** product page, checkout with an SMS code, card-to-card payment with a unique amount
  per order, "I've paid" review, the minute timer, shipping, returns, staff panel, SMS templates, SEO,
  colours.
- **Client:** no answers yet. PLAN.md §11 is the message to send, in Persian, ready to paste.

## Waiting on Amir

1. **Deploy go-ahead** for everything above that isn't on the server yet. He was asked; no answer yet.
2. **Tripling the new Plane times.** NISA-70 to 73 are at measured times. On 2026-10-16 he had every
   earlier PurseShop "Spent" tripled. Ask whether these get the same.
3. **Colours:** which colours, and their photos. Until then only black is shown.
   - All colours are assumed to cost the same; he hasn't confirmed that.
   - With photos, the 3D and the hero photos should switch per colour (not built).
4. **ArvanCloud cache rule for `/models/*`** (his Arvan panel): cache everything, 7 days. Today the 3D
   model bypasses Arvan's cache, so every visitor downloads it from our server (LOADTEST.md).
5. **Staff panel account:**
   `ssh -t amir@185.231.180.92 'cd /srv/purseshop/app/backend && .venv/bin/python manage.py createsuperuser'`.
   He types the password; then add people to Owners or Staff in `/admin/`.

## Next, in order

1. **Deploy, once Amir says so.**
   - Run `DOMAIN=shop.nisatech.org bash deploy/deploy.sh` from `PurseShop/`, on a clean `main`.
   - Migration 0002 gives existing products and orders the colour black.
   - Then verify:
     - every page answers 200 on the server, and through Arvan;
     - `node tools/dev/phone.mjs <dir> https://shop.nisatech.org` and
       `BASE=https://shop.nisatech.org node tools/dev/sections.mjs 1440 900 <dir>` both look right.
   - Record the redeploy on NISA-69 (or a new item) and in this file.
2. **After the deploy:**
   - Amir adds the Arvan cache rule (above). Check that `x-cache` reads `HIT` on the second request
     for `/models/alpha-mobile.glb`.
   - The server admin re-runs the root setup, so the nginx change takes effect. First send a fresh
     copy, since the old `~/purseshop-deploy` predates it:
     - `scp -r deploy amir@185.231.180.92:purseshop-deploy`
     - `sudo DOMAIN=shop.nisatech.org bash /home/amir/purseshop-deploy/server-setup.sh`
     - `amir` can't sudo, so the admin runs it.
   - Re-run the load test (LOADTEST.md, *Running it again*).
3. **On staging:** a test order end to end (the SMS code is in `journalctl -u purseshop`), then cancel it
   in the panel. Replace the sample card and the placeholder shipping prices once the client sends them.
4. **Client answers (PLAN.md §11).** The store name blocks the `.ir` domain, and the domain blocks
   Enamad: the domain must belong to whoever applies.
5. **Price (risk R1).** 10,000,000 toman + shipping + the offset lands just above 10M, and some transfer
   channels stop at 10M. Recommend that price + shipping + 999 stay ≤ 10,000,000; the client decides.
6. **cartbecart.** Once the client's Max account opens their API docs, finish `backend/shop/payments.py`
   (`TODO(cartbecart docs)`):
   - the real field names and the unit;
   - checking each deposit through their API;
   - whether orders must be registered with them first.

   Until then, `PAYMENT_PROVIDER=manual`.
7. **Kavenegar.** The client's account, with the 11 templates listed in README → *SMS*.
8. **Policy pages.** The [bracketed] text waits for the client: the warranty, how the bag opens with
   an empty battery, and the card holder's name. It must be filled in before applying for Enamad.
9. **Go live, then Enamad.** See PLAN.md §8 and phase 2 in §9: one real 10M payment end to end, then
   refund it. For the launch, consider giving the store its own small server (LOADTEST.md).
10. **3D, only if new photos arrive** (see below).

## What Amir has asked for, and how he reacts

The design went through several rounds. These are the things a new chat would otherwise relearn the
hard way:

- **He wants it rich and not AI-looking.**
  - He rejected a calm "shop window" design (near-white, lapis, Markazi) as "too simple" and
    switched to the "instrument" look (README, *Look*).
  - Avoid template patterns: cream and gold, an eyebrow label on every section, three equal cards,
    plain minimal pages.
- **Each section must look different** as you scroll: grey tour, black lock demo, light parts table,
  steel specs, graphite buying, grey FAQ, green closing band, black footer.
- **The hero is 3D only.**
  - He called a white glow and a circular fade around the bag ugly. They were the photo shown while
    the 3D loaded, and an elliptical mask on the canvas.
  - The photos are the backup only. Don't bring back the edge fade, wheel zoom, or a glow behind
    the bag.
- **Phones:** he found the old layout "mid". The tour is now one screen with swipe cards, and the
  sections have more room.
- **Persian text must join properly.** A self-hosted font missing ی ک گ پ broke words apart on his
  phone. Vazirmatn is the text font; Vazir Code is used only for figures and Latin
  (`unicode-range`).
- He reviews on the live staging site, and on a phone.

## Running it locally

- **Setup:** README → *Running it locally*.
- **Ports:** Django on `127.0.0.1:8030`, Vite on `127.0.0.1:5180`; port 8000 belongs to Contech.
- **Desktop app:** `E:\Work\Nisatech\.claude\launch.json` has `purseshop-backend` and
  `purseshop-frontend` for the preview pane. If a port is taken, another chat's servers are probably
  still running; check with `curl` first.
- **SMS in development:** printed in the Django terminal. The checkout and lookup pages also show the
  code.
- **Page cache:** off in development (`DEVELOPMENT=True`), so template edits show at once.
- **Panel logins** for local testing are in `backend/dev-credentials.txt`. It is not in git; don't
  paste it anywhere. On a fresh database, run `manage.py createsuperuser`, then add people to the
  Owners or Staff group in `/admin/`.
- **Testing colours locally:** show a second colour in the panel, or with `manage.py shell` add one with
  `shown=True`. Hide or delete it afterwards: with only black shown, the site asks no colour.
- **Not in git** (copy these when moving machines):
  - `backend/.env`;
  - `backend/db.sqlite3`;
  - `backend/dev-credentials.txt`;
  - `backend/private/` (transfer screenshots);
  - the AI attempts in `media/3d/ai/` other than the one used.

## Checking the site in a browser

The scripts in `tools/dev/` run headless Microsoft Edge through patchright, loaded from the CodeGPT VS
Code extension (`~/.vscode/extensions/danielsanmedium.dscodegpt-*`). On another machine, install that
extension, or `npm i patchright` and change the two lines that load it.

| Script | What it does |
| --- | --- |
| `sections.mjs <w> <h> <dir>` | Every home section and the other pages. Set `BASE=` for staging. |
| `phone.mjs <dir> [base]` | Phone tour: swiping the cards, the tabs, the sections. |
| `hero-states.mjs <base> <dir>` | The hero when the 3D loads, when the model is blocked, and without WebGL2. |
| `shots.mjs`, `orbits.mjs`, `overflow.mjs` | The older tour, 3D and width checks. |

- **Local only:** the scripts pass `--disable-features=LocalNetworkAccessChecks,…`. Without it, Edge
  blocks the page (port 8030) from loading Vite's modules (port 5180), and the page comes out
  unstyled.
- **The desktop app's own browser pane** stops drawing frames while it's hidden. Smooth scrolling and
  the scroll-driven `.reveal` animations then freeze, and screenshots come out half-faded. Use instant
  scrolling, or the headless scripts above.

## The 3D model, when new photos arrive

What would make the model exact:

- photos of the **bottom** and the **far end**: no photo shows them, so they are plain leather now;
- a sharp **close-up of the lock**: today it is traced from about 125 px;
- a sharper **front**.

Ask for daylight, the phone at the bag's height, and the whole side in frame. Photos of the other
colours are a separate need (*Waiting on Amir*).

**Setup**

- Venvs (Python 3.12), from `PurseShop/`:
  - `.venv-3d` from `tools/requirements.txt`;
  - `.venv-rembg` from `tools/requirements-rembg.txt`;
  - the commands are in each file's header.
- `cd frontend && npm install` brings gltf-transform, which `build_model.py` needs.

**Adding a photo**

- **Size:** every photo is assumed to be 960 x 1280, because `media/3d/cameras.json` holds one size.
  Resize new photos to that (they are 3:4), or generalise the code.
- **Per photo:**
  - its file in `SOURCES` (`tools/photo_masks.py`);
  - a few marked features and a starting pose in `KEYPOINTS`/`START` (`tools/fit_cameras.py`);
  - a weight in `FEATURE_WEIGHT` (`tools/refine_cameras.py`).
- **Baking:** `bake.py` projects through every camera in `cameras.json`.
- **Details:** `details.py` measures the lock in the side photo (`MODULE`, traced pixel coordinates)
  and the far end in the front and back photos (`FAR_END`). A lock close-up means tracing `MODULE`
  again in it.

**Order** (from `PurseShop/`; the last steps need the dev servers running):

```bash
.venv-rembg/Scripts/python tools/photo_masks.py
.venv-3d/Scripts/python tools/fit_cameras.py
.venv-3d/Scripts/python tools/fit_proportions.py   # optional: re-measures height and depth; then fit_cameras.py again
git show 0d3ba7a:media/3d/cameras.json > ../cameras-original.json
.venv-3d/Scripts/python tools/refine_cameras.py ../cameras-original.json
.venv-3d/Scripts/python tools/details.py
.venv-3d/Scripts/python tools/build_model.py       # `desktop`: only alpha.glb, while iterating
node tools/compare.mjs && .venv-3d/Scripts/python tools/dev/compose.py
node tools/dev/orbits.mjs
```

Results go to `media/3d/compare/` (not in git). For the tour, run `node tools/dev/shots.mjs 1440 900`
and `390 844`.

- **Framing:** with no edge fade, each tour stop's `frame` in `hero/scene.ts` must keep the bag and its
  shadow inside the stage. Check every stop after changing the model or the stage.
- **The AI shape** (`tools/ai_shape/`) only needs redoing if the new photos show it is wrong somewhere.
  In that case, check the cameras' marked features again (see the note in `run_hunyuan.py`).

## Gotchas

- **Fonts for Persian.** Before using a font, check that the served woff2 has ی ک گ پ, with fontTools or
  by rendering it.
  - Fontsource's Readex Pro has none of them. The browser then draws those letters from another font,
    and the words break apart.
  - A Google Fonts preview looked fine, because Google's copy differs.
- **Page cache and `.update()`.** `shop/pagecache.py` empties the cache on `post_save`/`post_delete`. A
  queryset `.update()` sends no signal, so it leaves stale pages for up to 60 s. Use `.save()` in
  anything that changes what the home or policy pages show.
- **Hero first paint.** The inline script in `home.html`'s head sets `html.three-d`, using the same test
  as `canRender3d()` in `hero.ts`. Change both together.
- **Output encoding.** Python run from Git Bash on Windows prints in cp1252, so printing Persian raises
  unless `PYTHONIOENCODING=utf-8` is set.
- **Line endings.** Python on Windows writes CRLF, and `makemigrations` too, but the repo is LF
  (`.gitattributes`). Open files with `newline=''`, and run `sed -i 's/\r$//'` on changed files before
  committing.
- **Heredocs.** Long inline Python in a bash heredoc gets mangled, Windows paths especially. Write a
  script file instead.
- **`window.__hero`.** patchright evaluates in an isolated world, so `window.__hero` is only reachable
  through CDP `Runtime.evaluate` (see `tools/compare.mjs`). It exists in development only, with
  `debugRender` and `debugOrbit`.
- **`cv2.remap`** can't take maps over 32767 px, so `bake.py` samples in rows (`sample()`).
- **`fit_cameras.py`** merges into `cameras.json`, so `shape_scale`/`shape_centre` from
  `fit_proportions.py` are kept.
- **Server over SSH:**
  - `pkill -f <name>` run through `ssh` matches its own command line and ends the session. Use a pid
    file.
  - The server's DNS resolver can lag hours behind Arvan changes.
- **ArvanCloud:**
  - The `shop` record needs the origin protocol set to **HTTP**. Over HTTPS, Arvan would reach
    nisatak.com's HTTPS on port 443 instead of the store.
  - HTML is never cached by Arvan (`x-cache: BYPASS`).
- **Plane:**
  - Items are created from a signed-in Plane tab in the browser pane, with
    `fetch('https://api.plane.so/api/workspaces/nisatech/projects/<project>/issues/', {method: 'POST', credentials: 'include', …})`.
  - Edit a description with a `description_html` PATCH only while the item has no
    `description_binary`, that is, nobody has opened it in Plane's editor. Otherwise the editor's copy
    wins; edit through the page instead.
  - Plane pages don't load while the browser pane is hidden, though fetches still work.
  - The API silently drops bodies that contain a Windows path or a sentence about the repo or GitHub.

## Working agreements

- **Commits:** one commit per task, with a plain message. **No Co-Authored-By line or any Claude
  attribution**, anywhere.
- **Deploys:** only on an explicit go-ahead. Before a deploy, run one short combined check (tests,
  build, a smoke pass), then verify on the server and through Arvan.
- **Plane:** every task goes in Plane (`app.plane.so/nisatech`, project Nisatech, `NISA-*`, name
  starting "PurseShop: ").
  - Mark it Done, assigned to Amir, with the first description line `Estimate: X · Spent: Y`.
  - Spent is working time, rounded up: 15m, 30m, 1h, then the next full hour.
  - Follow-up work adds to Spent, with a breakdown.
  - State the time in the chat summary too.
  - He may give his own figures (*Waiting on Amir*, 2).
- **Estimates:** at AI speed, about a third of classic hours. Waiting on the client is listed separately.
- **Credentials:** never repeated in chat or committed. Amir types passwords himself (sudo, panel
  accounts).

## Plane (Nisatech project, all Done, assigned to Amir)

| Item | What | Spent |
| --- | --- | --- |
| NISA-65 | Interview, cutouts and plan | 3h* |
| NISA-66 | Store core | 3h* |
| NISA-67 | 3D hero and scroll tour | 9h* (1h30m + 3h + 3h + 1h30m) |
| NISA-68 | Site design around the 3D bag, instrument look | 6h* (3h + 1h30m + 1h30m) |
| NISA-69 | Staging online at shop.nisatech.org | 2h15m* (1h30m + 45m) |
| NISA-70 | Load test of the live server, page cache | 30m |
| NISA-71 | Colours (panel, product page, checkout, orders) | 30m |
| NISA-72 | Phone layout (one-screen tour, roomier sections) | 15m |
| NISA-73 | Hero shows only the 3D bag (no ring, no glow, photos as backup) | 30m |

\* Amir's figures: three times the measured time, at his request on 2026-10-16. NISA-70 to 73 are
measured; ask him about tripling them.
