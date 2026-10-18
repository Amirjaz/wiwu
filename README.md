# PurseShop

Working name until the client picks one (see [PLAN.md](PLAN.md), the interview and all the decisions).
An online store for one product, the WiWU Alpha fingerprint-lock clutch («کیف دستی ویوو آلفا»; black, brown
and silver-white, about 10M toman), in
Persian. Payment is card-to-card to the owner's cards, confirmed automatically from the bank's deposit
SMS by cartbecart.com, or by staff in the panel.

| Folder | What |
| --- | --- |
| `backend/` | Django 5.2 (Python 3.12), SQLite. Renders the pages; JSON API under `/api/`; Django admin at `/admin/` |
| `frontend/` | Vite + React 18 + Tailwind v4 *islands* on Django's pages (checkout, order page, lookup) and the staff panel at `/panel` |
| `deploy/` | nginx site, systemd units (gunicorn + a minute timer) and deploy scripts for the Nisatech server |
| `media/` | the client's photos, the background-removed cutouts, 3D sources (not served) |
| `tools/` | `cutout.py`/`fix2.py` (background removal), `studio_images.py` (the site's product images, from WiWU's studio photos; `web_images.py` made them from the client's phone photos before), the 3D model's pipeline (see *The hero and the 3D bag*), `ai_shape/` (the AI shape it starts from), `dev/` (screenshots and checks) |

## Running it locally

```bash
cd backend && py -3.12 -m venv .venv && .venv/Scripts/pip install -r requirements.txt
printf 'Development=True\n' > .env
.venv/Scripts/python manage.py migrate && .venv/Scripts/python manage.py createcachetable
.venv/Scripts/python manage.py setup_roles && .venv/Scripts/python manage.py seed_store
.venv/Scripts/python manage.py runserver 127.0.0.1:8030
cd frontend && npm install && npm run dev      # Vite on 127.0.0.1:5180
```

Open http://127.0.0.1:8030. In development SMS are printed in the Django terminal (the OTP code
too) and logged in the panel. Panel users for local testing are in `backend/dev-credentials.txt`
(not in git). Tests: `manage.py test shop`.

## How an order works (`backend/shop/orders.py`)

