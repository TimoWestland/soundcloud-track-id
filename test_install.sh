#!/bin/sh
# Installs setid into a throwaway home folder with nothing on PATH, the way a fresh Mac would. Run: sh test_install.sh
set -eu
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
CLEAN_PATH=/usr/bin:/bin:/usr/sbin:/sbin

out=$(env -i HOME="$T" PATH="$CLEAN_PATH" SETID_URL="file://$PWD/setid.py" sh install.sh 2>&1) || { echo "$out"; echo "FAIL: install exited non-zero"; exit 1; }
[ -x "$T/.local/bin/setid" ] && [ ! -L "$T/.local/bin/setid" ] || { echo "FAIL: setid not installed as an executable file"; exit 1; }
echo "$out" | grep -q "open a new Terminal window" || { echo "$out"; echo "FAIL: no new-window hint"; exit 1; }
# a bare Mac has no compiler, so every package must come as a ready-made wheel
if echo "$out" | grep -q "Building "; then echo "$out" | grep "Building "; echo "FAIL: a package was compiled from source"; exit 1; fi
env -i HOME="$T" PATH="$T/.local/bin:/usr/bin:/bin" "$T/.local/bin/setid" --help | grep -q "Examples:" || { echo "FAIL: setid --help"; exit 1; }

ln -sf "$PWD/setid.py" "$T/.local/bin/setid"
if out=$(env -i HOME="$T" PATH="$CLEAN_PATH" SETID_URL="file://$PWD/setid.py" sh install.sh 2>&1); then
    echo "FAIL: install ran over a symlink"; exit 1
fi
echo "$out" | grep -q "symlink" || { echo "$out"; echo "FAIL: symlink refusal message"; exit 1; }
[ -L "$T/.local/bin/setid" ] || { echo "FAIL: symlink was replaced"; exit 1; }

echo "install test ok"
