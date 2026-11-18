# setid

Find out which tracks are played in a SoundCloud DJ set. Give setid the set's link and it lists every track it recognises with the time it starts, plus Spotify and Shazam links.

It runs on a Mac, in the Terminal app.

## Install

1. Open **Terminal**: press ⌘ Space, type `Terminal` and press Return.
2. Paste this line and press Return:

```bash
curl -LsSf https://raw.githubusercontent.com/TimoWestland/soundcloud-track-id/main/install.sh | sh
```

3. When it says **setid is installed**, close the window and open a new Terminal window.

That's all. The installer sets up [uv](https://docs.astral.sh/uv/), which brings its own Python, and puts the `setid` command in `~/.local/bin`. You don't need Homebrew, Python or git.

## First run

Copy a set's link from SoundCloud and run:

```bash
setid https://soundcloud.com/artist/some-set --step 90
```

setid downloads the set, sends short snippets to Shazam one at a time, and prints the tracklist when it's done. A one-hour set takes about 12 minutes, a two-hour set about 24. You can keep using your Mac while it runs.

The tracklist is saved to the **Music → setid** folder in your home folder (`~/Music/setid`), as a `.md` file you can open in any text editor and a `.json` file with all the data.

## Options

Run `setid --help` to see these in Terminal.

| Option | Default | What it does |
|---|---|---|
| `--start` | start of set | analyse from this time (`1:50:00`, `57:30` or seconds) |
| `--end` | end of set | analyse up to this time |
| `--budget` | 20 | target run time in minutes. setid spaces the snippets so the set fits, never closer than 90 seconds apart. |
| `--step` | from `--budget` | seconds between snippets. Overrides `--budget`. Lower finds more short tracks but takes longer. |
| `--snippet` | 12 | length of each snippet in seconds. Shazam only uses 10, so leave it. |
| `--pace` | 15 | seconds between Shazam requests. Going faster gets you blocked by Shazam for a while. |
| `--min-unknown` | 2 × step | a gap this long with no match becomes an `Unknown ID` row |
| `--copy` | off | also copy the tracklist to the clipboard |
| `--copy-spotify` | off | copy the Spotify track links, one per line. Paste them into a Spotify playlist to add every track. Needs the Spotify settings below. |
| `--notion` | off | also create a Notion page with the tracklist. Needs the Notion settings below. |
| `--strict` | off | only keep a track when two snippets in a row agree. Fewer wrong matches, but it can drop real tracks. |

## Examples

A whole set, where tracks play for at least 3 minutes:

```bash
setid https://soundcloud.com/artist/some-set --step 90
```

One track you heard around 1:57 into the set:

```bash
setid https://soundcloud.com/artist/some-set --start 1:50:00 --end 2:05:00 --step 30
```

A set with fast mixing:

```bash
setid https://soundcloud.com/artist/some-set --step 30
```

Copy the tracks for a Spotify playlist, or send the tracklist to Notion:

```bash
setid https://soundcloud.com/artist/some-set --step 90 --copy-spotify
```

```bash
setid https://soundcloud.com/artist/some-set --step 90 --notion
```

## Spotify links (optional)

Without this, the Spotify column holds search links. With it, setid finds the exact Spotify track, and `--copy-spotify` works. It needs a free Spotify developer app, which takes about two minutes:

1. Sign in at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) with your Spotify account and select **Create app**. Any name and description work. Tick **Web API**. If it asks for a redirect URI, enter `http://127.0.0.1:8888/callback` (setid never uses it).
2. Open the app's **Settings** and copy the **Client ID** and **Client secret**.
3. In Terminal, paste these two lines with your own values and press Return:

```bash
echo 'export SPOTIFY_CLIENT_ID=paste-client-id-here' >> ~/.zshrc
echo 'export SPOTIFY_CLIENT_SECRET=paste-client-secret-here' >> ~/.zshrc
```

4. Open a new Terminal window.

This stores `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` in `~/.zshrc`. Keep the secret to yourself.

## Notion pages (optional)

`--notion` creates one Notion page per run, with the set's title as the page title and the tracklist as its content.

1. Open [notion.so/developers/tokens](https://www.notion.so/developers/tokens), select **New token**, give it a name, tick **Notion API**, pick **1 year** as the expiration and select **Create token**. Copy it right away; Notion shows it only once.
2. Open the Notion page the tracklists should go under, select **Share → Copy link**, and copy the 32 letters and numbers at the end of the link. That's the page ID.
3. In Terminal, paste these two lines with your own values and press Return:

```bash
echo 'export NOTION_TOKEN=paste-token-here' >> ~/.zshrc
echo 'export NOTION_SOUNDCLOUD_PAGE_ID=paste-page-id-here' >> ~/.zshrc
```

4. Open a new Terminal window.

This stores `NOTION_TOKEN` and `NOTION_SOUNDCLOUD_PAGE_ID`. Without the page ID, pages land in your Private section. The token can read and edit everything you can in Notion, so keep it to yourself.

## Updating

Run the install line again. It replaces setid with the latest version.

## Uninstalling

Paste this in Terminal:

```bash
rm ~/.local/bin/setid && rm -rf ~/Library/Caches/setid
```

Your tracklists stay in `~/Music/setid`; delete that folder too if you don't want them.

## Limits

- Shazam's catalogue decides what gets found. Unreleased tracks, edits and bootlegs come back as `Unknown ID`.
- Start times are on the `--step` grid, and long blends can shift them by up to one step.
- Each snippet is a request to Shazam's unofficial endpoint, which allows about 5 per minute. If you get blocked, setid waits a minute and retries.
- Downloading from SoundCloud with yt-dlp and using Shazam's unofficial endpoint sit outside those services' terms. Personal use only.

## Development

Work on a local copy and link it as the `setid` command, so edits take effect straight away. Don't run the install line on this machine afterwards: it refuses to replace the link.

```bash
ln -s "$PWD/setid.py" ~/.local/bin/setid
```

Tests:

```bash
python3 test_setid.py
```

```bash
sh test_install.sh
```

`test_install.sh` installs into a throwaway home folder, so it downloads uv, Python and the packages each time (about a minute).
