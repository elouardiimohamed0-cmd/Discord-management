#!/usr/bin/env bash
set -e

echo "Installing Playwright browsers..."
export PLAYWRIGHT_CHROMIUM_USE_HEADLESS_SHELL=0
playwright install chromium

echo "Verifying browser installation..."
find ~/.cache/ms-playwright -name "chrome*" -type f | head -5

echo "Build complete!"
