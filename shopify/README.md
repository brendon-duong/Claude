# Nitidus — Shopify theme files

The single-file preview split into Shopify theme files. Drops into your
existing theme; nothing here replaces or edits Horizon's own files except two
added lines in `layout/theme.liquid`.

```
assets/     nitidus.css, nitidus.js, and the four product images
sections/   14 sections, one per block of the page, each with a schema
templates/  page.nitidus.json — wires the sections in order
```

The page is self-contained: every class is `nit-*` or its own `is-*` state, so
it does not depend on Dawn, Horizon, or any other theme's CSS. The Dawn
references in the stylesheet comments are about cascade order only.

## 1. Load the CSS and JS

Add these two lines to `layout/theme.liquid`, immediately before `</head>` —
**after** Horizon's own stylesheets, so equal-specificity rules resolve in
Nitidus's favour:

```liquid
{{ 'nitidus.css' | asset_url | stylesheet_tag }}
<script src="{{ 'nitidus.js' | asset_url }}" type="module"></script>
```

`type="module"` matters: the script is an ES module and defers automatically,
so it must not be converted to `script_tag`, which omits the attribute.

## 2. Get the files onto the store

**Shopify CLI** (a Development theme already exists on this store, so the CLI
is set up somewhere):

```bash
shopify theme pull --store nitidus.store          # into a working copy
cp -r assets sections templates <theme-folder>/   # add these files
# edit layout/theme.liquid as in step 1
shopify theme push --store nitidus.store --unpublished --theme-name "Nitidus"
```

Pushing `--unpublished` creates a new theme nobody can see. Preview it, and
publish only when the content in step 4 has been dealt with.

**GitHub** — connect the repo under Online Store → Themes → Add theme →
Connect from GitHub, pointing at a branch whose root is the theme folder.
Shopify then tracks that branch.

**Admin code editor** — Online Store → Themes → ⋯ → Edit code, and add each
file by hand. It works, but it is 20 files.

## 3. Make the page

Admin → Content → Pages → Add page. In **Theme template**, choose
`page.nitidus`. Save, then preview. To make it the homepage instead, rename
`templates/page.nitidus.json` to `templates/index.json` — that one does
replace the current homepage, so only do it deliberately.

Every section is in the theme editor, so they can be reordered, hidden or
removed without touching the code.

## 4. Before it goes public

The preview was built with placeholder content of the right shape. On a live
store some of it becomes a claim to real customers:

- **Prices are in GBP** (£79 / £142 / £199) and the type comments describe a
  UK storefront. This store is NZD, New Zealand.
- **The ratings are invented** — "4.7 out of 5, from 214 reviews", with a full
  distribution, and three named testimonials ("Sarah T. · March 2026") marked
  *Verified purchase*.
- **The stock counter is invented** — "6 left" on the triple pack.
- Specification figures, delivery times and the guarantee terms are all
  unverified placeholder.

Publishing invented reviews, review counts and scarcity counters to shoppers
is misleading conduct under the Fair Trading Act, and breaches Shopify's terms.
Replace them with real figures, or remove those sections — the reviews section
can be deleted in the theme editor without touching anything else.

## Notes

- Fonts are base64 inside `nitidus.css` (~83KB of its 191KB). Fine as is; if
  you would rather serve them separately, extract the two `@font-face` blocks
  to `assets/` and swap the `src` for `asset_url`.
- Images are referenced with `asset_url`. Replace them by overwriting the
  files in `assets/` under the same names.
- The hero's 360 viewer is in poster mode. Add a turntable frame sequence and
  set `data-nit-360-src` in `sections/nitidus-hero.liquid` to make it spin.
