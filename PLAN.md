# PurseShop — plan

Working name until the client picks one. An online store that sells **one product**: the WiWU Alpha
fingerprint-lock clutch, in black, at about 10M toman. The home page is the product page. Its hero is an
interactive 3D model of the bag, followed by a scroll tour of its features. Payment is card-to-card,
confirmed automatically by cartbecart.com. It runs on the client's own `.ir` domain, on the Nisatech
server in Iran behind ArvanCloud, with Enamad.

Interviewed with Amir on 2026-10-14 (22 Mehr 1405). No hard deadline: we ship when it's good. Enamad
still sets the order of work (see *Phases*).

---

## 1. Decisions

| Topic | Decision | Notes |
| --- | --- | --- |
| Domain | **Client's own `.ir`**, registered at IRNIC under the client's national ID | Enamad is issued to the domain's owner, so a `nisatech.org` subdomain can't get it. We still host it. Staging runs on a nisatech.org subdomain until the domain exists. |
| Store name | **None yet.** We send a shortlist of 8–10 with `.ir` availability checked, and the client picks | This blocks the domain and therefore Enamad, so it's the first task. Must not be "WiWU" or anything that sounds official. |
| Product | **One product, black only**, no variants | WiWU Alpha fingerprint-lock clutch. Imported and **unofficial** (not an authorized WiWU reseller). |
| Stock | **Not counted** (effectively unlimited) | Sold-out is handled by hand: a switch in the panel. |
| Price | **Manual**, one field in the panel | The price is copied into each order when it's created, so a price change never breaks a pending payment. |
| Payment | **Card-to-card only**, hard-wired, through **cartbecart.com** with **5 cards, all in the owner's name** | cartbecart reads the bank's deposit SMS and matches the exact amount. 5 cards needs the **Max plan, 440k toman/month** (Pro only allows 3). No gateway or installments planned. |
| Unique amount | **Offset added on top**: price + shipping + 1…999 toman, unique among open orders | See risk R1: the total ends up just above 10M toman. |
| Unpaid orders | **30-min window**, then the buyer can submit a transfer reference and screenshot → staff review | Late money goes to a *needs review* queue and is never dropped. One reminder SMS at minute 15. |
| SMS forwarder | **Dedicated always-on Android** at the shop, receiving all 5 cards' deposit SMS | If it goes silent, payments fall back to manual review. |
| Buyer identity | **Phone OTP at checkout**, no passwords | The OTP phone is also the key for order tracking and returns. |
| Shipping | **Iran Post (Pishtaz) and Tipax**, flat fees set in the panel | Staff paste the tracking code, and the buyer gets it by SMS. |
| Gifts | **"Gift: no price in the box"** checkbox only | The packing slip prints without prices, and the invoice goes to the buyer by SMS link. No separate recipient. |
| Returns | **7 working days** (e-commerce law art. 37), **buyer pays return postage**, unused, fingerprints wiped | Refunds are manual card-to-card or Sheba transfers. The buyer gives their Sheba, staff record the transfer reference. |
| Trust / social proof | **Nothing extra at launch**, beyond Enamad and clear policies | No Instagram embeds (Instagram is filtered in Iran). |
| Marketing | **Only the unpaid-order reminder SMS** | No discount codes or referral tracking at launch. |
| Staff alerts | **SMS to the owner** (new paid order, payment needs review) | Works during internet shutdowns. |
| Operator | **Unknown**, so roles are built anyway (owner / staff) and `/panel` is **phone-first** | Every payment approval and refund is logged with who did it. |
| Stack | **House stack: Django 5.2 + SQLite, React/Vite/Tailwind v4 islands**, nginx + systemd, frontend built locally | Django renders the real HTML (SEO, Torob, link previews). React handles the 3D, checkout, pay page and `/panel`. |
| Look | **"Instrument"** (chosen 2026-10-15 from two designs): aluminium grey, off-black, the sensor's green for state only, Vazirmatn + Vazir Code for figures, 4px corners, a different ground per section | Unisex. Light keeps the black bag readable. See README, *Look*. |
| 3D source | **AI image-to-3D from the 3 photos we have**, cleaned up in Blender | "Same bag, the color differences are lighting." Fallback: Blender blockout (see §5). |
| Hero | **Both**: drag-to-rotate + hotspots at the top, then a scroll-driven tour | One shared WebGL canvas. No AR. |
| Lock video | **None from the client** | Maker media may fill the gap (next row). |
| Maker info | **Find WiWU's listing; use specs and their media** | Using their media is a gray area for an unofficial reseller. The client accepts that. |
| Material copy | **Say what it is**: PU (artificial) leather, water- and scratch-resistant | Never «چرم طبیعی». |
| Logo plate on the model | **Keep it** (it's the real product) | Repaint it from the photo if the AI smears it. |

## 2. The product (from retailer listings; confirm with the client)

The logo plate reads **WiWU**. The product is the **WiWU Alpha Fingerprint Lock Clutch Bag**, sold across
the Middle East (Sharaf DG UAE ~293 AED; El Ryan, Zain Jordan, Xmart). Listings disagree with each other:

- Lock: fingerprint, up to **10 fingerprints**, unlocks in **~0.5 s**, rechargeable over **USB-C**.
- Material: **PU leather**, water- and scratch-resistant, microfiber lining. One listing claims genuine
  leather; we don't.
- Size: **~25 × 15.5 × 6.5 cm** (other listings: 24×14×6, 26×17×7). Needed for 3D scale. Measure the real bag.
- Colors sold by WiWU: black, blue, walnut. We sell black. Check the front photo: it reads navy when
  brightened, and WiWU *does* sell a blue one.
- A different "Alpha **Anti-Theft**" clutch has a 3-digit combination lock. Don't mix up their specs.

Still unknown and needed for the FAQ: what happens when the battery dies (is there a key or override?),
battery life, how to enroll and delete fingerprints, and the warranty (store-defined, since it's not official).

## 3. Architecture

```
PurseShop/
  backend/            Django 5.2, Python 3.12, SQLite (WAL)
    shop/             Product, Order, Payment, Shipment, ReturnRequest, Setting, AuditLog
    payments/         cartbecart adapter + webhook
    sms/              provider adapter (Kavenegar or sms.ir), templates, rate limits
    panel/            JSON API for /panel (pattern from Nisatak: resources.py per section)
    templates/        Django-rendered pages (home/product, legal pages, order tracking shell)
  frontend/           React 18 + Vite + Tailwind v4, Persian RTL; builds islands, not one SPA
    src/hero3d/       R3F canvas: hero + scroll tour
    src/checkout/     checkout form, OTP, pay page (polling)
    src/panel/        staff panel, loaded only on /panel
  media/              source photos, cutouts, 3D sources (.blend) — not served
  deploy/             nginx site, systemd unit, deploy.sh / remote-deploy.sh / server-setup.sh
  tools/              one-off scripts (photo cutouts)
```

- **Rendering:** Django templates output the full HTML for `/` (product, price, specs, FAQ, policies),
  with OpenGraph tags (Telegram and WhatsApp previews) and `Product` JSON-LD (price in IRR, availability).
  Vite builds separate entry points that mount on `data-island` elements. The server never needs Node,
  same as Contech and Nisatak.
- **Money:** stored as **integer rial** everywhere and shown in toman with Persian digits. Bank SMS
  amounts are in rial, so a toman/rial mix-up is the most likely bug here. Test it explicitly.
- **Iran-proofing:** self-host **everything**: the Vazirmatn and Vazir Code fonts; the three.js **Draco/meshopt decoders and
  KTX2 transcoder** (three's default decoder URLs point at gstatic.com); the HDRI. No Google Fonts,
  Analytics or reCAPTCHA.
- **Persian input:** normalize Persian/Arabic digits and letters in every input. Phone `09xxxxxxxxx`
  (also accept +98 / 0098 / Persian digits). Postal code 10 digits. Sheba `IR` + 24 digits with the mod-97
  check. Province and city from a fixed list. Jalali dates in the panel and SMS.

## 4. Checkout and payment (the critical path)

1. **Buy** → checkout: name, phone, province/city, address, postal code, shipping (Pishtaz / Tipax with
   price), "gift: no price in the box".
2. **OTP:** one SMS code (template-based "verify" API so it isn't blocked as advertising).
   **Rate limits** stop SMS-pumping abuse from draining credit: Iranian mobiles only, 1 per minute and 5 per
   hour per phone, plus a per-IP cap and a cooldown.
3. **Order created:** `awaiting_payment`, `amount = price + shipping + offset` (offset 1…999 toman, unique
   among open orders), `expires_at = +30 min`, short code like `PS-4F7K`. SMS to the buyer with a
   **resume link** (`/o/<code>`).
4. **Pay page** (`/o/<code>`, works after leaving Instagram/Telegram for the bank app and coming back):
   - the card number in 4-digit groups with a copy button, and **«به نام: [owner's name]»** so it matches
     the name the bank app shows;
   - the **exact amount** with a copy button and a clear "send exactly this, don't round" line;
   - a countdown, and a status that polls every 5 s.
5. **Confirmation:** cartbecart webhook → **re-check the payment through their API** (never trust the
   webhook body alone) → `paid` (idempotent). SMS to the buyer ("paid") and to the owner ("new order").
6. **Minute 15:** one reminder SMS with the resume link, if still unpaid.
7. **Minute 30 / no match:** the pay page switches to **"I've paid"**: transfer reference, time, last 4
   digits of the source card, optional screenshot → `needs_review` → SMS to the owner. Staff approve or
   reject in `/panel` (audited).
8. **Late or orphan money:** an expired order whose amount arrives later moves to `needs_review`, never
   silently lost. cartbecart's own "wrong amount / needs review" items are mirrored into the same queue.
9. **Fulfilment:** `paid → preparing → shipped` (tracking code → SMS) `→ delivered`. Packing slip and
   address label print from `/panel`, without prices if the gift flag is set.
10. **Returns:** `/return` → order code + OTP → reason, buyer's Sheba and account holder name →
    `return_requested → received → refunded` (staff enter the transfer reference) → SMS.

**cartbecart unknowns** (their docs are behind the login, so the client needs a **Max** account and
gives us API access first):
- Does the API assign a card per order, or do we? How does it rotate across 5 cards?
- Who makes the unique amount, them or us?
- Webhook signature/secret, retries, timeout, and whether amounts are in rial or toman.
- API mode vs their hosted "payment link". We prefer the API plus our own pay page, which handles the
  in-app-browser return.

The adapter lives in `payments/cartbecart.py`, written after reading the docs.

**Infra details for this path:**
- **Arvan:** exempt the webhook path from any challenge or "under attack" mode, or server-to-server POSTs
  get blocked.
- **Forwarder health:** the panel shows "last payment matched N min ago". Two expired unmatched orders in
  a row trigger an owner SMS ("is the forwarder phone on?").

## 5. The 3D hero

**Pipeline**
1. **Normalize the photos.** Match white balance and exposure of the three cutouts to the back photo
   (`media/cutouts/*-lifted.png` are already shadow-lifted).
2. **Generate.** Try multi-view first, front + back + side (Hunyuan3D-2mv or Tripo multiview), then
   single-image (TRELLIS / Hunyuan3D 2.x / Tripo / Meshy) from the best photo. Keep the best silhouette.
   Expect problems:
   - the photos are perspective three-quarter shots, not the clean orthographic views these models expect;
   - the second end of the bag, the top and the bottom are never seen, so the AI invents them.
3. **Blender cleanup** (most of the work):
   - **Shape:** scale to real dimensions; fix the silhouette and symmetry.
   - **Zipper:** if smeared, rebuild it as an array-modifier strip.
   - **Textures:** re-project the **logo plate and fingerprint module** from the photos. Add a CC0
     pebbled-leather normal map (ambientCG / Poly Haven) and roughness for sheen. The front face is
     smoother than the back.
   - Bake the textures.
   - **Fallback**, if the AI mesh is unusable: a Blender blockout of the rounded box, using the photos as
     reference (~1 day), textured the same way.
4. **Export.** GLB ≤ 40k triangles, optimized with `gltf-transform` (meshopt). Two versions: desktop
   (2K textures, ≤ 2.5 MB) and mobile (1K textures, ≤ 1.2 MB).
5. **Poster.** A still rendered from the hero's exact first camera (AVIF/WebP ≤ 120 KB), so the swap from
   image to canvas is invisible. Also one pre-rendered still per tour stop, for the fallback.

**Runtime** (React Three Fiber + drei, GSAP ScrollTrigger for the tour)
- **One canvas, pinned (sticky)** through the hero and the tour. The model loads once and there's only
  one WebGL context. That's important for the in-app browsers' memory.
- **Hero:** slow idle turn, drag to rotate, limited pinch zoom, and 3–4 hotspots:
  - the lock: 10 fingerprints, 0.5 s, USB-C;
  - the back zip pocket;
  - the wrist strap;
  - water-resistant PU.
- **Tour:** 4–5 camera stops scrubbed by scroll (front with logo → side with the lock → back pocket → strap
  → top zipper). Persian captions, RTL. Ends on the price and the buy button.
- **Light:** a small self-hosted studio HDRI and a soft contact shadow on a cream floor.
- **Load order:**
  - First: HTML, text, poster and the buy button.
  - After first paint / idle: the 3D JavaScript (a lazy chunk), then the GLB (mobile or desktop by
    screen and `deviceMemory`).
  - DPR capped at 1.5. Rendering pauses off-screen and in hidden tabs.
- **Fallbacks:** without WebGL2, with `prefers-reduced-motion`, with Save-Data, or if loading fails,
  show the poster plus the pre-rendered tour stills. The 3D must never block buying.
- **Maker media:** if WiWU's listing has a lock demo video or studio shots, use them for reference, and
  the video for the lock stop (self-hosted, muted loop).

## 6. Panel (`/panel`, phone-first)

- **Today:** orders needing action, the *needs review* queue, last matched payment.
- **Orders:** filters by status, order detail, approve/reject payment, tracking code, mark shipped,
  print slip/label, cancel.
- **Returns:** requests, buyer's Sheba (copy), mark received, record refund reference.
- **Settings:** price, shipping fees, sold-out switch, card holder display name, SMS on/off per
  template, policy texts and FAQ.
- **Roles:** owner (everything, money, refunds) and staff (fulfilment). Staff sign in like Nisatak
  (Django session, rate-limited). Django admin stays at `/admin/` as the fallback.
- **Audit log:** every payment approval, rejection, refund and price change, with user and time.

## 7. SMS

The client opens the SMS provider account (Kavenegar or sms.ir) in their own name. Transactional
templates:

| Recipient | Templates |
| --- | --- |
| Buyer | OTP, order created + resume link, reminder at 15 min, paid, shipped + tracking, return received, refunded |
| Owner | new paid order, payment needs review, forwarder seems silent |

Templates may need provider approval, so submit them early.

## 8. Enamad path

1. The client picks a name → we check the `.ir` → **the client registers it at IRNIC** under their own
   NIC handle.
2. DNS on ArvanCloud (CDN proxy on, like the other hosts) → nginx site on the Nisatech server.
3. The **minimal real store goes live** on the domain:
   - real price, working checkout;
   - pages: about, contact (address, phone, email), terms, returns, privacy, shipping, FAQ;
   - the photos are enough for now, the 3D comes later.
4. The client applies at enamad.ir:
   - national ID;
   - a **mobile registered under their own national ID** (checked);
   - email and address with postal code (often verified by post, 1–2 weeks).
5. We place the domain-verification code, then paste the **seal snippet exactly as Enamad gives it**,
   in the footer and next to the buy button.
6. After Enamad: an optional Torob listing and feed.

## 9. Phases

No hard date. Estimates are our build hours at Claude Code speed. Waiting on the client, cartbecart, the
SMS provider and Enamad comes on top and is listed separately.

| Phase | What | Our hours | Waiting on others |
| --- | --- | --- | --- |
| **0. Client setup** (blocks everything) | Name shortlist with `.ir` availability · client picks → `.ir` registration · cartbecart **Max** account + API access + dedicated Android forwarder · SMS provider account + template approval · Enamad address and mobile · answers to §11 | ~2h | client: days; IRNIC: 1–2 days |
| **1. Store core** | Repo + deploy (staging subdomain with basic auth and noindex) · models · Django-rendered home/product with photo gallery · checkout + OTP + cartbecart + pay page + review flow · panel · SMS · legal pages · returns | ~24–30h | cartbecart docs/API key |
| **2. Go live + Enamad** | Move to the `.ir` domain, smoke-test a real 10M payment end to end (then refund it), apply for Enamad | ~3h | Enamad review + postal check: 2–4 weeks |
| **3. 3D hero** (in parallel with the Enamad wait) | AI generation → Blender cleanup → GLB + posters → hero + hotspots → scroll tour → fallbacks → phone testing (Instagram/Telegram in-app browsers, a low-end Android) | ~16–20h | — |
| **4. After Enamad** | Seal on the site · Torob feed · launch | ~2h | — |

Total build is roughly **47–57h**. The Blender cleanup is the least compressible part: if the AI mesh is
poor, phase 3 grows toward the top of its range.

## 10. Risks

| # | Risk | Mitigation |
| --- | --- | --- |
| R1 | **The total crosses 10M toman.** 10,000,000 + shipping + an upward offset ≈ 10.1–10.3M. Bank apps allow ~15M/day per card (1405), but some channels (certain ATMs, some apps per transfer) stop at 10M. | **Recommend to the client:** set the price so that price + shipping + 999 ≤ 10,000,000 (e.g. 9,800,000 with shipping included). Otherwise the pay page says "use your bank's app, not an ATM". |
| R2 | **The forwarder phone is offline** (battery, SIM, internet shutdown) → no auto-confirmations. | Dedicated phone, the review queue, the "seems silent" SMS, the "last matched" line on the panel. |
| R3 | **Tax authority** flags personal cards that receive many payments as business accounts. | The client's accountant registers the cards/accounts as business accounts (حساب تجاری). Not our call, but tell them. |
| R4 | **The AI 3D looks cheap** on black PU. | Light scene, Blender texture re-projection, the blockout fallback; the poster/stills fallback is always there. |
| R5 | **Unofficial import + using WiWU media.** Possible takedown, Torob disputes over the brand name. | The store name never implies WiWU. Media use is the client's accepted risk. Prefer our own renders and photos where possible. |
| R6 | **The store name is the bottleneck** for the domain, Enamad and the payment smoke test. | Send the shortlist this week. Build on staging meanwhile. |
| R7 | **cartbecart is a small third party** (API behind login, unknown webhook semantics). | Adapter isolated in one module. The manual review path works even if cartbecart is down. |
| R8 | **Shared server** with nisatak.com, nisatech.org and contech; this one holds addresses and phones. | Own system user and directory (like contech), daily SQLite backup kept off the web root and copied off the server. |

## 11. Ask the client (پیام برای کارفرما)

برای شروع کار به این موارد نیاز داریم:

۱. **نام فروشگاه:** از فهرستی که می‌فرستیم یکی را انتخاب کنید. دامنه‌ی `.ir` با کد ملی خودتان در ایرنیک ثبت می‌شود.
۲. **کارت‌به‌کارت:** اشتراک **مکس** سایت cartbecart.com (برای ۵ کارت، ماهانه ۴۴۰ هزار تومان). شماره‌ی ۵ کارت، همه به نام خودتان. نام دقیق صاحب کارت، همان‌طور که در اپ بانک دیده می‌شود. یک **گوشی اندرویدی جداگانه** که پیامک واریز هر ۵ کارت به آن برسد و همیشه روشن و به شارژ باشد. دسترسی API پنل cartbecart برای ما.
۳. **پیامک:** ساخت حساب در یک سامانه‌ی پیامک (کاوه‌نگار یا sms.ir) به نام خودتان.
۴. **اینماد:**
   - شماره‌ی موبایلی که به نام کد ملی خودتان ثبت شده؛
   - ایمیل؛
   - آدرس و کد پستی کسب‌وکار. این آدرس در صفحه‌ی اینماد عمومی دیده می‌شود، پس اگر آدرس منزل است، در نظر داشته باشید.
۵. **مشخصات کالا:**
   - ابعاد دقیق کیف؛
   - تعداد اثر انگشت؛
   - مدت شارژ باتری؛
   - اگر باتری تمام شود، کیف چطور باز می‌شود؟
   - جنس (طبق مشخصات سازنده چرم مصنوعی PU است)؛
   - رنگ کیف در عکس روبه‌رو: مشکی است یا سرمه‌ای؟
۶. **قیمت:** پیشنهاد ما این است که مبلغ نهایی، یعنی قیمت به‌علاوه‌ی هزینه‌ی ارسال، کمتر از ۱۰ میلیون تومان بماند. بعضی خودپردازها و اپ‌ها کارت‌به‌کارت بیش از ۱۰ میلیون را قبول نمی‌کنند.
۷. **ارسال:** هزینه‌ی پست پیشتاز و تیپاکس.
۸. **گارانتی:** چند ماه، و چه چیزهایی را پوشش می‌دهد؟ (کالا رسمی نیست، پس گارانتی را خودتان تعیین می‌کنید.)
۹. **حساب‌ها:** با حسابدارتان درباره‌ی ثبت کارت‌ها به‌عنوان «حساب تجاری» در سامانه‌ی مالیاتی مشورت کنید.
۱۰. **اپراتور:** چه کسی سفارش‌ها را مدیریت می‌کند؟ خودتان، یا همکار هم دارید؟

## 12. Done so far

- **Backgrounds removed** (2026-10-14) from the three photos: `media/cutouts/purse-{side-lock,front,back}.png`
  (transparent, cropped). Each has a `-lifted` copy with brightened shadows, for the 3D input.
  `contact-sheet.jpg` compares them.
  - Model: rembg `birefnet-general-lite`.
  - Photo 2 had a sofa pillow fused to the zipper, removed with `tools/fix2.py`.
  - Originals are in `media/source-photos/`.
- **Store core** built (2026-10-14, commit 2ea06c9): see README.md.
- **3D hero** built (2026-10-14): Hunyuan3D-2mv gave a good untextured shape (the textured generators
  were unusable or out of free quota); materials, grain and the sensor are made in the browser instead
  of Blender. Hero and scroll tour are one pinned section with photo fallbacks. See README.md.

- **3D model from the photos** (2026-10-14): the three photos are projected onto the AI shape (cameras
  fitted per photo), so front, back, top and the lock end with its sensor look like the real bag; the
  bottom and the far end have no photo yet. Bigger bag in the hero. See README.md, "The 3D hero".
- **3D details from the photos** (2026-10-15): the lock module, zipper and far-end hardware are now
  modelled to measurements taken through the fitted photo cameras; the bag's proportions come from the
  photos (a little deeper than the listings say). See README.md, "The 3D hero".
- **Look** (2026-10-15): two directions built around the 3D bag ("instrument" and "shop window").
  Amir first picked the shop window (d6e8140), then switched to the instrument, made richer: a
  hold-to-unlock lock demo, a parts diagram on the photos, the size on a centimetre mat, a printed
  sample bill. Checkout, order, lookup, policy pages and the panel follow through the shared tokens.
  See README, *Look*.
- **Look, review round** (2026-10-16, from the live staging site): Persian words broke apart on phones
  (Readex Pro's self-hosted copy has no ی ک گ پ) → Vazirmatn, with Vazir Code kept to figures; the
  white glow behind the bag removed; each section on its own ground; a solid phone menu; a new dark
  footer.
