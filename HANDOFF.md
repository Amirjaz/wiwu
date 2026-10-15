# PurseShop: handoff

State on 2026-10-15 (23 Mehr 1405), when the work moved to another session; updated the same day after
the new look. [PLAN.md](PLAN.md) has the decisions, the risks and the message for the client;
[README.md](README.md) explains how everything works. This page is the short version, plus what isn't
written down anywhere else.

## Where it stands

- **Online on staging: https://shop.nisatech.org** (2026-10-15). Open to everyone (no password, Amir's
  choice), noindex, SMS codes only in the server log, manual payments: people can browse but can't finish
  an order. Plain http redirects to https. One branch, `main`, and **no remote**: the repo exists only in
  `E:\Work\Nisatech\PurseShop` (and the deploy bare repo on the server). To continue on another machine, copy the folder (with the local files
  listed under *Running it locally*) or push it to a private repo first.
- **Store:** product page, checkout with an SMS code, card-to-card payment with a unique amount per order,
  "I've paid" review, the minute timer, shipping, returns, staff panel, SMS templates, SEO.
  `manage.py test shop`: 38 tests pass. `npm run build` passes.
- **3D hero:** the bag is pinned beside a five-stop scroll tour, with a photo fallback at every stop. The
  model is the AI shape wrapped in the client's three photos, through cameras fitted to each photo. The
  lock module, zipper and far-end hardware are modelled from measurements in the photos. The last round
  (d743e56) answered the feedback on the lock close-up, the zipper from above and the far end.
- **Look:** "instrument" (README, *Look*), picked from two designs built around the 3D bag: aluminium
  grey, a lock demo, a parts diagram, the size on a centimetre mat, a sample bill. Checkout, order,
  lookup, policy pages and the panel follow through the shared tokens in `frontend/src/site.css`.
- **Client:** no answers yet. PLAN.md §11 is the message to send, in Persian, ready to paste.
- **Plane** (Nisatech project), all Done:
  - NISA-65: interview, cutouts and plan (1h).
  - NISA-66: store core (1h).
  - NISA-67: 3D hero and scroll tour (3h: 30m, then follow-ups of 1h, 1h, and 30m for this handoff).
  - NISA-68: site design around the 3D bag, instrument look (1h30m: 1h for the two designs and the shop
    window, then 30m to switch to the instrument and enrich it).
  - NISA-69: staging online at shop.nisatech.org (30m).

## Next, in order

1. **Get the client's answers (PLAN.md §11).** The store name blocks the `.ir` domain, and the domain
   blocks Enamad: the domain must belong to whoever applies.
2. **Staging** is live (above). Still to do there:
   - a staff panel account: `ssh -t amir@185.231.180.92 'cd /srv/purseshop/app/backend && .venv/bin/python manage.py createsuperuser'`
     (Amir types the password), then add people to Owners or Staff in `/admin/`;
   - a test order end to end (the SMS code is in `journalctl -u purseshop`), then cancel it in the panel;
   - replace the sample card and the placeholder shipping prices in the panel once the client sends them.
   - **Redeploy:** commit to `main`, then `DOMAIN=shop.nisatech.org bash deploy/deploy.sh`. Deploys still
     need Amir's go-ahead.
3. **Price (risk R1).** 10,000,000 toman + shipping + the offset lands just above 10M. Some transfer
   channels stop at 10M. Recommend that price + shipping + 999 stay ≤ 10,000,000; the client decides.
4. **cartbecart.** Once the client's Max account opens their API docs, finish `backend/shop/payments.py`
   (`TODO(cartbecart docs)`):
   - the real field names and unit;
   - checking each deposit through their API;
   - whether orders must be registered with them first.

   Until then, `PAYMENT_PROVIDER=manual`.
