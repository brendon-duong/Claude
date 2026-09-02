# -*- coding: utf-8 -*-
"""Split the single-file preview into Shopify theme files."""
import io, os, re, json, base64, shutil

SRC = "nitidus-preview.html"
OUT = "shopify"
s = io.open(SRC, encoding="utf8").read()

if os.path.isdir(OUT): shutil.rmtree(OUT)
for d in ("assets", "sections", "templates"): os.makedirs(os.path.join(OUT, d))

# --- 1. CSS and JS out of the single file ----------------------------------
css = re.search(r"<style>(.*?)</style>", s, re.S).group(1)
js  = re.search(r'<script type="module">(.*?)</script>', s, re.S).group(1)

# --- 2. body markup, minus preview-only furniture --------------------------
body = s[s.index("</style>") + len("</style>"):]
body = re.sub(r'<script type="module">.*?</script>', "", body, flags=re.S)
status = re.search(r'<footer class="nit nit-status">.*?</footer>', body, re.S)
if status: body = body.replace(status.group(0), "")

# --- 3. data URIs become real theme assets ---------------------------------
names = {}
def name_for(uri):
    if uri in names: return names[uri]
    # match the blob back to the file that produced it
    for f, n in (("hero-product.webp","nitidus-product.webp"), ("slide-kit.webp","nitidus-kit.webp"),
                 ("slide-hand.webp","nitidus-hand.webp"), ("slide-car.webp","nitidus-car.webp")):
        if os.path.exists(f):
            blob = "data:image/webp;base64," + base64.b64encode(open(f,"rb").read()).decode()
            if blob == uri:
                shutil.copy(f, os.path.join(OUT, "assets", n))
                names[uri] = n
                return n
    raise SystemExit("unmatched data URI (len %d) — refusing to guess" % len(uri))

for uri in set(re.findall(r'data:image/webp;base64,[A-Za-z0-9+/=]+', body)):
    n = name_for(uri)
    body = body.replace(uri, "{{ '%s' | asset_url }}" % n)

io.open(os.path.join(OUT, "assets", "nitidus.css"), "w", encoding="utf8").write(css.strip() + "\n")
io.open(os.path.join(OUT, "assets", "nitidus.js"),  "w", encoding="utf8").write(js.strip() + "\n")

# --- 4. split the markup at top-level block boundaries ----------------------
opens = [(m.start(), m.group(1), m.group(2))
         for m in re.finditer(r'<(section|header|footer)[^>]*class="nit ([a-z0-9\-]+)', body)]
blocks = []
for i, (start, tag, cls) in enumerate(opens):
    end = opens[i+1][0] if i+1 < len(opens) else len(body)
    chunk = body[start:end]
    close = chunk.rfind("</%s>" % tag)
    if close == -1: raise SystemExit("no closing tag for " + cls)
    blocks.append((cls, chunk[:close + len(tag) + 3]))

TITLES = {
 "nit-header":"Nitidus header","nit-hero":"Nitidus hero","nit-assurance":"Nitidus assurance bar",
 "nit-problem":"Nitidus problem","nit-anatomy":"Nitidus anatomy","nit-spec":"Nitidus specification",
 "nit-usecase":"Nitidus use cases","nit-compare":"Nitidus comparison","nit-reviews":"Nitidus reviews",
 "nit-offer":"Nitidus offer","nit-guarantee":"Nitidus guarantee","nit-faq":"Nitidus FAQ",
 "nit-closing":"Nitidus closing","nit-footer":"Nitidus footer",
}

order = []
for cls, markup in blocks:
    handle = cls.replace("nit-", "nitidus-")
    title = TITLES.get(cls, cls)
    schema = {"name": title[:25], "tag": "div", "settings": [], "presets": [{"name": title}]}
    liquid = markup.strip() + "\n\n{% schema %}\n" + json.dumps(schema, indent=2) + "\n{% endschema %}\n"
    io.open(os.path.join(OUT, "sections", handle + ".liquid"), "w", encoding="utf8").write(liquid)
    order.append(handle)

# --- 5. its own page template, so the live homepage is untouched -----------
tpl = {"sections": {h: {"type": h, "settings": {}} for h in order}, "order": order}
io.open(os.path.join(OUT, "templates", "page.nitidus.json"), "w", encoding="utf8").write(
    json.dumps(tpl, indent=2) + "\n")

print("sections:", len(order))
print("assets:", sorted(os.listdir(os.path.join(OUT,"assets"))))
print("css %.0f KB  js %.0f KB" % (len(css)/1024, len(js)/1024))
