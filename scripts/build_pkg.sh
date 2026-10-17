#!/bin/bash

# Build a .pkg installer for dlwithit with component-choice UI:
#   - dlwithit app (required) — the SwiftUI app from mac/, which embeds the
#     PyInstaller engine at Contents/Resources/engine/. The old PyQt app
#     (dlwithit.spec) is no longer packaged.
#   - Firefox extension (optional, postinstall opens Firefox with the .xpi)
#   - Chrome extension (optional, postinstall opens CWS listing or load-unpacked)
#
# Build the app first:
#   .venv/bin/pyinstaller --noconfirm engine.spec
#   xcodebuild -project mac/dlwithit.xcodeproj -target dlwithit -configuration Release SYMROOT=build build
#
# Outputs an unsigned installer (ad-hoc signed app) at
# dist/dlwithit-installer-v<VERSION>.pkg. Developer ID signing + notarization
# slot into the SIGNING section below once Apple Dev enrollment lands.

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

# Where to grab the .app from: the Release build of the SwiftUI app.
# Override via APP_SOURCE=path/to/dlwithit.app.
APP_SOURCE="${APP_SOURCE:-$REPO_ROOT/mac/build/Release/dlwithit.app}"

# === Signing (hook) =================================================
# Unset = ad-hoc ("-"), which is all we can do before Apple Dev enrollment.
# Once enrolled, set these and fill in the TODOs in sign_app / the
# "Sign the final .pkg" section:
#   APP_SIGN_IDENTITY="Developer ID Application: … (TEAMID)"
#   INSTALLER_SIGN_IDENTITY="Developer ID Installer: … (TEAMID)"
APP_SIGN_IDENTITY="${APP_SIGN_IDENTITY:--}"
INSTALLER_SIGN_IDENTITY="${INSTALLER_SIGN_IDENTITY:-}"

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
    err "Build it first (see the top of this script) or set APP_SOURCE=path/to/dlwithit.app"
    exit 1
fi
ok "App bundle: $APP_SOURCE"

APP_PLIST="$APP_SOURCE/Contents/Info.plist"
APP_ID_FOUND=$(/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "$APP_PLIST" 2>/dev/null || true)
APP_VERSION_FOUND=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$APP_PLIST" 2>/dev/null || true)
if [[ "$APP_ID_FOUND" != "$APP_BUNDLE_ID" ]]; then
    err "App bundle id is '$APP_ID_FOUND', expected '$APP_BUNDLE_ID' (is APP_SOURCE the Swift app?)"
    exit 1
fi
# The installer version-checks bundles: an app reporting a lower version than
# the one already in /Applications gets silently skipped. Keep them in step.
if [[ "$APP_VERSION_FOUND" != "$VERSION" ]]; then
    err "App version is '$APP_VERSION_FOUND' but this script says VERSION=$VERSION."
    err "Bump MARKETING_VERSION in mac/dlwithit.xcodeproj (see the version bump checklist in CLAUDE.md #20)."
    exit 1
fi
if [[ ! -x "$APP_SOURCE/Contents/Resources/engine/dlwithit-engine" ]]; then
    err "No engine inside the app (Contents/Resources/engine/dlwithit-engine)."
    err "Build it with engine.spec, then rebuild the app with -configuration Release."
    exit 1
fi
ok "Bundle id $APP_ID_FOUND, version $APP_VERSION_FOUND, engine embedded"

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
# ditto keeps symlinks and bundle structure intact (PyInstaller's _internal/
# is full of them).
ditto "$APP_SOURCE" "$STAGING_APP_ROOT/dlwithit.app"
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

# Installed permissions: pkgbuild records each file's mode as staged (owner
# becomes root:wheel). An earlier build shipped root:wheel 700 dirs, which
# locked the user out of their own app. Normalise: everyone can read and
# traverse, only the owner writes; executables keep their x bit.
say "Normalising file permissions"
chmod -R u+rwX,go+rX,go-w "$STAGED_APP"
# Drop quarantine/provenance xattrs picked up during the build; codesign
# refuses bundles carrying resource-fork-style detritus.
xattr -cr "$STAGED_APP"
ok "Permissions normalised (dirs 755, files 644/755)"

# === SIGNING ========================================================
# Re-sign the .app since we modified its contents (added Resources).
# Without this, macOS sees a tampered signature and refuses to launch.
sign_app() {
    local app="$1"
    if [[ "$APP_SIGN_IDENTITY" == "-" ]]; then
        codesign --force --deep --sign - "$app"
        return
    fi
    # TODO (Apple Dev enrollment): Developer ID signing for notarization.
    # --deep isn't enough for notarization; sign inside-out with the
    # hardened runtime and a secure timestamp:
    #   1. every Mach-O under Contents/Resources/engine/ (dlwithit-engine,
    #      _internal/*.dylib, *.so, ffmpeg, ffprobe, deno, Python), with
    #      engine entitlements (allow-unsigned-executable-memory etc. if
    #      PyInstaller needs them)
    #   2. Contents/Resources/engine/dlwithit-engine last within the engine
    #   3. the .app itself
    #   codesign --force --options runtime --timestamp \
    #       --sign "$APP_SIGN_IDENTITY" [--entitlements …] <path>
    err "Developer ID signing isn't implemented yet (APP_SIGN_IDENTITY=$APP_SIGN_IDENTITY)."
    exit 1
}
say "Signing the staged .app (identity: $APP_SIGN_IDENTITY)"
sign_app "$STAGED_APP" 2>&1 | sed 's/^/    /'
codesign --verify --deep --strict "$STAGED_APP" 2>&1 | sed 's/^/    /' \
    && ok "Signature verifies" \
    || warn "codesign --verify reported issues (ad-hoc signing is fragile; real signing comes with Apple Dev)"

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

# === Sign the final .pkg (hook) =====================================
if [[ -n "$INSTALLER_SIGN_IDENTITY" ]]; then
    # TODO (Apple Dev enrollment):
    #   productsign --sign "$INSTALLER_SIGN_IDENTITY" --timestamp "$OUTPUT_PKG" "$OUTPUT_PKG.signed"
    #   mv "$OUTPUT_PKG.signed" "$OUTPUT_PKG"
    #   xcrun notarytool submit "$OUTPUT_PKG" --keychain-profile <profile> --wait
    #   xcrun stapler staple "$OUTPUT_PKG"
    err "Installer signing isn't implemented yet (INSTALLER_SIGN_IDENTITY=$INSTALLER_SIGN_IDENTITY)."
    exit 1
fi
# productsign requires a real Developer ID cert; until then the .pkg stays
# unsigned. Fine for local + same-machine testing; a fresh Mac will need
# right-click → Open until real signing lands.
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
