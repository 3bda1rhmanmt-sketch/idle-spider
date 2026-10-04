#!/bin/sh
# Install menu entry + icon for the current user (run after `pip install .` / pipx).
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
data="${XDG_DATA_HOME:-$HOME/.local/share}"
mkdir -p "$data/applications" "$data/icons/hicolor/scalable/apps"
cp "$here/packaging/idle-spider.desktop" "$data/applications/"
cp "$here/assets/idle-spider.svg" "$data/icons/hicolor/scalable/apps/"
echo "Installed desktop entry and icon under $data"
echo "Optional systemd user service:"
echo "  mkdir -p ~/.config/systemd/user && cp packaging/idle-spider.service ~/.config/systemd/user/"
echo "  systemctl --user enable --now idle-spider.service"
