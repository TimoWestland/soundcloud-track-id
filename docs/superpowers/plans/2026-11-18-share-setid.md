# Share setid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A friend with a bare Mac installs setid with one Terminal line from the public GitHub repo, and the README and `setid --help` both document every option.

**Architecture:** setid stays a single uv script (`setid.py`). A new `install.sh` installs uv when missing and downloads `setid.py` to `~/.local/bin/setid`. ffmpeg comes from the `imageio-ffmpeg` package, and output moves out of the script's folder into `~/Music/setid` and `~/Library/Caches/setid`.

**Tech Stack:** Python 3.11+ run by uv (inline script metadata), POSIX `sh`, git and the `gh` CLI.

**Spec:** `docs/superpowers/specs/2026-11-18-share-setid-design.md`

## Global Constraints

- macOS only; no Windows or Linux code paths.
- The friend needs nothing preinstalled except what macOS ships (`curl`, `sh`). No Homebrew, Xcode, git or system Python.
- Install command: `curl -LsSf https://raw.githubusercontent.com/TimoWestland/soundcloud-track-id/main/install.sh | sh`
- Script install location: `~/.local/bin/setid`. Output: `~/Music/setid`. Cache: `~/Library/Caches/setid`.
- Settings names, unchanged: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `NOTION_TOKEN`, `NOTION_SOUNDCLOUD_PAGE_ID`.
- Never commit `.cache/`, `tracklists/`, `.claude/`, `__pycache__/` or any key.
- Tests run with `python3 test_setid.py` (stdlib only at import; third-party imports stay inside functions).
- Commits: conventional format (`feat:`, `fix:`, `docs:`, `chore:`), no attribution lines.
- Sharing work happens on branch `feat/share-setid` in the worktree `.claude/worktrees/share-setid`, never tracking `origin/main`, and lands through a PR.

## Review Focus

- Timo runs `install.sh` himself while `~/.local/bin/setid` is his symlink to the working copy: the script must stop with a message and leave the symlink alone (Task 5 test).
- She runs `setid` in the same Terminal window right after installing, before `~/.local/bin` is on PATH: the installer must call setid by its full path for the warm-up and tell her to open a new window (Task 5 test checks the message).
- README and `--help` drift apart when a flag is added later: a test fails when a parser flag is missing from the README (Task 4).
- No ffmpeg anywhere on her PATH: snippets must still be cut using the bundled binary (Task 3 verification with a stripped PATH).
- `~/Music/setid` or `~/Library/Caches/setid` doesn't exist yet on first run: both are created with their parents (Task 2 test).

---

### Task 1: Put the current code on GitHub

**Files:**
- Create: `.gitignore`

