#!/bin/bash
#
# Build WhisperKey Debian Package
# This script creates a .deb package for Ubuntu/Debian systems
#

set -e

# Configuration
VERSION="0.2.1"
PACKAGE_NAME="whisperkey"
EXTENSION_UUID="whisperkey@whisperkey.app"
BUILD_ROOT="debian-package"
DIST_DIR="dist"
APP_DIR="app"

echo "=========================================="
echo "  Building WhisperKey v${VERSION}"
echo "  Debian Package Builder"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "Makefile" ] || [ ! -d "$APP_DIR" ]; then
    echo "❌ Error: Must run from repository root"
    echo "   Current directory: $(pwd)"
    exit 1
fi

# Check for required tools
echo "🔍 Checking build dependencies..."
MISSING_TOOLS=()

if ! command -v dpkg-deb >/dev/null 2>&1; then
    MISSING_TOOLS+=("dpkg-deb")
fi

if ! command -v uv >/dev/null 2>&1; then
    MISSING_TOOLS+=("uv")
fi

if ! command -v glib-compile-schemas >/dev/null 2>&1; then
    MISSING_TOOLS+=("glib-compile-schemas (libglib2.0-dev)")
fi

if [ ${#MISSING_TOOLS[@]} -ne 0 ]; then
    echo "❌ Missing required tools:"
    for tool in "${MISSING_TOOLS[@]}"; do
        echo "   - $tool"
    done
    echo ""
    echo "Install with:"
    echo "   sudo apt-get install dpkg-dev libglib2.0-dev"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✅ All build dependencies found"
echo ""

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT/DEBIAN"
mkdir -p "$BUILD_ROOT/usr/share/whisperkey"
mkdir -p "$BUILD_ROOT/usr/share/doc/whisperkey"
mkdir -p "$DIST_DIR"
echo "✅ Build directories prepared"
echo ""

# Build Python application
echo "📦 Building Python application..."
cd "$APP_DIR"

echo "   Syncing dependencies..."
uv sync

echo "   Building wheel..."
uv build

# Find the built wheel
WHEEL_FILE=$(ls dist/*.whl | head -n1)
if [ -z "$WHEEL_FILE" ]; then
    echo "❌ Error: Wheel file not found"
    exit 1
fi

echo "   ✅ Built: $(basename $WHEEL_FILE)"
cd ..
echo ""

# Copy wheel to package
echo "📋 Copying application files..."
cp "$APP_DIR/$WHEEL_FILE" "$BUILD_ROOT/usr/share/whisperkey/"
echo "   ✅ Python wheel copied"

# Copy extension files
echo "   Copying GNOME extension..."
mkdir -p "$BUILD_ROOT/usr/share/whisperkey/extension"
cp -r extension/* "$BUILD_ROOT/usr/share/whisperkey/extension/"

# Compile extension schemas
if [ -d "$BUILD_ROOT/usr/share/whisperkey/extension/schemas" ]; then
    echo "   Compiling extension schemas..."
    glib-compile-schemas "$BUILD_ROOT/usr/share/whisperkey/extension/schemas"
fi
echo "   ✅ Extension files copied"

# Copy documentation
echo "   Copying documentation..."
cp README.md "$BUILD_ROOT/usr/share/doc/whisperkey/"
cp LICENSE "$BUILD_ROOT/usr/share/doc/whisperkey/"
cp CHANGELOG.md "$BUILD_ROOT/usr/share/doc/whisperkey/" 2>/dev/null || true

# Create copyright file
cat > "$BUILD_ROOT/usr/share/doc/whisperkey/copyright" << EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: whisperkey
Upstream-Contact: WhisperKey Team <support@whisperkey.app>
Source: https://github.com/yourusername/voxvibe

Files: *
Copyright: 2024 WhisperKey Team
License: MIT
 Permission is hereby granted, free of charge, to any person obtaining a
 copy of this software and associated documentation files (the "Software"),
 to deal in the Software without restriction, including without limitation
 the rights to use, copy, modify, merge, publish, distribute, sublicense,
 and/or sell copies of the Software, and to permit persons to whom the
 Software is furnished to do so, subject to the following conditions:
 .
 The above copyright notice and this permission notice shall be included
 in all copies or substantial portions of the Software.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
 OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
 THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
 DEALINGS IN THE SOFTWARE.
EOF

echo "   ✅ Documentation copied"
echo ""

# Copy DEBIAN control files
echo "📋 Setting up package metadata..."

# Create DEBIAN directory structure
mkdir -p "$BUILD_ROOT/DEBIAN"

# Copy control files if they exist in the source
if [ -f "debian-source/DEBIAN/control" ]; then
    cp debian-source/DEBIAN/control "$BUILD_ROOT/DEBIAN/"
    cp debian-source/DEBIAN/postinst "$BUILD_ROOT/DEBIAN/"
    cp debian-source/DEBIAN/prerm "$BUILD_ROOT/DEBIAN/"
    cp debian-source/DEBIAN/postrm "$BUILD_ROOT/DEBIAN/"
    echo "   ✅ Control files copied from debian-source/"
else
    # Create control files inline if they don't exist
    cat > "$BUILD_ROOT/DEBIAN/control" << 'CTRLEOF'
Package: whisperkey
Version: 0.2.1
Section: sound
Priority: optional
Architecture: all
Depends: python3 (>= 3.11), python3-pip, python3-dev, portaudio19-dev, pipx, gnome-shell (>= 42), gir1.2-glib-2.0, ydotool
Recommends: python3-venv
Suggests: pulseaudio
Maintainer: WhisperKey Team <support@whisperkey.app>
Homepage: https://github.com/yourusername/voxvibe
Description: Fast voice transcription with global hotkeys for Linux
 WhisperKey is a unified Python application that provides instant 
 speech-to-text transcription with global hotkeys. Simply hold Win+Alt 
 and speak - WhisperKey will transcribe your speech and paste it 
 directly where you need it.
 .
 Features:
  * Ultra-fast pasting (0.25s response time)
  * Global hotkeys - Works anywhere in the system
  * Transcription history - Access recent transcriptions via tray menu
  * Auto-startup - Runs automatically when you log in
  * Native Wayland & X11 support
  * Clean system tray integration
CTRLEOF

    echo "   ⚠️  Using embedded control files"
fi

echo ""

# Calculate installed size
echo "📏 Calculating package size..."
INSTALLED_SIZE=$(du -sk "$BUILD_ROOT" | cut -f1)

# Only add Installed-Size if not already present
if ! grep -q "^Installed-Size:" "$BUILD_ROOT/DEBIAN/control"; then
    echo "Installed-Size: $INSTALLED_SIZE" >> "$BUILD_ROOT/DEBIAN/control"
fi

echo "   Package size: ${INSTALLED_SIZE}KB"
echo ""

# Set correct permissions
echo "🔒 Setting file permissions..."
find "$BUILD_ROOT" -type f -exec chmod 644 {} \;
find "$BUILD_ROOT" -type d -exec chmod 755 {} \;

# Set executable permissions for maintainer scripts if they exist
if [ -f "$BUILD_ROOT/DEBIAN/postinst" ]; then
    chmod 755 "$BUILD_ROOT/DEBIAN/postinst"
fi
if [ -f "$BUILD_ROOT/DEBIAN/prerm" ]; then
    chmod 755 "$BUILD_ROOT/DEBIAN/prerm"
fi
if [ -f "$BUILD_ROOT/DEBIAN/postrm" ]; then
    chmod 755 "$BUILD_ROOT/DEBIAN/postrm"
fi

echo "   ✅ Permissions set"
echo ""

# Build the .deb package
echo "🔨 Building .deb package..."
DEB_FILE="${DIST_DIR}/${PACKAGE_NAME}_${VERSION}_all.deb"

dpkg-deb --build "$BUILD_ROOT" "$DEB_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "  ✅ Build Complete!"
    echo "=========================================="
    echo ""
    echo "📦 Package created: $DEB_FILE"
    echo ""
    echo "Package details:"
    dpkg-deb --info "$DEB_FILE" | head -n 20
    echo ""
    echo "📊 Package size: $(du -h "$DEB_FILE" | cut -f1)"
    echo ""
    echo "🚀 Installation instructions:"
    echo "   1. Install the package:"
    echo "      sudo dpkg -i $DEB_FILE"
    echo ""
    echo "   2. Fix any missing dependencies:"
    echo "      sudo apt-get install -f"
    echo ""
    echo "   3. Log out and back in to activate"
    echo ""
    echo "📝 To uninstall:"
    echo "   sudo apt-get remove $PACKAGE_NAME"
    echo ""
    echo "📝 To purge all configuration:"
    echo "   sudo apt-get purge $PACKAGE_NAME"
    echo ""
else
    echo "❌ Error building package"
    exit 1
fi

