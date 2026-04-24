#!/bin/bash
# fix_deployment_target.sh
#
# Patches all .so and .dylib files in a PyInstaller .app bundle that have
# minos > TARGET_VERSION, lowering them to TARGET_VERSION so the app runs
# on older macOS.
#
# The minos field is a linker stamp — none of these Python stdlib or
# Homebrew dylibs actually call macOS-version-gated APIs, so patching
# is safe in practice.
#
# After patching, each binary is re-signed with an ad-hoc signature
# (-s -) so macOS doesn't reject the modified binaries. The app remains
# unsigned/not-notarized; users still need right-click → Open on first launch.
#
# Usage:
#   ./scripts/fix_deployment_target.sh [app_path] [target_version]
#
# Defaults:
#   app_path       = dist/dlwithit.app
#   target_version = 14.0

set -euo pipefail

APP="${1:-dist/dlwithit.app}"
TARGET="${2:-14.0}"
SDK="15.2"   # keep the SDK version unchanged; only minos matters for compat

if [ ! -d "$APP" ]; then
  echo "Error: $APP not found. Run PyInstaller first." >&2
  exit 1
fi

echo "Patching $APP → minos $TARGET"

patched=0
skipped=0
failed=0

while IFS= read -r -d '' f; do
  # Read current minos
  current=$(vtool -show "$f" 2>/dev/null | awk '/minos/{print $2}' | head -1)

  if [ -z "$current" ]; then
    # Thin binary or no LC_BUILD_VERSION (e.g. fat slice not for this arch)
    ((skipped++)) || true
    continue
  fi

  # Compare: only patch if minos > TARGET
  # Use Python for reliable version comparison
  needs_patch=$(python3 -c "
import sys
cur = tuple(int(x) for x in '$current'.split('.'))
tgt = tuple(int(x) for x in '$TARGET'.split('.'))
print('yes' if cur > tgt else 'no')
")

  if [ "$needs_patch" = "yes" ]; then
    if vtool -set-build-version macos "$TARGET" "$SDK" -replace -output "$f" "$f" 2>/dev/null; then
      # Re-sign with ad-hoc signature to satisfy macOS loader
      codesign --force --sign - "$f" 2>/dev/null || true
      ((patched++)) || true
    else
      echo "  FAILED: $f" >&2
      ((failed++)) || true
    fi
  else
    ((skipped++)) || true
  fi
done < <(find "$APP" \( -name "*.so" -o -name "*.dylib" \) -print0)

# Re-sign the main executable too (it may have been affected indirectly)
main_exe="$APP/Contents/MacOS/$(basename "${APP%.app}")"
if [ -f "$main_exe" ]; then
  codesign --force --sign - "$main_exe" 2>/dev/null || true
fi

# Re-sign the bundle as a whole
codesign --force --deep --sign - "$APP" 2>/dev/null || true

echo ""
echo "Done."
echo "  Patched : $patched"
echo "  Skipped : $skipped (already ≤ $TARGET or no LC_BUILD_VERSION)"
echo "  Failed  : $failed"
echo ""
echo "Verify with:"
echo "  find \"$APP\" \\( -name '*.so' -o -name '*.dylib' \\) | xargs -I{} sh -c 'vtool -show \"{}\" 2>/dev/null | grep -q \"minos 15\" && echo \"STILL 15: {}\"' | head"
