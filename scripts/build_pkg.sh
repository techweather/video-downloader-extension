#!/bin/bash

# Build a .pkg installer for dlwithit with component-choice UI:
#   - dlwithit app (required)
#   - Firefox extension (optional, postinstall opens Firefox with the .xpi)
#   - Chrome extension (optional, postinstall opens CWS listing or load-unpacked)
#
# Outputs an ad-hoc signed installer at dist/dlwithit-installer-v<VERSION>.pkg.
# Full Developer ID signing + notarization is layered in once Sean has Apple
# Dev enrollment — see installer/README-signing.md (TODO) for the diff.

set -euo pipefail

# === Config =========================================================
VERSION="1.0.0"
APP_BUNDLE_ID="com.dlwithit.app"
FIREFOX_BUNDLE_ID="com.dlwithit.firefox"
CHROME_BUNDLE_ID="com.dlwithit.chrome"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Stage under /tmp so pkgbuild re-owning files to root:wheel during framework
# signing doesn't pollute the repo's build/ dir — /tmp gets cleaned by macOS
# and root-owned files there aren't our problem. Timestamped per run.
BUILD_DIR="/tmp/dlwithit-pkg-build-$$"
DIST_DIR="$REPO_ROOT/dist"
STAGING_APP_ROOT="$BUILD_DIR/staging-app"           # holds dlwithit.app to pkgbuild
COMPONENTS_DIR="$BUILD_DIR/components"               # individual component .pkgs
INSTALLER_DIR="$REPO_ROOT/installer"
PKG_SCRIPTS_DIR="$REPO_ROOT/scripts/pkg_scripts"

# Where to grab the .app from. Default points at the legacy DMG staging
# bundle so iteration on the installer doesn't require a full PyInstaller
# run. Override via APP_SOURCE=path/to/dlwithit.app for a fresh build.
APP_SOURCE="${APP_SOURCE:-$REPO_ROOT/dist/dmg-staging/dlwithit.app}"

OUTPUT_PKG="$DIST_DIR/dlwithit-installer-v${VERSION}.pkg"

# === Colors =========================================================
RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'
say()  { echo -e "${BLUE}==>${NC} $*"; }
ok()   { echo -e "${GREEN}✓${NC}  $*"; }
warn() { echo -e "${YELLOW}!${NC}  $*"; }
err()  { echo -e "${RED}✗${NC}  $*" >&2; }

# === Pre-flight =====================================================
say "Pre-flight checks"

if [[ ! -d "$APP_SOURCE" ]]; then
    err "App bundle not found at $APP_SOURCE"
    err "Build the .app first (pyinstaller dlwithit.spec) or set APP_SOURCE=path/to/dlwithit.app"
    exit 1
fi
ok "App bundle: $APP_SOURCE"

XPI_FILE=$(ls "$DIST_DIR/extension/"dlwithit-connector-firefox-v*.xpi 2>/dev/null | sort | tail -1 || true)
if [[ -z "$XPI_FILE" ]]; then
    warn "No Firefox .xpi found in dist/extension/ — running build_extension.sh"
    (cd "$REPO_ROOT" && bash build_extension.sh) >/dev/null
    XPI_FILE=$(ls "$DIST_DIR/extension/"dlwithit-connector-firefox-v*.xpi | sort | tail -1)
fi
ok "Firefox .xpi: $XPI_FILE"

CHROME_ZIP=$(ls "$DIST_DIR/extension/"dlwithit-connector-chrome-v*.zip 2>/dev/null | sort | tail -1 || true)
if [[ -z "$CHROME_ZIP" ]]; then
    warn "No Chrome .zip found in dist/extension/ — running build_chrome_zip.sh"
    (cd "$REPO_ROOT" && bash scripts/build_chrome_zip.sh) >/dev/null
    CHROME_ZIP=$(ls "$DIST_DIR/extension/"dlwithit-connector-chrome-v*.zip | sort | tail -1)
fi
ok "Chrome .zip: $CHROME_ZIP"

for required_file in \
    "$INSTALLER_DIR/Distribution.xml" \
    "$INSTALLER_DIR/resources/welcome.html" \
    "$INSTALLER_DIR/resources/conclusion.html" \
    "$PKG_SCRIPTS_DIR/firefox/postinstall" \
    "$PKG_SCRIPTS_DIR/chrome/postinstall"
do
    if [[ ! -e "$required_file" ]]; then
        err "Missing required file: $required_file"
        exit 1
    fi
done
ok "Installer resources and postinstall scripts present"

# === Clean build dir ================================================
# Ad-hoc deep-signing the staged .app can write xattrs/perms that make
# a plain `rm -rf` fail on subsequent runs. Chmod first to be safe; if
# that still fails (e.g. files owned by root from an earlier sudo run),
# bail clearly so the user can fix it.
say "Cleaning build directory"
if [[ -d "$BUILD_DIR" ]]; then
    chmod -R u+w "$BUILD_DIR" 2>/dev/null || true
    if ! rm -rf "$BUILD_DIR" 2>/dev/null; then
        err "Could not remove $BUILD_DIR (likely root-owned from a prior run)."
        err "Run: sudo rm -rf \"$BUILD_DIR\""
        exit 1
    fi
