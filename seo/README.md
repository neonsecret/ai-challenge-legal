# SEO IndexNow and Bing Verification

## IndexNow via Cloudflare
- Navigate to **Cloudflare dashboard → vitreon.app → Speed → Crawler Hints**.
- Toggle **Enable IndexNow**. Owner: Neon.
- Once enabled, every cache‑purge or newly added URL automatically ping Bing and Yandex.

## Self‑hosted fallback
- Place the IndexNow key file `/<KEY>.txt` under `frontend/public/`.
- On every sitemap update, POST `https://api.indexnow.org/indexnow` with the new sitemap URL.

## Bing Site Verification
- The key value is already in `frontend/public/BingSiteAuth.xml` and referenced in `layout.tsx` as `msvalidate.01: "79D6925D8DEC12408DE1AE18E93DE54B"`.
- No Google verification placeholder remains.
