#!/bin/sh
# Installs setid on a Mac. Run again to update:
#   curl -LsSf https://raw.githubusercontent.com/TimoWestland/soundcloud-track-id/main/install.sh | sh
set -eu

SETID_URL="${SETID_URL:-https://raw.githubusercontent.com/TimoWestland/soundcloud-track-id/main/setid.py}"
BIN="$HOME/.local/bin"
TARGET="$BIN/setid"

if [ -L "$TARGET" ]; then
    echo "$TARGET is a symlink (a development setup), so it was left alone. Remove it first to install the released setid." >&2
    exit 1
fi

if ! command -v uv >/dev/null 2>&1 && [ ! -x "$BIN/uv" ]; then
    echo "Installing uv (runs setid and brings its own Python)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# uv's installer puts ~/.local/bin on PATH for new windows; add it here too when uv was already installed elsewhere
case ":$PATH:" in
    *":$BIN:"*) ;;
    *)
        if ! grep -qs '.local/bin' "$HOME/.zshrc"; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
        fi
        PATH="$BIN:$PATH"
        export PATH
        ;;
esac

echo "Downloading setid..."
mkdir -p "$BIN"
curl -fsSL "$SETID_URL" -o "$TARGET"
chmod +x "$TARGET"

echo "Preparing setid's packages (the first time can take a minute)..."
"$TARGET" --help >/dev/null

cat <<'DONE'

setid is installed.

  1. Close this window and open a new Terminal window.
  2. Run: setid --help

Tracklists are saved to ~/Music/setid.
To update setid later, run the same install line again.
DONE
