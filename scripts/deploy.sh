#!/usr/bin/env bash
# One-command deploy from a laptop. Same overlay the CI workflow does.
#
#   ./scripts/deploy.sh <theme-id>
#   ./scripts/deploy.sh            # lists themes and stops
set -euo pipefail

STORE="${SHOPIFY_FLAG_STORE:-nitidus.store}"
cd "$(dirname "$0")/.."

command -v shopify >/dev/null || { echo "Shopify CLI not found: npm i -g @shopify/cli"; exit 1; }

if [ $# -lt 1 ]; then
  echo "Themes on $STORE:"
  shopify theme list --store "$STORE"
  echo
  echo "Then: ./scripts/deploy.sh <theme-id>   (never the live one)"
  exit 0
fi

THEME_ID="$1"

role=$(shopify theme list --store "$STORE" --json \
  | THEME_ID="$THEME_ID" python3 -c "import json,sys,os; t=json.load(sys.stdin); i=os.environ['THEME_ID']; print(next((x.get('role','') for x in t if str(x.get('id'))==i),'missing'))")

case "$role" in
  live|main) echo "That is the published theme. Duplicate it first and deploy to the copy."; exit 1 ;;
  missing)   echo "Theme $THEME_ID not found on $STORE."; exit 1 ;;
esac
echo "Deploying to theme $THEME_ID (role: $role) on $STORE"

rm -rf build
shopify theme pull --store "$STORE" --theme "$THEME_ID" --path build --force
cp -r shopify/assets/.    build/assets/
cp -r shopify/sections/.  build/sections/
cp -r shopify/templates/. build/templates/
./scripts/inject-theme-tags.sh build/layout/theme.liquid
shopify theme push --store "$STORE" --theme "$THEME_ID" --path build --allow-live=false

echo
echo "Done. Preview it from Online Store -> Themes, then add a page using the"
echo "page.nitidus template under Content -> Pages."
