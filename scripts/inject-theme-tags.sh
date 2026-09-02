#!/usr/bin/env bash
# Add the Nitidus stylesheet and module script to a theme's layout.
#
# Idempotent by design: it looks for the marker before writing, so running it
# on every deploy adds the tags once and then does nothing. A CI step that
# cannot safely run twice is a CI step that will eventually run twice.
set -euo pipefail

LAYOUT="${1:?usage: inject-theme-tags.sh path/to/layout/theme.liquid}"
MARKER="nitidus.css"

[ -f "$LAYOUT" ] || { echo "no layout at $LAYOUT"; exit 1; }

if grep -q "$MARKER" "$LAYOUT"; then
  echo "tags already present — nothing to do"
  exit 0
fi

grep -qi '</head>' "$LAYOUT" || { echo "no </head> in $LAYOUT"; exit 1; }

# Inserted immediately before </head>, which puts it after the theme's own
# stylesheets so equal-specificity rules resolve in Nitidus's favour.
python3 - "$LAYOUT" <<'PY'
import io, re, sys
p = sys.argv[1]
s = io.open(p, encoding="utf8").read()
tags = (
  "  {{ 'nitidus.css' | asset_url | stylesheet_tag }}\n"
  "  <script src=\"{{ 'nitidus.js' | asset_url }}\" type=\"module\"></script>\n"
)
# only the final </head>, and keep the author's original casing
i = s.lower().rfind("</head>")
s = s[:i] + tags + s[i:]
io.open(p, "w", encoding="utf8").write(s)
PY

echo "injected into $LAYOUT"
