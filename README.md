# PurseShop

Working name until the client picks one (see [PLAN.md](PLAN.md), the interview and all the decisions).
An online store for one product, the WiWU Alpha fingerprint-lock clutch («کیف دستی ویوو آلفا»; black and
brown, 14.1M toman), in
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

1. **Checkout** (`/checkout/`): name, mobile, province/city, address, postal code, Pishtaz (free) or
   Tipax (paid by the buyer on delivery, پس‌کرایه: `StoreSettings.tipax_on_delivery`, copied onto the order),
   "gift: no price in the box". The mobile is confirmed with a 5-digit SMS code (5 minutes, 5 tries;
   one code a minute and 5 an hour per phone, 15 an hour per address, so the SMS credit can't be drained).
2. **The amount**: price + shipping + a small extra so a bank deposit points at exactly one order. The
   buyer pays the extra (decided 2026-10-14). With cartbecart it's their **1–999 rials**, so the amount
   is shown, copied and texted in rials; without, the shop picks **1–999 tomans** no open order (or one
   expired in the last 48 h) has. Price, fee and card are copied into the order: later changes don't touch it.
3. **The card**: with cartbecart, the card marked default in their dashboard (they say which, with its
   holder; the bank's name comes from the same card in the panel, or its first six digits); without, the
   panel's active card used least recently. The order page shows it, the holder's name, the exact amount
   with copy buttons, and the countdown (cartbecart's expiry, or the panel's payment minutes). It polls
   every 5 s and checks again the moment the buyer comes back from their bank app (in-app browsers reload pages).
4. **Confirmation**: cartbecart sees the deposit SMS and sends a signed event → the order is paid (SMS
   to buyer and owner). With `PAYMENT_PROVIDER=manual`, staff approve it in the panel.
5. **"I've paid"**: the buyer can send the transfer reference, the last 4 card digits, the time and a
   screenshot → *needs review* → SMS to the owner → approve or reject in the panel.
6. **Late money**: cartbecart still matches a deposit for an hour after the countdown ends, and the
   order then turns paid. A deposit that doesn't quite match goes to *needs review* (decide in their
   dashboard); one for no order is in their dashboard's manual review. Nothing is dropped.
7. **The minute timer** (`manage.py tick`, systemd timer): one reminder SMS at minute 15, expiry when the
   countdown ends, and with cartbecart on, a status check of open orders (in case a webhook was missed)
   and an SMS to the owner if two orders in 3 hours ran out with no match (the forwarder phone is
   probably off).
8. **Shipping**: paid → preparing → shipped (tracking code → SMS) → delivered. The panel prints an address
   label and packing slip; a gift's slip has no prices.
9. **Returns**: 7 working days (Fridays skipped) from delivery, or from shipping + 3 days if never marked
   delivered. The buyer gives reason, Sheba (checked) and holder; staff mark it received, then the owner
   records the refund's transfer reference (SMS to the buyer).

Money is whole **rials** everywhere (bank SMS count in rials) and shown in tomans, except an amount to
pay that doesn't end in a whole toman (cartbecart's), which is shown in rials.

## cartbecart (`backend/shop/payments.py`)

Their REST API (docs in their dashboard → مستندات API; it needs the **Pro or Max** plan, a card set
**active and default** in their dashboard, and their forwarder app on the phone that gets that card's
bank SMS). `PAYMENT_PROVIDER=cartbecart` with:

- `CARTBECART_API_KEY`: `cb_…`, their dashboard → Settings → API key.
- `CARTBECART_WEBHOOK_SECRET`: their dashboard → Settings → Webhook → «ساخت کلید امضا» (shown once).
  The webhook address to enter there is `https://<site>/api/payments/cartbecart/` (https on 443 only;
  not behind the staging password).

How it runs: checkout registers the order (`POST /api/v1/public/orders`, our code as
`merchant_order_id`) and reads the card from their public `GET /api/v1/pay/<token>`; our own order page
shows it (their hosted pay page isn't used). Each change comes as a signed event (`X-CBC-Signature`,
HMAC-SHA256 over `timestamp.body`, at most 5 minutes old; repeats recognised by `event_id`):
`order.paid` → paid; `order.needs_review` → needs review (they're decided in **their** dashboard, and the
next event follows); `order.expired` → expired, or cancelled with an SMS to the buyer when the reason is
a rejection; `order.cancelled` → cancelled. The minute timer asks for the status of open orders, so a
missed webhook is caught within a few minutes. Every event is in the panel → Logs → payments.

If they refuse an order (no default card, plan, monthly quota, key), the buyer sees «پرداخت همین حالا
آماده نشد», their SMS code still works for another try, and the owner gets an SMS (once an hour).

