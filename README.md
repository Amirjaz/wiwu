# PurseShop

Working name until the client picks one (see [PLAN.md](PLAN.md), the interview and all the decisions).
An online store for one product, the WiWU Alpha fingerprint-lock clutch (black, about 10M toman), in
Persian. Payment is card-to-card to the owner's cards, confirmed automatically from the bank's deposit
SMS by cartbecart.com, or by staff in the panel.

| Folder | What |
| --- | --- |
| `backend/` | Django 5.2 (Python 3.12), SQLite. Renders the pages; JSON API under `/api/`; Django admin at `/admin/` |
| `frontend/` | Vite + React 18 + Tailwind v4 *islands* on Django's pages (checkout, order page, lookup) and the staff panel at `/panel` |
| `deploy/` | nginx site, systemd units (gunicorn + a minute timer) and deploy scripts for the Nisatech server |
| `media/` | the client's photos, the background-removed cutouts, 3D sources (not served) |
| `tools/` | `cutout.py`/`fix2.py` (background removal), `web_images.py` (the site's product images) |

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

## The 3D hero (`frontend/src/hero/`, `frontend/src/islands/hero.ts`, `tools/build_model.py`)

The home page opens with a tour: the bag stays pinned (beside the text on desktop, on top on phones)
while five stops scroll past: the hero, the lock, the back pocket, the wrist strap, the leather. Each
stop has a photo, so it all works without 3D. After the page has loaded, devices with WebGL2 (and
no data saver, 2 GB+ memory) get the 3D bag instead: plain three.js, loaded as a separate chunk
(158 KB gzipped) plus the model (`public/models/alpha.glb` 755 KB, `alpha-mobile.glb` 320 KB).
At the hero people can drag it (sideways on phones; vertical swipes still scroll) and open three
hotspots (text in `views.HOTSPOTS`); further down the camera moves to each stop. The fingerprint
sensor's light turns green at the lock stop. Reduced motion: no turning by itself, no camera glides.

The model looks like the client's bag because it is wrapped in their photos:

1. **Shape**: Hunyuan3D-2mv made it from the three photos (`media/3d/ai/`, compared in
   `previews/contact-sheet.jpg`; the textured AI results were unusable).
2. **Masks** (`tools/photo_masks.py`, rembg): which pixels of each photo are bag → `media/3d/photos/`.
3. **Cameras** (`tools/fit_cameras.py`): where the phone was for each photo, from features marked on
   both photo and shape (snap, pocket pull, logo plate corners, lock module, sensor) and then refined
   until the shape's outline matches the photo's (outline overlap 0.95–0.98) → `media/3d/cameras.json`,
   overlays in `media/3d/fit/`.
4. **Model** (`tools/build_model.py` + `tools/bake.py`): cleans and decimates the shape, unwraps it
   (xatlas), projects the photos onto it (each texel from the photos that see it head-on and unblocked,
   colour-matched so they blend), sorts faces into leather / zipper / metal parts, fixes the proportions
   to 25 x 15.5 x 6.5 cm and compresses it (meshopt, JPEG texture): `alpha.glb` 755 KB,
   `alpha-mobile.glb` 320 KB. The `.json` beside each says where the sensor's status light is (from
   the side photo) and how often the page's faint leather grain repeats.

The front, back, top and lock end (with the real sensor) come from the photos. **The bottom and the
far end are in no photo**, so they get plain black leather; photos of those sides (and a sharper one
of the front) would make them exact: add them to the masks and cameras and rebuild. Rebuild:
`python tools/photo_masks.py` (rembg venv), then `python tools/fit_cameras.py` and
`python tools/build_model.py` (the 3D venv: numpy, scipy, opencv-python-headless, trimesh,
fast-simplification, xatlas).

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

gunicorn on 127.0.0.1:8030, `/srv/purseshop`, its own system user. The first deploy writes
`backend/.env` with staging defaults (SMS printed to the journal, manual payments); edit it for the
real domain, Kavenegar and cartbecart. Each deploy backs up the database (last 30 kept). Buyers'
transfer screenshots are in `backend/private/`, never served by nginx, only through the panel.

## Still to do

- The 3D model: photos of the bottom and the far end (no photo shows them yet) and a sharper front
  photo would make every side exact (README, "The 3D hero").
- cartbecart: finish `payments.py` with their docs.
- The client's answers (PLAN.md §11): name, domain, cards, SMS account, Enamad details, specs, warranty.