5. **Kavenegar.** The client's account, with the 11 templates listed in README → *SMS*.
6. **Policy pages.** The [bracketed] text waits for the client (warranty, how the bag opens with an empty
   battery, the card holder's name). It must be filled in before applying for Enamad.
7. **Go live, then Enamad.** See PLAN.md §8 and phase 2 in §9: one real 10M payment end to end, then
   refund it.
8. **3D, only if new photos arrive** (see below). Without them there is little left to gain.

## Running it locally

- **Setup:** README → *Running it locally*.
- **Ports:** Django on `127.0.0.1:8030`, Vite on `127.0.0.1:5180`. Port 8000 belongs to Contech.
- **Preview pane:** `E:\Work\Nisatech\.claude\launch.json` has `purseshop-backend` and
  `purseshop-frontend` for the desktop app's preview.
- **SMS in development:** printed in the Django terminal. The checkout and lookup pages also show the code.
- **Panel logins** for local testing are in `backend/dev-credentials.txt`. It is not in git; don't paste
  it anywhere. On a fresh database, run `manage.py createsuperuser`, then add people to the Owners or
  Staff group in `/admin/`.
- **Not in git** (copy these when moving machines):
  - `backend/.env`;
  - `backend/db.sqlite3`;
  - `backend/dev-credentials.txt`;
  - `backend/private/` (transfer screenshots);
  - the AI attempts in `media/3d/ai/` other than the one used.

## The 3D model, when new photos arrive

What would make the model exact:

- photos of the **bottom** and the **far end**: no photo shows them, so they are plain leather now;
- a sharp **close-up of the lock**: today it is traced from about 125 px;
- a sharper **front**.

Ask for daylight, the phone at the bag's height, and the whole side in frame.

**Setup**

- Venvs (Python 3.12), from `PurseShop/`:
  - `.venv-3d` from `tools/requirements.txt`;
  - `.venv-rembg` from `tools/requirements-rembg.txt`;
  - the commands are in each file's header.
- `cd frontend && npm install` brings gltf-transform, which `build_model.py` needs.
- The browser scripts (`tools/compare.mjs` and `tools/dev/*.mjs`) run headless Microsoft Edge through
  patchright. It is loaded from the CodeGPT VS Code extension (`~/.vscode/extensions/danielsanmedium.dscodegpt-*`).
  On another machine, install that extension, or `npm i patchright` and change the two lines that load it.

**Adding a photo**

- Size: every photo is assumed to be 960 x 1280, because `media/3d/cameras.json` holds one size. Resize
  new photos to that (they are 3:4), or generalise the code.
- Per photo:
  - its file in `SOURCES` (`tools/photo_masks.py`);
  - a few marked features and a starting pose in `KEYPOINTS`/`START` (`tools/fit_cameras.py`);
  - a weight in `FEATURE_WEIGHT` (`tools/refine_cameras.py`).
- `bake.py` projects through every camera in `cameras.json`.
- `details.py` measures the lock in the side photo (`MODULE`, traced pixel coordinates) and the far end
  in the front and back photos (`FAR_END`). A lock close-up means tracing `MODULE` again in it.

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

Results go to `media/3d/compare/` (not in git). For the tour, `node tools/dev/shots.mjs 1440 900` and
`390 844`.

**The AI shape** (`tools/ai_shape/`) only needs redoing if the new photos show it is wrong somewhere. In
that case, check the cameras' marked features again (see the note in `run_hunyuan.py`).

## Gotchas

- **Output encoding.** Python run from Git Bash on Windows prints in cp1252, so printing Persian raises
  unless `PYTHONIOENCODING=utf-8` is set. The console SMS backend is safe now (32e4d5b). Before that, 5
  tests failed in a plain terminal.
- **Line endings.** Python on Windows writes CRLF, but the repo is LF (`.gitattributes`). Open files with
  `newline=''`, and run `sed -i 's/\r$//'` on changed files before committing.
- **Heredocs.** Long inline Python in a bash heredoc gets mangled. Write a script file instead.
- **`window.__hero`.** patchright evaluates in an isolated world, so `window.__hero` is only reachable
  through CDP `Runtime.evaluate` (see `tools/compare.mjs`). It exists in development only, with
  `debugRender` and `debugOrbit`.
- **`cv2.remap`** can't take maps over 32767 px, so `bake.py` samples in rows (`sample()`).
- **`fit_cameras.py`** merges into `cameras.json`, so `shape_scale`/`shape_centre` from
  `fit_proportions.py` are kept.
- **Plane pages** don't load in the app's browser pane while the pane is hidden, though JS fetches still
  work. Plane's API also silently drops request bodies that contain a Windows path or a sentence about
  the repo or GitHub.

## Working agreements

- **Commits:** one commit per task, with a plain message. **No Co-Authored-By line or any Claude
  attribution**, anywhere.
- **Deploys:** only on an explicit go-ahead. Before a deploy, run one short combined check (tests, build,
  a smoke pass), then verify on the server.
- **Plane:** every task goes in Plane (`app.plane.so/nisatech`, project Nisatech, `NISA-*`, name starting
  "PurseShop: "). Mark it Done, assigned to Amir, with the first description line `Estimate: X · Spent: Y`.
  - Spent is working time, rounded up: 15m, 30m, 1h, then the next full hour.
  - Follow-up work adds to Spent, with a breakdown.
  - State the time in the chat summary too.
- **Estimates:** at AI speed, about a third of classic hours. Waiting on the client is listed separately.
- **Credentials:** never repeated in chat or committed.
