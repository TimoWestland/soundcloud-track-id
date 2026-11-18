# Share setid with a friend: design

## Intent

A friend with a bare Mac (no Homebrew, Python or git) installs setid with one line in Terminal and uses it like Timo does. The code lives in the public repo https://github.com/TimoWestland/soundcloud-track-id. The README and `setid --help` both list every option.

## Goals

- One Terminal line installs everything setid needs. Re-running the same line updates it.
- The README is written for a non-technical reader: install, first run, every flag, examples, optional Spotify and Notion setup with her own accounts, updating, uninstalling.
- `setid --help` lists every flag, the Spotify and Notion settings, and a few examples.

## Non-goals

- Windows or Linux support.
- PyPI publishing, version numbers, an upgrade command.
- A downloadable app or binary, or a Homebrew formula.

## Anti-goals

- Timo's Spotify or Notion keys, his cached audio or his tracklists ending up in the public repo.
- An install that needs Xcode, git, Homebrew or a separate Python.

## Approaches

- **A. Install script that fetches the single-file script (chosen).** `install.sh` installs uv if missing and downloads `setid.py` to `~/.local/bin/setid`. setid stays one file. Update = re-run the line. Chosen because it adds the least to maintain for one friend.
- **B. Python package via `uv tool install`.** Adds `pyproject.toml`, gives versioning and `uv tool upgrade`, and is PyPI-ready. Rejected for now: more packaging than one friend needs. A can grow into B later.
- **Dropped:** an app or binary (macOS blocks unsigned apps; signing needs an Apple developer account and a release pipeline) and Homebrew (it's the prerequisite we're avoiding).

## Design

1. **`install.sh`**, run with `curl -LsSf https://raw.githubusercontent.com/TimoWestland/soundcloud-track-id/main/install.sh | sh`:
   - installs uv with Astral's official installer when `uv` isn't found (uv brings its own Python);
   - downloads `setid.py` from the repo's `main` branch to `~/.local/bin/setid` and makes it executable;
   - makes sure `~/.local/bin` is on her PATH (uv's installer already adds it to her shell profile);
   - runs `setid --help` once so the first real run doesn't stall on package downloads;
   - prints what to do next.
2. **`setid.py` changes:**
   - ffmpeg comes from the `imageio-ffmpeg` package (bundled builds for Apple Silicon and Intel) instead of a system install.
   - Output moves to `~/Music/setid` and the audio cache to `~/Library/Caches/setid`. *(Claude's call: a normal place she can find; the cache is safe to delete.)*
3. **`--help`:** keeps the argparse flag list and adds an epilog with examples and the `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `NOTION_TOKEN` and `NOTION_SOUNDCLOUD_PAGE_ID` settings.
4. **README:** rewritten for her (see Goals). The flag table matches `--help`. Keeps the Limits section, including the note that yt-dlp and the unofficial Shazam endpoint are for personal use.
5. **Repo:** `git init`, a `.gitignore` for `.cache/`, `tracklists/` and `__pycache__/`, an initial commit of the current code on `main`, pushed. The changes above go on a branch and land through a pull request.

## Effects on Timo's own setup

- His `~/.local/bin/setid` symlink keeps pointing at his working copy, so his edits still take effect straight away. He shouldn't run `install.sh` himself: it would replace the symlink with a downloaded copy.
- His new runs also write to `~/Music/setid`. His existing tracklists stay in the project's `tracklists/` folder.

## Left to the builder

- Exact README and help wording.
- Testing `install.sh` in a throwaway home folder with no uv on PATH, and checking that `--help` and the README list the same flags.
- No license file unless Timo asks for one.
