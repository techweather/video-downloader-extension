#!/bin/bash

# Chrome Web Store Submission Package Builder
# Produces a .zip of extension_chrome/ suitable for uploading to the
# Chrome Web Store developer dashboard. Strips .DS_Store and stray files.

set -e

EXTENSION_DIR="extension_chrome"
BUILD_DIR="dist/extension"
OUTPUT_NAME="dlwithit-connector-chrome"
VERSION="1.0.0"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}Building Chrome Web Store submission package v${VERSION}${NC}"
echo "================================================="

if [ ! -d "$EXTENSION_DIR" ]; then
    echo -e "${RED}Error: $EXTENSION_DIR directory not found!${NC}"
    exit 1
fi

mkdir -p "$BUILD_DIR"

OUTPUT_PATH="$BUILD_DIR/${OUTPUT_NAME}-v${VERSION}.zip"

if [ -f "$OUTPUT_PATH" ]; then
    echo -e "${YELLOW}Removing previous build...${NC}"
    rm "$OUTPUT_PATH"
fi

echo -e "${YELLOW}Copying extension files...${NC}"
cp -r "$EXTENSION_DIR" "$BUILD_DIR/temp_chrome"

# Force version in manifest.json to match the package version.
echo -e "${YELLOW}Setting manifest version to ${VERSION}...${NC}"
sed -i.bak "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$BUILD_DIR/temp_chrome/manifest.json"
rm "$BUILD_DIR/temp_chrome/manifest.json.bak" 2>/dev/null || true

echo -e "${YELLOW}Files to be included:${NC}"
find "$BUILD_DIR/temp_chrome" -type f -exec basename {} \; | sort

echo -e "${YELLOW}Creating CWS submission package...${NC}"
cd "$BUILD_DIR/temp_chrome"
zip -r "../${OUTPUT_NAME}-v${VERSION}.zip" . -x "*.DS_Store" "*~" "*.bak" "*.tmp"
cd - > /dev/null

rm -rf "$BUILD_DIR/temp_chrome"

echo -e "${YELLOW}Package contents:${NC}"
unzip -l "$OUTPUT_PATH"

FILESIZE=$(stat -f%z "$OUTPUT_PATH" 2>/dev/null || stat -c%s "$OUTPUT_PATH" 2>/dev/null)
FILESIZE_KB=$((FILESIZE / 1024))

echo ""
echo -e "${GREEN}✅ Chrome submission package built successfully!${NC}"
echo -e "${GREEN}📦 Package: $OUTPUT_PATH${NC}"
echo -e "${GREEN}📏 Size: ${FILESIZE_KB}KB${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  Upload this .zip to the Chrome Web Store developer dashboard:"
echo "    https://chrome.google.com/webstore/devconsole/"
echo ""
echo "  Required for first submission:"
echo "    - Short description + detailed description"
echo "    - 128x128 icon (already in extension_chrome/icons/)"
echo "    - At least one 1280x800 or 640x400 promo screenshot"
echo "    - Privacy policy URL — point to PRIVACY.md in the repo:"
echo "      https://raw.githubusercontent.com/techweather/video-downloader-extension/main/PRIVACY.md"
echo ""
echo "  Review typically takes a few days. Once published, the .pkg"
echo "  postinstall script will open the CWS listing for one-click install."