1. **Checkout** (`/checkout/`): name, mobile, province/city, address, postal code, Pishtaz or Tipax,
   "gift: no price in the box". The mobile is confirmed with a 5-digit SMS code (5 minutes, 5 tries;
   one code a minute and 5 an hour per phone, 15 an hour per address, so the SMS credit can't be drained).
2. **The amount**: price + shipping + a random **1–999 toman** that no open order (or one expired in the
   last 48 h) has, so a bank deposit points at exactly one order. The buyer pays the extra (decided
   2026-10-14). Price, fee and card are copied into the order: later changes don't touch it.
3. **The card**: the active card used least recently (all in the owner's name). The order page shows it,
   the holder's name, the exact amount with copy buttons, and a 30-minute countdown. It polls every 5 s
   and checks again the moment the buyer comes back from their bank app (in-app browsers reload pages).
4. **Confirmation**: cartbecart sees the deposit SMS and calls the webhook → the order with that amount
   is paid (SMS to buyer and owner). With `PAYMENT_PROVIDER=manual`, staff approve it in the panel.
5. **"I've paid"**: the buyer can send the transfer reference, the last 4 card digits, the time and a
   screenshot → *needs review* → SMS to the owner → approve or reject in the panel.
6. **Late money**: a deposit for an order whose 30 minutes ran out goes to *needs review*; one for no
   order is logged and shown on the panel's Today page. Nothing is dropped.
7. **The minute timer** (`manage.py tick`, systemd timer): one reminder SMS at minute 15, expiry at 30,
   and with cartbecart on, an SMS to the owner if two orders in 3 hours ran out with no match (the
   forwarder phone is probably off).
8. **Shipping**: paid → preparing → shipped (tracking code → SMS) → delivered. The panel prints an address
   label and packing slip; a gift's slip has no prices.
9. **Returns**: 7 working days (Fridays skipped) from delivery, or from shipping + 3 days if never marked
   delivered. The buyer gives reason, Sheba (checked) and holder; staff mark it received, then the owner
   records the refund's transfer reference (SMS to the buyer).

Money is whole **rials** everywhere (bank SMS count in rials) and shown in tomans.

## cartbecart (`backend/shop/payments.py`)

Their API docs are behind their login. Until the client's **Max** account (5 cards) gives us access,
the webhook stores every payload as received and reads the amount from a few likely field names.
`TODO(cartbecart docs)` marks what to finish: the real field names and unit, verifying each deposit
through their API, and whether orders must be registered with them first. The webhook URL is
`https://<site>/api/payments/cartbecart/<CARTBECART_WEBHOOK_SECRET>/` (not behind the staging password).
Without cartbecart (`PAYMENT_PROVIDER=manual`) unpaid orders show under "needs action" in the panel.

## SMS (`backend/shop/sms.py`)

`SMS_BACKEND=kavenegar` uses Kavenegar's verify/lookup templates, which must be created in the
client's Kavenegar panel first: `ps-otp`, `ps-order-created`, `ps-reminder`, `ps-paid`,
`ps-payment-not-found`, `ps-shipped`, `ps-return-received`, `ps-refunded`, `ps-owner-new-order`,
`ps-owner-review`, `ps-owner-forwarder` (wording and tokens in `MESSAGES`). Every SMS is logged
(panel → Logs), OTP codes hidden.

## Staff panel (`/panel`)

Phone-first: Today (counts, what needs action, last automatic match), Orders (queues, search by code,
mobile, name or tracking code), the order page (approve/reject payment, prepare, ship, deliver, cancel,
print, note, history, its SMS), Returns, Store (cards, price, fees, timings, contact details, the
Enamad code), Texts (policy pages and FAQ, light markup) and Logs (deposits, SMS, who changed what).

Roles (`manage.py setup_roles`, every deploy): **Staff** ship and handle returns; **Owners** also approve
and reject payments, cancel, record refunds and edit the store. Create people in `/admin/` → Users and
add them to a group. Sign-in lasts two weeks, 10 attempts per 15 minutes per address.

## The hero and the 3D bag (`frontend/src/islands/home.ts`, `frontend/src/bag3d/`, `frontend/src/islands/bag3d.ts`, `tools/build_model.py`)

The home page opens with the bag in use, as a campaign page: six photos (`views.LOOK`, the originals
in `media/source-photos/look/`, the site's copies 160, 600 and 1200 px wide in `public/images/look/`),
one at a time over the whole first screen, a large line at the bottom over a dark fade with the price
and the buy button, and the photos as thumbnails beside it (Amir's pick of three designs, 2026-10-18).
The header lies over the photo, see-through until the hero scrolls away (`data-header="clear"`). Each
photo has a crop point for tall screens and one for wide ones, where only a band of the tall photo
shows. A bar under each thumbnail fills over 6 s, then the next photo fades in while the last drifts
slowly closer. It waits while the thumbnails are pointed at, keyboard focus is in the hero, it's touched
or off screen; the pause button stops it, and with reduced motion it never moves by itself. A swipe
anywhere on the hero, the thumbnails, or the arrow keys on them move it (right to left: the next photo
is to the left). Without JavaScript the first photo stays.

The 3D bag is the next section, **جزء به جزء** (`#parts`): a tab per side (روبه‌رو، کنار، پشت), the
side's numbered parts listed beside the bag, the same numbers pinned on it (`views.PARTS`: each part's
point on the model and the way that surface faces; a pin hides when its side turns away or it leaves the
stage). A tab turns the bag to that side (`VIEWS` in `bag3d/scene.ts`), a tapped row or pin turns it
toward the part, and people can drag it round (sideways on phones; vertical swipes still scroll). The
lock's numbers sit beside the module with lines to its parts, kept apart as the view changes. The
fingerprint sensor's light turns green on the lock's side.

The bag takes the colour picked on the page (the dots in the hero and beside the bag move together):
`BagScene.setColor` with the colour's swatch from the panel. The baked texture comes from photos of the
black bag, so every colour, black included, is drawn as a tint of it: the leather's colour times the
photo's light and dark relative to its median (softened, so the grain, seams and pocket lines stay but
the photo's lighting doesn't blotch), while pixels far brighter than the leather (the brand plate, the
metal) keep the photo's own colour. The zipper tape is a dark shade of the leather; the modelled lock,
teeth and far-end hardware carry two looks each (`finish` in `details.ts`): gunmetal on black, as on
WiWU's side photo, and silver on the lighter colours, as on their brown and silver-white bags. A colour
added in the panel tints the bag the same way, from its swatch.

Devices with WebGL2 (and no data saver, 2 GB+ memory) get the 3D: plain three.js, loaded as a separate
chunk (170 KB gzipped), plus the model (`public/models/alpha.glb` 720 KB, `alpha-mobile.glb` 300 KB). It
loads once the page has (the hero's photos come first) and the section is about a screen away.

- **While it loads:** the stage is `[data-pending]`: a thin line shows the download.
- **The photos are the backup.** Each side's photo with the same numbers (the earlier parts diagram)
  shows on devices without the 3D, and when it fails or takes over 6 s.
- **No zoom, no turning by itself:** the pins stay readable; the mouse wheel scrolls the page.
- **No fade at the canvas edge:** it read as a white ring.
- **Framing:** each side's view, and a tapped part's, keeps the whole bag and its shadow inside the
  stage (a closer look cut it off at the edges).
- **Reduced motion:** no camera glides.
- **Pin positions** came from `window.__bag.debugSnap(at, normal)` (development only), which finds the
  model's surface under a rough point. Re-check them after rebuilding the model (`tools/dev/shots.mjs`).

The model is built from the client's three photos, checked against them view by view:

1. **Shape**: Hunyuan3D-2mv made it from the three photos (`tools/ai_shape/`, results in `media/3d/ai/`,
   compared in `previews/contact-sheet.jpg`; the textured AI results were unusable).
2. **Masks** (`tools/photo_masks.py`, rembg): which pixels of each photo are bag → `media/3d/photos/`.
3. **Cameras**: where the phone was for each photo → `media/3d/cameras.json`, overlays in `media/3d/fit/`.
   `tools/fit_cameras.py` starts from features marked on both photo and shape (snap, pocket pull, logo
   plate corners, lock module) and refines until the shape's outline matches the photo's;
   `tools/refine_cameras.py` polishes all three (the side one on its outline only: its features sit on
   the AI's own, misplaced lock module). Outline overlap: back 0.979, front 0.979, side 0.968.
4. **Proportions** (`tools/fit_proportions.py`): the height and depth the three photos agree on best.
   The retailers' sizes disagree (24x14x6 to 26x17x7 cm); at 25 cm wide the photos give about
   14.2 x 7.7 cm.
5. **Details** (`tools/details.py`): what the AI shape blurs and the photos have too few pixels for, so
   the page models it (`frontend/src/bag3d/details.ts`):
   - the lock module, traced in the side photo (outline, cap with the pull's slot and latch, groove,
     light window, sensor glass and frame) and projected through the fitted camera onto its face;
   - the zipper: tape and interlocked teeth (2.4 mm apart) along the seam, up the lock end, over the
     top, down the far end to the pull tab;
   - the far end's ring and pull tab, triangulated from the front and back photos.
6. **Model** (`tools/build_model.py` + `tools/bake.py`): cleans and decimates the shape, gives it the
   photos' proportions, presses the AI's blurry versions of the details flat (and smooths away the
   bracket it invented at the far end), pulls the front onto a smooth fitted surface (taut, as on
   WiWU's studio photos; the AI shape rippled there), unwraps it (xatlas), projects the
   photos onto it (each texel from the photos that see it head-on and unblocked, colour-matched),
   sorts faces into leather / front panel / zipper / metal and compresses it (meshopt, JPEG texture):
   `alpha.glb` 720 KB, `alpha-mobile.glb` 300 KB. The `.json` beside each holds the details' measurements,
   hotspot anchors (unused since the pins moved to `views.PARTS`) and the leather grain's repeat.
7. **Check** (`node tools/compare.mjs`, dev servers running): renders the site's 3D bag from each photo's
   camera, the same size as the photo, to lay over it; `python tools/dev/compose.py` puts them in a
   photo | render | blend sheet. `tools/dev/orbits.mjs` renders close-ups (lock, zipper from above, far
   end), `tools/dev/shots.mjs` screenshots each side and tapped part in `#parts`, `tools/dev/overflow.mjs`
   checks phone width.
   All write to `media/3d/compare/` (not in git).

The front, back, top and lock end come from the photos; the lock, zipper and far-end hardware are
modelled to their measurements. **The bottom and the far end's leather are in no photo**, so they are
plain black leather; photos of those sides would make them exact (add them to the masks and cameras,
rebuild). Venvs: `tools/requirements-rembg.txt` for the masks and cutouts, `tools/requirements.txt` for
the rest (Python 3.12).

## Look (`frontend/src/site.css`, `frontend/src/islands/home.ts`)

"Instrument", picked on 2026-10-15 from two directions built around the 3D bag: the bag as a precise
object on an aluminium-grey bench, like a hardware catalogue. Cool greys and off-black; primary buttons
are ink. One signal colour, the sensor's green: `signal` for lights (`.led`: in stock, the view on
screen, a step), `accent` for done (paid, a completed step, an OK notice). Vazirmatn for text; Vazir
Code, its monospace sibling, for the figures and Latin in labels and readouts (`font-mono`,
`.readout-label`); its `@font-face` leaves out the Persian letters and spaces, which fall through to
Vazirmatn, since Persian set in a monospace stretches and reads as broken. Both self-hosted. (Readex
Pro was tried first: Fontsource's copy has no ی ک گ پ, so words fell apart on phones.) Corners 4px.
The panel and the other pages share these tokens.

Each home section has its own ground, so moving down the page reads as moving between parts: the hero
on aluminium grey (`page`), the parts on a light table (`raised`), the lock on ink, the specs on
`steel`, buying on `graphite` with the bill in white, the questions on grey, a closing band in signal
green, and an ink footer. No white glows behind the bag. On phones the menu is a solid ink panel under
the header (outside it, since the header's blur would trap a fixed panel), with the buy button at the
bottom; the page doesn't scroll under it, and Escape closes it.

The home page, after the hero and the parts (above):
- **Lock** (`#try`, the one dark block): what the lock does in three readouts (10 fingerprints, about
  half a second, USB-C), and a drawing of the real module. Holding it for half a second (the lock's own
  speed) fills the print and lights the status light; letting go early asks again. It reads nothing, it
  only times the press. Works by keyboard (hold Space or Enter).
- **Specs**: the size drawn on the front and side photos over a centimetre mat (`.cm-grid`, `--cm` per
  breakpoint), then the specs as cells.
- **Buying**: the steps on a rail beside a sample bill that explains the odd amount (`.receipt`, printed
  in as it scrolls into view).

Motion is CSS: scroll-driven where the browser has it, nothing otherwise, nothing with reduced motion.

## Colours (`shop.models.Color`, panel → فروشگاه → رنگ‌ها)

The bag comes in black, brown (قهوه‌ای) and silver-white (سفید), all at the product's price, all on
show since 2026-10-19 (migration 0003; Amir's call). Each colour has a name, a swatch (#rrggbb, the
leather's colour on WiWU's photos, which the 3D bag is tinted to), a photo (`images/colors/*.webp`,
`tools/studio_images.py`) and two switches: *shown on the site* and *in stock*. While only one colour is
shown nobody is asked and every order gets that colour. With two or more shown:

- the hero and the 3D section show the swatches (`shop/color_picker.html`, `islands/home.ts`), moving
  together, and the 3D bag turns that colour;
- the pick rides along to checkout as `?color=`, where the buyer can change it and the summary shows
  that colour's photo;
- sold-out colours are visible but can't be picked.

`orders.pick_color` checks the pick before the SMS code is used up. Orders keep the colour's name as it
was (`color_name`), which the panel, the order page and the packing slip show. A colour with orders is
hidden rather than deleted. New colours start hidden: add the photo first, then show them. The hero's
lifestyle photos are of the black bag only.

## Load and caching

See [LOADTEST.md](LOADTEST.md) (2026-10-18). The home and policy pages are cached for 60 s in the
`pages` database cache (`shop/pagecache.py`), which is off in development. Any save of the product, a
colour, the settings, a card, an FAQ or a page empties it. Each page then costs about 2 ms of CPU
instead of about 26 ms. A migration's data changes don't send those signals, so after a deploy that
changes content, empty it by hand: `manage.py shell -c "from django.core.cache import caches;
caches['pages'].clear()"`.

Images and 3D models are cached for a week (nginx `expires 7d`, ArvanCloud for images). In production
their addresses carry a hash of the file's content (`{% asset %}` adds `?v=`, `templatetags/vite.py`), so a
file replaced under the same name is fetched again.

## Pages and SEO

Django renders every page, so search engines, Torob and Telegram/WhatsApp previews see the product,
price and FAQ (with `Product` and `FAQPage` JSON-LD). `SITE_NOINDEX=True` (staging) adds noindex
everywhere and a blocking robots.txt. Policy pages (`/p/<slug>/`) are edited in the panel; text in
[brackets] waits for the client (warranty, what happens when the lock's battery is empty, the card
holder's name) and must be filled before applying for Enamad.

## Deploying (Nisatech server, next to nisatech.org, nisatak.com and contech)

```bash
scp -r deploy amir@185.231.180.92:purseshop-deploy
ssh -t amir@185.231.180.92 'sudo DOMAIN=<host> STAGING=1 bash purseshop-deploy/server-setup.sh'
DOMAIN=<host> bash deploy/deploy.sh
```

Staging runs at **https://shop.nisatech.org** (2026-10-15): set up without `STAGING=1` (open, no
password, Amir's choice), DNS on ArvanCloud (A record `shop` → 185.231.180.92, CDN on, origin over
HTTP; nisatak.com's own HTTPS answers on this server's port 443). `amir` can't sudo, so the root setup is
run by the server admin; deploys need no root. With an https `PUBLIC_URL`, Django sends http visitors to
https (`SECURE_SSL_REDIRECT`).

gunicorn on 127.0.0.1:8030, `/srv/purseshop`, its own system user. The first deploy writes
`backend/.env` with staging defaults (SMS printed to the journal, manual payments); edit it for the
real domain, Kavenegar and cartbecart. Each deploy backs up the database (last 30 kept). Buyers'
transfer screenshots are in `backend/private/`, never served by nginx, only through the panel.

## Still to do

- The 3D model: photos of the bottom and the far end (no photo shows them yet) and a sharper front
  photo would make every side exact (README, "The hero and the 3D bag").
- cartbecart: finish `payments.py` with their docs.
- The client's answers (PLAN.md §11): name, domain, cards, SMS account, Enamad details, specs, warranty.