`manage.py cartbecart_check` checks the key and plan and prints the webhook address;
`manage.py cartbecart_check --test 10000` also registers a 10,000-toman test order (not a shop order) to
pay from your own card: once paid, the panel's payments log shows it as a test, which proves the webhook.
Without cartbecart (`PAYMENT_PROVIDER=manual`) unpaid orders show under "needs action" in the panel.

## SMS (`backend/shop/sms.py`)

`SMS_BACKEND=kavenegar` with `KAVENEGAR_API_KEY` sends each message one of two ways (Kavenegar's REST
API over plain HTTPS; their Node SDK is the same calls, so no package is needed):

- **Plain text** (`sms/send`) from the line `KAVENEGAR_SENDER` (`2000660110`, empty for the account's
  default line), with the texts in `MESSAGES`. Works as soon as the account has credit.
- **Templates** (`verify/lookup`) for the kinds listed in `KAVENEGAR_TEMPLATES` (`otp,paid`, or `all`).
  They must be created and approved in the Kavenegar panel first (the Advanced plan): `ps-otp`,
  `ps-order-created`, `ps-reminder`, `ps-paid`, `ps-payment-not-found`, `ps-shipped`,
  `ps-return-received`, `ps-refunded`, `ps-owner-new-order`, `ps-owner-review`, `ps-owner-forwarder`,
  `ps-owner-payment-down` (wording and tokens in `MESSAGES`). They also reach numbers that block advertising SMS, so move at
  least `otp` to a template before launch.

`manage.py sms_check` shows the key's credit and which messages go how, sending nothing;
`manage.py sms_check 09xxxxxxxxx` also texts that number a test code (12345). Every SMS is logged
(panel → Logs), OTP codes hidden; a refusal is logged with Kavenegar's reason (no credit, bad key…).

## Staff panel (`/panel`)

Phone-first: Today (counts, what needs action, last automatic match), Orders (queues, search by code,
mobile, name or tracking code), the order page (approve/reject payment, prepare, ship, deliver, cancel,
print, note, history, its SMS), Returns, Store (cards, price, fees, timings, contact details, the
Enamad code), Texts (policy pages and FAQ, light markup) and Logs (deposits, SMS, who changed what).

Roles (`manage.py setup_roles`, every deploy): **Staff** ship and handle returns; **Owners** also approve
and reject payments, cancel, record refunds and edit the store. Create people in `/admin/` → Users and
add them to a group. Sign-in lasts two weeks, 10 attempts per 15 minutes per address.

## The hero and the 3D bag (`frontend/src/islands/home.ts`, `frontend/src/bag3d/`, `frontend/src/islands/bag3d.ts`, `tools/build_model.py`)

**The 3D bag is off the page since 2026-10-23** (Amir: a picture of each bag instead). جزء به جزء shows every
model in every colour (`views.bag_pictures`: the Alpha in black and brown, the two-zipper bag in black and
brown), each on a light tile with its price, opening checkout for that bag; the Alpha's parts are listed
beside them, a tab per side. The page no longer loads `islands/bag3d.ts` (out of the build's inputs in
`vite.config.ts`), so no three.js and no model download. Everything below about the 3D bag still describes
the code, the models and the tools, which stay in the repo for if it comes back: add the island back to
the build and to `home.html`, and the stage (git history, `home.html` before 2026-10-23).