**Interfaces:**
- Produces: `main` on `origin` (https://github.com/TimoWestland/soundcloud-track-id) holding today's `setid.py`, `test_setid.py`, `README.md` and `docs/`.

- [ ] **Step 1: Write `.gitignore`** with exactly these lines: `.cache/`, `tracklists/`, `.claude/`, `__pycache__/`, `.DS_Store`.

- [ ] **Step 2: Initialise the repo and check nothing private is staged**

Run: `git init -b main && git add -A && git status --short`
Expected: only `.gitignore`, `README.md`, `setid.py`, `test_setid.py` and the two `docs/superpowers/...` files. Also run `git grep -nE "SPOTIFY_CLIENT_SECRET=|NOTION_TOKEN=[a-z0-9_]{20,}"` and expect only placeholder values such as `your-token`.

- [ ] **Step 3: Commit, add the remote and push**

```bash
git commit -m "chore: initial import of setid"
git remote add origin https://github.com/TimoWestland/soundcloud-track-id.git
git push -u origin main
```
Expected: `gh repo view TimoWestland/soundcloud-track-id --json isEmpty` prints `"isEmpty":false`.

- [ ] **Step 4: Create the worktree for the remaining tasks**

Run: `git worktree add .claude/worktrees/share-setid -b feat/share-setid --no-track main`
Expected: the worktree exists; `git -C .claude/worktrees/share-setid rev-parse --abbrev-ref @{u}` fails (no upstream). All later tasks run inside this worktree.

---

### Task 2: Move output and cache to standard Mac folders

**Files:**
- Modify: `setid.py:27-29` (path constants), `setid.py:117` (`download`), `setid.py:340` (`main`)
- Test: `test_setid.py`

**Interfaces:**
- Produces: module constants `OUT_DIR = Path.home() / "Music" / "setid"` and `CACHE_DIR = Path.home() / "Library" / "Caches" / "setid"`. `PROJECT_DIR` is removed.

- [ ] **Step 1: Write the failing test `test_output_and_cache_dirs`**

```python
def test_output_and_cache_dirs() -> None:
    assert setid.OUT_DIR == Path.home() / "Music" / "setid"
    assert setid.CACHE_DIR == Path.home() / "Library" / "Caches" / "setid"
    assert not hasattr(setid, "PROJECT_DIR")
```
(Add `import setid` and `from pathlib import Path` at the top of the test file.)

- [ ] **Step 2: Run it to see it fail**

Run: `python3 test_setid.py`
Expected: `AssertionError` from `test_output_and_cache_dirs`.

- [ ] **Step 3: Change the constants, and make both `mkdir` calls `mkdir(parents=True, exist_ok=True)`.**

- [ ] **Step 4: Run the tests**

Run: `python3 test_setid.py`
Expected: all `ok`.

- [ ] **Step 5: Move Timo's existing cache so it isn't downloaded again**

Run: `mkdir -p ~/Library/Caches/setid && mv ~/Documents/Projects/Code/setid/.cache/* ~/Library/Caches/setid/`
Expected: three `.m4a` files in `~/Library/Caches/setid`. Leave `tracklists/` where it is (per the spec).

- [ ] **Step 6: Commit**

```bash
git add setid.py test_setid.py
git commit -m "feat: write tracklists to ~/Music/setid and cache to ~/Library/Caches/setid"
```

---

### Task 3: Bundle ffmpeg

**Files:**
- Modify: `setid.py` (script metadata line 4, `snippet()` around line 134)

**Interfaces:**
- Produces: `snippet(audio: Path, offset: int, length: int) -> bytes` keeps its signature and now runs `imageio_ffmpeg.get_ffmpeg_exe()` instead of `"ffmpeg"`.

- [ ] **Step 1: Add `"imageio-ffmpeg>=0.6,<0.9"` to the `dependencies` list** in the `# /// script` block.

- [ ] **Step 2: In `snippet()`, import `imageio_ffmpeg` inside the function** (keeps the module importable by the stdlib-only tests) and pass `imageio_ffmpeg.get_ffmpeg_exe()` as the program.

- [ ] **Step 3: Run the tests**

Run: `python3 test_setid.py`
Expected: every test prints `ok`.

- [ ] **Step 4: Verify with no ffmpeg on PATH**

Run: `env PATH=/usr/bin:/bin:$HOME/.local/bin ./setid.py https://soundcloud.com/kioskradio/call-super-kiosk-x-the-lot --start 10:00 --end 11:00 --step 30`
Expected: 2 snippets analysed from the cache Task 2 moved (no download), a tracklist printed, no `ffmpeg` not-found error. (`command -v ffmpeg` under that PATH prints nothing.) Delete the window's tracklist files afterwards.

- [ ] **Step 5: Commit**

```bash
git add setid.py
git commit -m "feat: bundle ffmpeg through imageio-ffmpeg"
```

---

### Task 4: Help text with examples and settings

**Files:**
- Modify: `setid.py` (`main()`, around lines 308-323)
- Test: `test_setid.py`

**Interfaces:**
- Produces: `build_parser() -> argparse.ArgumentParser`, holding every argument now added inline in `main()`. `main()` calls `build_parser().parse_args()`.
- Produces: `HELP_EPILOG: str`, rendered with `argparse.RawDescriptionHelpFormatter`.

- [ ] **Step 1: Write the failing tests**

```python
SETTINGS = ["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "NOTION_TOKEN", "NOTION_SOUNDCLOUD_PAGE_ID"]

def long_flags() -> list[str]:
    return [o for a in setid.build_parser()._actions for o in a.option_strings if o.startswith("--") and o != "--help"]

def test_help_lists_flags_settings_and_examples() -> None:
    text = setid.build_parser().format_help()
    for name in long_flags() + SETTINGS:
        assert name in text, name
    assert "Examples:" in text and "setid https://soundcloud.com/" in text

def test_readme_lists_every_flag_and_setting() -> None:
    readme = (Path(__file__).parent / "README.md").read_text()
    for name in long_flags() + SETTINGS:
        assert f"`{name}`" in readme, name
```

- [ ] **Step 2: Run them to see them fail**

Run: `python3 test_setid.py`
Expected: `AttributeError: module 'setid' has no attribute 'build_parser'`.

- [ ] **Step 3: Extract `build_parser()` and add `HELP_EPILOG`.** The epilog has an `Examples:` block (whole set with `--step 90`, a window with `--start 1:50:00 --end 2:05:00 --step 30`, `--copy-spotify`, `--notion`), a `Settings (optional):` block naming the four variables with one line each on what they turn on, and a final line saying where tracklists are saved (`~/Music/setid`).

- [ ] **Step 4: Run the tests**

Run: `python3 test_setid.py`
Expected: `test_help_lists_flags_settings_and_examples` passes. `test_readme_lists_every_flag_and_setting` may still fail until Task 6 rewrites the README; note which flags it names.

- [ ] **Step 5: Commit**

```bash
git add setid.py test_setid.py
git commit -m "feat: list examples and settings in --help"
```

---

### Task 5: One-line installer

**Files:**
- Create: `install.sh`
- Test: `test_install.sh`

**Interfaces:**
- Consumes: `setid.py` from Tasks 2-4 (downloaded, never imported).
- Produces: `install.sh`, which honours `SETID_URL` (default `https://raw.githubusercontent.com/TimoWestland/soundcloud-track-id/main/setid.py`) so it can be tested against a local file before merge.

- [ ] **Step 1: Write the failing test script `test_install.sh`** (POSIX `sh`, `set -eu`), which:
  1. makes a throwaway home with `mktemp -d`;
  2. runs `env -i HOME="$T" PATH=/usr/bin:/bin:/usr/sbin:/sbin SETID_URL="file://$PWD/setid.py" sh install.sh` and checks it exits 0;
  3. checks `"$T/.local/bin/setid"` is an executable regular file and that the installer's output contains `open a new Terminal window`;
  4. checks `env -i HOME="$T" PATH="$T/.local/bin:/usr/bin:/bin" "$T/.local/bin/setid" --help` prints `Examples:`;
  5. replaces it with a symlink (`ln -sf "$PWD/setid.py" "$T/.local/bin/setid"`), runs the installer again, and checks it exits non-zero, mentions `symlink`, and leaves the link in place;
  6. removes the throwaway home and prints `install test ok`.

- [ ] **Step 2: Run it to see it fail**

Run: `sh test_install.sh`
Expected: fails because `install.sh` doesn't exist.

- [ ] **Step 3: Write `install.sh`** (`#!/bin/sh`, `set -eu`), in this order:
  - stop with a message mentioning `symlink` when `~/.local/bin/setid` is a symlink (Timo's development link);
  - when `uv` isn't on PATH and `~/.local/bin/uv` doesn't exist, run Astral's installer: `curl -LsSf https://astral.sh/uv/install.sh | sh`;
  - prepend `$HOME/.local/bin` to PATH for the rest of the script;
  - `mkdir -p ~/.local/bin`, download `$SETID_URL` with `curl -fsSL` to `~/.local/bin/setid`, then `chmod +x`;
  - warm up with `"$HOME/.local/bin/setid" --help >/dev/null` (installs Python and packages on first run; print a line saying this can take a minute);
  - finish with: open a new Terminal window, then run `setid --help`; where tracklists go; re-run the same install line to update.

- [ ] **Step 4: Run the test**

Run: `sh test_install.sh`
Expected: `install test ok`. (The first run downloads uv, Python and packages into the throwaway home, so allow a few minutes.)

- [ ] **Step 5: Commit**

```bash
git add install.sh test_install.sh
git commit -m "feat: add one-line installer"
```

---

### Task 6: README for a first-time user

**Files:**
- Modify: `README.md` (rewrite)

**Interfaces:**
- Consumes: flag names from `build_parser()` (Task 4), the install line and folders from Global Constraints.

- [ ] **Step 1: Rewrite `README.md`** for someone who has never used Terminal, in this order:
  1. what setid does, in two sentences;
  2. **Install:** open Terminal (Spotlight, type "Terminal"), paste the install line, open a new Terminal window;
  3. **First run:** one example, what she'll see, where the tracklist is saved (`~/Music/setid`), and how long a run takes;
  4. **Options:** a table with every flag from `--help`, each in backticks;
  5. **Examples:** whole set, one moment in a set, copy for a Spotify playlist, send to Notion;
  6. **Spotify links (optional)** and **Notion pages (optional):** the existing setup steps, written for her own accounts, each variable name in backticks, with how to add it to `~/.zshrc`;
  7. **Updating:** re-run the install line;
  8. **Uninstalling:** delete `~/.local/bin/setid`, `~/Music/setid`, `~/Library/Caches/setid`;
  9. **Limits:** keep the existing points, including personal use only;
  10. **For Timo (development):** the symlink setup and `python3 test_setid.py` and `sh test_install.sh`.

- [ ] **Step 2: Run the tests**

Run: `python3 test_setid.py`
Expected: all `ok`, including `test_readme_lists_every_flag_and_setting`.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for first-time users"
```

---

### Task 7: Pull request and a real install

**Files:** none

- [ ] **Step 1: Push the branch and open the PR**

Run: `git push -u origin feat/share-setid` then `gh pr create --base main --title "feat: make setid installable with one line" --body "<summary of tasks 2-6 plus a test plan>"`.
Expected: a PR URL. The body ends with no attribution line.

- [ ] **Step 2: After Timo merges, test the real install line in a throwaway home**

Run: `T=$(mktemp -d); env -i HOME="$T" PATH=/usr/bin:/bin:/usr/sbin:/sbin sh -c 'curl -LsSf https://raw.githubusercontent.com/TimoWestland/soundcloud-track-id/main/install.sh | sh' && env -i HOME="$T" PATH="$T/.local/bin:/usr/bin:/bin" "$T/.local/bin/setid" --help | head -3`
Expected: the installer's closing message, then the setid usage line. Remove `$T` afterwards.

- [ ] **Step 3: Remove the worktree** once it has no uncommitted or unpushed changes: `git worktree remove .claude/worktrees/share-setid`.
