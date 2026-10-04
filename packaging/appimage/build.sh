#!/bin/sh
# EXPERIMENTAL: build an AppImage with python-appimage (https://github.com/niess/python-appimage).
# Not part of CI; the PySide6 AppImage is large (~300 MB). Run from the repository root.
set -eu
python3 -m pip install --user build python-appimage
python3 -m build --wheel --outdir packaging/appimage .
wheel=$(ls packaging/appimage/idle_spider-*.whl | head -n1)
printf '%s\nPySide6>=6.6,<7\n' "./$(basename "$wheel")" > packaging/appimage/requirements.txt
cp packaging/idle-spider.desktop packaging/appimage/idle-spider.desktop
cp assets/idle-spider.svg packaging/appimage/idle-spider.svg
cat > packaging/appimage/entrypoint.sh <<'EOS'
#! /bin/bash
{{ python-executable }} -m idle_spider "$@"
EOS
python3 -m python_appimage build app -p 3.12 packaging/appimage
