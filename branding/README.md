# Branding source files

These are the original, full-resolution logo files — kept here so a higher-res
export is always possible later (print, merch, a bigger hero placement,
anything not anticipated yet) without needing to re-source them.

- `logo-source.png` — 1832×1052, the header wordmark
- `icon-source.png` — 224×224, the square icon mark (favicon/app-icon source)

**These are not linked from any page.** Everything the site actually serves
(`/logo.png`, `/logo.webp`, `/favicon.ico`, `/favicon-192.png`,
`/apple-touch-icon.png`, `/og-image.png`, all in the repo root) is a
resized/optimized derivative generated from these two files, sized for its
specific use:

| File | Derived from | Size | Why |
|---|---|---|---|
| `/logo.png`, `/logo.webp` | logo-source.png | 208×120 | ~3× the 40px header display height — sharp on retina without shipping a 1832px image for a 40px-tall element |
| `/favicon.ico` | icon-source.png | 16/32/48px (multi-res) | Standard favicon sizes |
| `/favicon-192.png` | icon-source.png | 192×192 | Modern browser/PWA icon reference |
| `/apple-touch-icon.png` | icon-source.png | 180×180 | iOS home-screen icon standard |
| `/og-image.png` | logo-source.png | 1200×630 | Social share preview (Discord/Slack/Twitter/etc.) — logo centered on a white canvas at that aspect ratio, not the header logo stretched |

If the logo ever changes, regenerate the derivatives from a new source here
rather than resizing the already-resized versions in the repo root.
