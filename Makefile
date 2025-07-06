# Root Makefile for Whisper Key Monorepo

# Configuration
VERSION := 0.2.0
EXTENSION_UUID := whisperkey@whisperkey.app
PYTHON_APP_DIR := app
BUILD_DIR := build
DIST_DIR := dist

# Detect if we're in the app directory
IS_IN_APP := $(if $(wildcard pyproject.toml),1,0)

# Main targets
.PHONY: all help clean check-tools python extension package dist lint check-version

all: check-tools python
	@echo ""
	@echo "✅ Installation complete!"
	@echo ""
	@echo "🚀 Whisper Key is now installed and ready to use."
	@echo "   • The application will start automatically on login"
	@echo "   • Look for the microphone icon in your system tray"
	@echo "   • Use Win+Alt hotkey to start dictating"
	@echo ""
	@echo "\nSetup complete. Whisper Key standalone application is ready."
	@echo "The application will auto-start on next login."

help:
	@echo ""
	@echo "Whisper Key Makefile Commands:"
	@echo ""
	@echo "Main Commands:"
	@echo "  all          - Setup standalone Whisper Key application (recommended)"
	@echo "  python       - Install Python app only"
	@echo "  extension    - Install GNOME extension only (optional)"
	@echo "  clean        - Remove build artifacts"
	@echo "  package      - Create release package"
	@echo "  dist         - Create distribution build with linting"
	@echo ""
	@echo "Development:"
	@echo "  lint         - Run linting and validation"
	@echo "  check-tools  - Verify required tools are installed"
	@echo "  check-version - Show current version info"
	@echo ""

# Check required tools
check-tools:
	@echo "🔍 Checking required tools..."
	@command -v uv >/dev/null 2>&1 || { echo "❌ uv not found. Install from https://astral.sh/uv/install.sh"; exit 1; }
	@command -v python3 >/dev/null 2>&1 || { echo "❌ python3 not found"; exit 1; }
	@echo "✅ All required tools found"

# Version information  
check-version:
	@echo ""
	@echo "Whisper Key Version Information:"
	@echo "  Project Version: $(VERSION)"
	@echo "  Extension UUID: $(EXTENSION_UUID)"
	@echo "  Python App Dir: $(PYTHON_APP_DIR)"
	@echo ""

# Python application
python: check-tools
	@echo "📦 Installing Python application..."
	cd $(PYTHON_APP_DIR) && uv sync
	cd $(PYTHON_APP_DIR) && uv build
	# Install using pipx for global availability
	@if command -v pipx >/dev/null 2>&1; then \
		echo "📦 Installing globally with pipx..."; \
		pipx install --force $(PYTHON_APP_DIR)/dist/*.whl; \
		echo "Python application installed. The 'whisperkey' command should now be available."; \
	else \
		echo "⚠️  pipx not found. Install manually: pip install $(PYTHON_APP_DIR)/dist/*.whl"; \
	fi
	# Create autostart file
	@./create_autostart.sh

# GNOME extension (optional)
extension:
	@echo "🔌 Installing GNOME extension..."
	@mkdir -p ~/.local/share/gnome-shell/extensions/$(EXTENSION_UUID)
	@cp -r extension/* ~/.local/share/gnome-shell/extensions/$(EXTENSION_UUID)/
	@echo "Extension installed. Please log out and back in, then enable the extension."
	@gnome-extensions enable $(EXTENSION_UUID) || echo "Could not enable extension automatically. Please enable 'Whisper Key' in the GNOME Extensions app."

# Clean build artifacts
clean:
	@echo "🧹 Cleaning build artifacts..."
	@rm -rf $(BUILD_DIR) $(DIST_DIR)
	@cd $(PYTHON_APP_DIR) && rm -rf dist/ build/ *.egg-info/ .venv/
	@echo "✅ Clean complete"

# Create release package  
package: clean python
	@echo "📦 Creating release package..."
	@mkdir -p $(BUILD_DIR)/whisperkey-$(VERSION)
	@mkdir -p $(BUILD_DIR)/whisperkey-$(VERSION)/app
	@mkdir -p $(BUILD_DIR)/whisperkey-$(VERSION)/extension
	@mkdir -p $(DIST_DIR)
	
	# Copy Python wheel
	@cp $(PYTHON_APP_DIR)/dist/*.whl $(BUILD_DIR)/whisperkey-$(VERSION)/app/
	
	# Copy extension files  
	@cp -r extension/* $(BUILD_DIR)/whisperkey-$(VERSION)/extension/
	
	# Copy root files
	@cp README.md LICENSE Makefile $(BUILD_DIR)/whisperkey-$(VERSION)/
	@cp $(PYTHON_APP_DIR)/README.md $(BUILD_DIR)/whisperkey-$(VERSION)/app/
	
	# Create version file
	@echo "Whisper Key $(VERSION)" > $(BUILD_DIR)/whisperkey-$(VERSION)/VERSION
	@echo "Git Commit: $(GIT_COMMIT)" >> $(BUILD_DIR)/whisperkey-$(VERSION)/VERSION
	@echo "Build Date: $(shell date -u +"%Y-%m-%d %H:%M:%S UTC")" >> $(BUILD_DIR)/whisperkey-$(VERSION)/VERSION
	
	# Create install script from template
	@sed -e 's/{{VERSION}}/$(VERSION)/g' -e 's/{{EXTENSION_UUID}}/$(EXTENSION_UUID)/g' install.sh.template > $(BUILD_DIR)/whisperkey-$(VERSION)/install.sh
	@chmod +x $(BUILD_DIR)/whisperkey-$(VERSION)/install.sh
	
	# Create tarball
	@cd $(BUILD_DIR) && tar -czf whisperkey-$(VERSION).tar.gz whisperkey-$(VERSION)/
	@mv $(BUILD_DIR)/whisperkey-$(VERSION).tar.gz $(DIST_DIR)/
	@echo "Release package created: $(DIST_DIR)/whisperkey-$(VERSION).tar.gz"
