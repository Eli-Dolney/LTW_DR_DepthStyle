#!/usr/bin/env bash
# Copy the LTW Depth Style script into DaVinci Resolve's Scripts folder.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

if [[ "$(uname -s)" == "Darwin" ]]; then
  DEST="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit"
elif [[ "$(uname -s)" == "Linux" ]]; then
  DEST="$HOME/.local/share/DaVinciResolve/Fusion/Scripts/Edit"
else
  echo "Windows: run install.bat, or copy scripts/*.py to:"
  echo "  %APPDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Fusion\\Scripts\\Edit"
  exit 1
fi

mkdir -p "$DEST"
cp "$ROOT/scripts/ltw_depth_style.py" "$DEST/"
cp "$ROOT/scripts/ltw_depth_lib.py" "$DEST/"
echo "Installed:"
echo "  $DEST/ltw_depth_style.py"
echo "  $DEST/ltw_depth_lib.py"
echo
echo "Restart DaVinci Resolve, then: Workspace → Scripts → Edit → ltw_depth_style"