The home page opens as a campaign page (Amir's pick of three designs, 2026-10-18): seven pictures, one
at a time over the whole first screen (`views.LOOK`, the originals in `media/source-photos/look/`, the
site's copies 600 and 1200 px wide in `public/images/look/`). Amir's photo of the man with the bag opens
it, for 3 seconds only (2026-10-21). Five are posters of the bag alone: black, both versions in black
(the two-zipper bag beside the Alpha, 2026-10-23), black and brown side by side as mirror images (Amir,
2026-10-21), brown, both versions in brown (WiWU's studio renders on a dark studio sweep,
`tools/hero_slides.py`, 2026-10-20; WiWU's black render is from another angle, so the black is their
brown render made black, `tools/black_render.py`; silver dropped 2026-10-21). Between them, Amir's other
photo, the plate in hand. A large line at the bottom over a dark fade, the price and a compact buy button; nothing else (Amir,
2026-10-20: the thumbnails, pause button and counter crowded it). The header lies over the picture,
see-through until the hero scrolls away (`data-header="clear"`). Each picture has a crop point for tall
screens and one for wide ones, where only a band of the tall picture shows. After each picture's time
(6 s, or its own `--slide-time`: `time` in `views.LOOK`) the next fades in while the last drifts slowly
closer. It waits while keyboard focus is in the hero, it's touched, off
screen or in a background tab, and with reduced motion it never moves by itself. A sideways swipe moves
it (right to left: the next picture is to the left). Without JavaScript the first picture stays.

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
the photo's lighting doesn't blotch), while pixels far brighter than the leather (the pulls, the snap)
keep the photo's own colour. The zipper tape is a dark shade of the leather; the modelled lock,
teeth and far-end hardware carry two looks each (`finish` in `details.ts`): gunmetal on dark leather (black
and WiWU's coffee brown, as on their renders) and silver on light (their silver-white bag). The brand
plate stays the same grey satin metal on every colour, as on all three of WiWU's photos. A colour
added in the panel tints the bag the same way, from its swatch.

Devices with WebGL2 (and no data saver, 2 GB+ memory) get the 3D: plain three.js, loaded as a separate
chunk (170 KB gzipped), plus the model (`public/models/alpha.glb` 732 KB, `alpha-mobile.glb` 324 KB). It
loads once the page has (the hero's photos come first), the section is about a screen away and the hero
has moved past its opening photo, or the visitor has scrolled: starting the 3D holds the page for a second
or more, and the opening photo's 3 seconds stretched to about 5 (2026-10-21).

- **While it loads:** the stage is `[data-pending]`: a thin line shows the download.
- **The backup is a picture of the bag in the picked colour** (`images/colors/`, swapped by the colour
  dots; Amir, 2026-10-20), the numbered list beside it as before. It shows on devices without the 3D, when
  it fails or takes over 6 s, when a frame draws nothing (`BagScene.drawsTheBag` reads the middle of the
  first frame back: some GPUs fail quietly and leave a blank stage) and when the browser drops the GPU.
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
   - the far end's ring and pull tab, triangulated from the front and back photos;
   - the brand plate: its corners in the front photo projected onto the finished front
     (`details.logo_plate`, which `build_model.py` runs once the front is pulled taut), square to the
     bag, 17.9 x 19 mm. Its face (`frontend/src/bag3d/logo.ts`) is drawn in the browser: WiWU's emblem
     (the tall hexagon round an i) and name, traced from the logo on wiwu.com and placed as on the plate
     in WiWU's front photo, raised (a normal map), with the raised parts a little brighter so they still
     read where the plate is a few pixels across. The front photo's own plate is painted out before
     baking (`bake.painted_out`), so none of its blurry pixels show round the modelled one.
6. **Model** (`tools/build_model.py` + `tools/bake.py`): cleans and decimates the shape, gives it the
   photos' proportions, presses the AI's blurry versions of the details flat (and smooths away the
   bracket it invented at the far end), pulls the front onto a smooth fitted surface (taut, as on
   WiWU's studio photos; the AI shape rippled there), unwraps it (xatlas), projects the
   photos onto it (each texel from the photos that see it head-on and unblocked, colour-matched),
   sorts faces into leather / front panel / zipper / metal and compresses it (meshopt, JPEG texture):
   `alpha.glb` 732 KB, `alpha-mobile.glb` 324 KB. The `.json` beside each holds the details' measurements,
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
`steel`, buying on `graphite` with the bill in white, the questions on grey, the closing "pick a colour"
section on a light table (the bag in each colour side by side, each opening checkout in that colour; it
replaced a band in signal green, 2026-10-20), and an ink footer. No white glows behind the bag. On phones the menu is a solid ink panel under
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

The bag comes in black and brown (قهوه‌ای), both at the product's price, on show since 2026-10-19
(migration 0003; Amir's call). The silver-white (سفید) went on 2026-10-21: the client doesn't have it
(migration 0006; it is hidden instead if an order has it). Each colour has a name, a swatch (#rrggbb, the
leather's colour on WiWU's renders, which the 3D bag is tinted to; the brown is their coffee brown since
migration 0005), a picture (`images/colors/*.webp`, `tools/color_photos.py`: both turned the same way,
on a transparent background) and two switches: *shown on the site* and *in stock*. While only one colour is
shown nobody is asked and every order gets that colour. With two or more shown:

- the hero and the 3D section show the swatches (`shop/color_picker.html`, `islands/home.ts`), moving
  together, and the 3D bag turns that colour;
- the pick rides along to checkout as `?color=`, where the buyer can change it and the summary shows
  that colour's photo;
- sold-out colours are visible but can't be picked.

`orders.pick_color` checks the pick before the SMS code is used up. Orders keep the colour's name as it
was (`color_name`), which the panel, the order page and the packing slip show. A colour with orders is
hidden rather than deleted. New colours start hidden: add the photo first, then show them. The hero's
lifestyle photos are of the black bag only; its bag-only slides show black and brown.

## The two-zipper model (WiWU Phantom Pro, `seed_store.PHANTOM`, `views.lineup`)

The client also has WiWU's two-zipper bag, in black and brown (Amir, 2026-10-21): the Phantom Pro
(«کیف دستی دو زیپ ویوو فانتوم پرو»), 28 × 12.5 × 9 cm, about 800 g, two compartments, a side handle, the same
kind of fingerprint lock. It is a second `Product` (`phantom-pro`), with its own price, specs and colours;
the Alpha stays the main bag (`PRODUCT_SLUG`): the hero, the specs and the search data are the Alpha's.

- **Price: 16,500,000 toman** (Amir, 2026-10-23; migration 0007, and `seed_store` for a new store). A price
  of 0 keeps it off the home page and out of checkout, and an order for it is refused (`unavailable`); the
  Alpha's price can never be 0.
- **On the page:** a poster of both versions per colour in the hero; its two pictures beside the Alpha's in
  جزء به جزء; the closing section's card per colour shows both versions in one picture
  (`views.colour_cards`, `tools/duo_pictures.py`) with each one's price; and its own section before the closing one (`#phantom-pro`, dark: what's different, a few
  spec rows from `views.HIGHLIGHTS`, the price, each colour on a light tile opening
  `/checkout/?product=phantom-pro&color=<id>`).
- **Checkout asks which version** (مدل: تک‌زیپ or دو زیپ, Amir 2026-10-23), starting from the one the link
  asked for (`?product=`, else the Alpha); switching keeps the colour by its name, and the summary beside
  the form (name, price, the bag in that colour) and the bill follow. The order is placed for the version
  picked (`product` in `/api/orders/`).
- **Panel → فروشگاه:** with two models, a switch at the top picks which one the colours and the
  product fields below are for; the list says which has no price yet.
- **Pictures:** `images/colors/phantom-<black|brown>.webp` from `tools/phantom_photos.py`. The only clean
  studio render found was of its tan bag (a reseller's, `media/source-photos/wiwu/phantom-tan.png`; other
  stores watermark theirs), so its leather is made each colour, as `tools/black_render.py` did for the
  Alpha: the deep brown of Amir's screenshot of the bag, and a neutral black. The render's own cut-out is
  kept (`phantom-<colour>.png`, transparent): cut out from white, it showed a pale rim on the dark posters.

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
[brackets] waits for the client (the card holder's name, contact details) and must be filled before
applying for Enamad. The warranty, the battery and shipping came from the client on 2026-10-20 (migration
0004).

## Deploying (Nisatech server, next to nisatech.org, nisatak.com and contech)

```bash
scp -r deploy amir@185.231.180.92:purseshop-deploy
ssh -t amir@185.231.180.92 'sudo DOMAIN=penolinshop.com REDIRECT="www.penolinshop.com shop.nisatech.org" CERT=1 bash purseshop-deploy/server-setup.sh'
DOMAIN=penolinshop.com bash deploy/deploy.sh
```

Staging runs at **https://penolinshop.com** (since 2026-10-24; at https://shop.nisatech.org from
2026-10-15): set up without `STAGING=1` (open, no password, Amir's choice), DNS on ArvanCloud (A records
`@` and `www` → 185.231.180.92, meant to have the CDN on). `REDIRECT` lists the other names that send
visitors to the shop's address, keeping the path, each with its own certificate: `www.penolinshop.com`
and the old `shop.nisatech.org`. Pass the same list on every re-run; a name left out stops redirecting.

**Moving to another domain:** point its DNS here, re-run `server-setup.sh` with the new `DOMAIN` and the
old one added to `REDIRECT`, then in the server's `backend/.env` set `DJANGO_ALLOWED_HOSTS` and
`PUBLIC_URL` to the new name (the deploy refuses to run while `PUBLIC_URL` doesn't match `DOMAIN`),
deploy, and empty the page cache (the pages hold the old address).

**The site also answers HTTPS itself**, with its own Let's Encrypt certificate
(`CERT=1`; certbot.timer renews it and reloads nginx): on 2026-10-20 Arvan's proxy was off for the whole
nisatech.org zone, browsers came straight to the server, and nginx answered them with its only HTTPS
site, nisatak.com. So it works with the proxy on or off and with either origin protocol. Every deploy
then asks the server itself for `https://<host>/` and fails loudly if the certificate is missing, wrong or
within 21 days of running out. The root setup needs sudo (`amir` has it since 2026-10-20; before, the
server admin ran it); deploys need no root. With an https `PUBLIC_URL`, Django sends http visitors to
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
