#!/bin/bash

# Firefox Extension Build Script for Media Downloader Connector
# Creates a distributable .zip file from the extension_minimal folder

set -e  # Exit on any error

# Configuration
EXTENSION_DIR="extension_minimal"
BUILD_DIR="dist/extension"
OUTPUT_NAME="dlwithit-connector-firefox"
VERSION="1.0.0"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Building Firefox Extension: Media Downloader Connector v${VERSION}${NC}"
echo "================================================="

# Check if extension_minimal directory exists
if [ ! -d "$EXTENSION_DIR" ]; then
    echo -e "${RED}Error: $EXTENSION_DIR directory not found!${NC}"
    echo "Please ensure the extension_minimal folder exists in the current directory."
    exit 1
fi

# Create build directory
echo -e "${YELLOW}Creating build directory...${NC}"
mkdir -p "$BUILD_DIR"

# Clean previous builds
if [ -f "$BUILD_DIR/${OUTPUT_NAME}-v${VERSION}.xpi" ]; then
    echo -e "${YELLOW}Removing previous build...${NC}"
    rm "$BUILD_DIR/${OUTPUT_NAME}-v${VERSION}.xpi"
fi

# Copy extension files
echo -e "${YELLOW}Copying extension files...${NC}"
cp -r "$EXTENSION_DIR" "$BUILD_DIR/temp_extension"

# Update version in manifest.json
echo -e "${YELLOW}Updating manifest version to ${VERSION}...${NC}"
sed -i.bak "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$BUILD_DIR/temp_extension/manifest.json"
rm "$BUILD_DIR/temp_extension/manifest.json.bak" 2>/dev/null || true

# List files to be included
echo -e "${YELLOW}Files to be included:${NC}"
find "$BUILD_DIR/temp_extension" -type f -exec basename {} \; | sort

# Create the .xpi file
# An .xpi is a renamed zip with manifest.json at the archive root —
# the format AMO accepts for submission and Firefox accepts for install.
echo -e "${YELLOW}Creating distribution package (.xpi)...${NC}"
cd "$BUILD_DIR/temp_extension"
zip -r "../${OUTPUT_NAME}-v${VERSION}.xpi" . -x "*.DS_Store" "*~" "*.bak" "*.tmp"
cd - > /dev/null

# Clean up temporary directory
rm -rf "$BUILD_DIR/temp_extension"

# Verify the package
echo -e "${YELLOW}Package contents:${NC}"
unzip -l "$BUILD_DIR/${OUTPUT_NAME}-v${VERSION}.xpi"

# Calculate file size
FILESIZE=$(stat -f%z "$BUILD_DIR/${OUTPUT_NAME}-v${VERSION}.xpi" 2>/dev/null || stat -c%s "$BUILD_DIR/${OUTPUT_NAME}-v${VERSION}.xpi" 2>/dev/null)
FILESIZE_KB=$((FILESIZE / 1024))

echo ""
echo -e "${GREEN}✅ Extension built successfully!${NC}"
echo -e "${GREEN}📦 Package: $BUILD_DIR/${OUTPUT_NAME}-v${VERSION}.xpi${NC}"
echo -e "${GREEN}📏 Size: ${FILESIZE_KB}KB${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  Submit this .xpi to addons.mozilla.org for signing:"
echo "    https://addons.mozilla.org/developers/addon/submit/"
echo ""
echo "  Once AMO returns a signed .xpi, that's the file the .pkg"
echo "  installer drops onto end-user machines."
echo ""
echo -e "${YELLOW}Local-install testing before AMO signing:${NC}"
echo "  Firefox Dev/ESR/Nightly: about:debugging → 'Load Temporary Add-on'"
echo "  Firefox Release rejects unsigned .xpi files — AMO signing required."
echo ""
echo -e "${YELLOW}See Firefox_Extension_Installation.md for full details.${NC}"