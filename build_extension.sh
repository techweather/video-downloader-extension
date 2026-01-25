#!/bin/bash

# Firefox Extension Build Script for Media Downloader Connector
# Creates a distributable .zip file from the extension_minimal folder

set -e  # Exit on any error

# Configuration
EXTENSION_DIR="extension_minimal"
BUILD_DIR="dist/extension"
OUTPUT_NAME="media-downloader-connector-firefox"
VERSION="1.0"

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
if [ -f "$BUILD_DIR/${OUTPUT_NAME}-v${VERSION}.zip" ]; then
    echo -e "${YELLOW}Removing previous build...${NC}"
    rm "$BUILD_DIR/${OUTPUT_NAME}-v${VERSION}.zip"
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

# Create the zip file
echo -e "${YELLOW}Creating distribution package...${NC}"
cd "$BUILD_DIR/temp_extension"
zip -r "../${OUTPUT_NAME}-v${VERSION}.zip" . -x "*.DS_Store" "*~" "*.bak" "*.tmp"
cd - > /dev/null

# Clean up temporary directory
rm -rf "$BUILD_DIR/temp_extension"

# Verify the package
echo -e "${YELLOW}Package contents:${NC}"
unzip -l "$BUILD_DIR/${OUTPUT_NAME}-v${VERSION}.zip"

# Calculate file size
FILESIZE=$(stat -f%z "$BUILD_DIR/${OUTPUT_NAME}-v${VERSION}.zip" 2>/dev/null || stat -c%s "$BUILD_DIR/${OUTPUT_NAME}-v${VERSION}.zip" 2>/dev/null)
FILESIZE_KB=$((FILESIZE / 1024))

echo ""
echo -e "${GREEN}✅ Extension built successfully!${NC}"
echo -e "${GREEN}📦 Package: $BUILD_DIR/${OUTPUT_NAME}-v${VERSION}.zip${NC}"
echo -e "${GREEN}📏 Size: ${FILESIZE_KB}KB${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Install in Firefox by going to about:debugging"
echo "2. Click 'This Firefox' → 'Load Temporary Add-on'"
echo "3. Select the .zip file or extract and select manifest.json"
echo ""
echo -e "${YELLOW}For permanent installation, the extension needs to be signed by Mozilla.${NC}"
echo -e "${YELLOW}See Firefox_Extension_Installation.md for detailed instructions.${NC}"