fi
mkdir -p "$STAGING_APP_ROOT" "$COMPONENTS_DIR" "$DIST_DIR"

# === Stage the .app with extensions bundled inside ==================
say "Staging .app with bundled extensions"
cp -R "$APP_SOURCE" "$STAGING_APP_ROOT/dlwithit.app"
STAGED_APP="$STAGING_APP_ROOT/dlwithit.app"

FF_DEST="$STAGED_APP/Contents/Resources/extensions/firefox"
CR_DEST="$STAGED_APP/Contents/Resources/extensions/chrome"
mkdir -p "$FF_DEST" "$CR_DEST"

# Firefox: ship the .xpi as-is (postinstall opens Firefox with it).
cp "$XPI_FILE" "$FF_DEST/"
ok "Firefox .xpi bundled at Contents/Resources/extensions/firefox/"

# Chrome: unzip the submission zip into the folder so chrome://extensions
# load-unpacked can point at it directly (pre-CWS-publication fallback).
unzip -q -o "$CHROME_ZIP" -d "$CR_DEST"
ok "Chrome extension unpacked at Contents/Resources/extensions/chrome/"

# Ad-hoc re-sign the .app since we modified its contents (added Resources).
# Without this, macOS sees a tampered signature and refuses to launch.
say "Ad-hoc re-signing the staged .app"
codesign --force --deep --sign - "$STAGED_APP" 2>&1 | sed 's/^/    /' || {
    warn "codesign reported issues — continuing (ad-hoc signing is fragile, real signing happens post-Apple-Dev)"
}

# === Build component packages =======================================
say "Building component package: app"
# pkgbuild defaults <BundleIsRelocatable> to true for .app bundles, which
# tells the installer to update an existing bundle of the same ID wherever
# it sits on disk (the "relocation" feature for shipping in-place updates).
# That's catastrophic for a fresh install: if the user has dist/dlwithit.app
# from a local build, the .pkg "updates" THAT path instead of installing to
# /Applications. We always want /Applications, so disable relocation via a
# component plist.
COMPONENT_PLIST="$BUILD_DIR/dlwithit-app.plist"
cat > "$COMPONENT_PLIST" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<array>
    <dict>
        <key>BundleHasStrictIdentifier</key>
        <true/>
        <key>BundleIsRelocatable</key>
        <false/>
        <key>BundleIsVersionChecked</key>
        <true/>
        <key>BundleOverwriteAction</key>
        <string>upgrade</string>
        <key>RootRelativeBundlePath</key>
        <string>dlwithit.app</string>
    </dict>
</array>
</plist>
EOF

pkgbuild \
    --root "$STAGING_APP_ROOT" \
    --identifier "$APP_BUNDLE_ID" \
    --version "$VERSION" \
    --install-location "/Applications" \
    --component-plist "$COMPONENT_PLIST" \
    "$COMPONENTS_DIR/dlwithit-app.pkg"
ok "dlwithit-app.pkg (non-relocatable)"

say "Building component package: firefox (nopayload, scripts only)"
pkgbuild \
    --nopayload \
    --identifier "$FIREFOX_BUNDLE_ID" \
    --version "$VERSION" \
    --scripts "$PKG_SCRIPTS_DIR/firefox" \
    "$COMPONENTS_DIR/dlwithit-firefox.pkg"
ok "dlwithit-firefox.pkg"

say "Building component package: chrome (nopayload, scripts only)"
pkgbuild \
    --nopayload \
    --identifier "$CHROME_BUNDLE_ID" \
    --version "$VERSION" \
    --scripts "$PKG_SCRIPTS_DIR/chrome" \
    "$COMPONENTS_DIR/dlwithit-chrome.pkg"
ok "dlwithit-chrome.pkg"

# === Combine with productbuild ======================================
say "Building distribution installer"
productbuild \
    --distribution "$INSTALLER_DIR/Distribution.xml" \
    --resources "$INSTALLER_DIR/resources" \
    --package-path "$COMPONENTS_DIR" \
    "$OUTPUT_PKG"
ok "Distribution installer built"

# === Ad-hoc sign the final .pkg =====================================
say "Ad-hoc signing the installer"
# productsign requires a real Developer ID cert; for ad-hoc we just leave
# the .pkg unsigned. This is fine for local + same-machine testing; a
# fresh Mac will need right-click → Open until real signing lands.
warn "Installer is unsigned (no Developer ID cert yet). Fresh Macs will need right-click → Open."

# === Done ===========================================================
SIZE=$(stat -f%z "$OUTPUT_PKG")
SIZE_MB=$((SIZE / 1024 / 1024))

echo ""
ok "Installer built successfully"
echo -e "${GREEN}   Output: $OUTPUT_PKG${NC}"
echo -e "${GREEN}   Size:   ${SIZE_MB}MB${NC}"
echo ""
echo -e "${BLUE}Next:${NC}"
echo "  Test locally:  open \"$OUTPUT_PKG\""
echo "  Inspect:       pkgutil --expand \"$OUTPUT_PKG\" /tmp/dlwithit-pkg-inspect"
echo ""
