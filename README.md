# setid

Local, set79-style tracklist generator for SoundCloud DJ sets. Paste a set URL, get the tracks with the time they start, and links where Shazam knows them.

## Requirements

- macOS with [ffmpeg](https://ffmpeg.org) (`brew install ffmpeg`)
- [uv](https://docs.astral.sh/uv/) (`brew install uv`). It installs `yt-dlp` and `shazamio` on first run, nothing else to set up.

## Usage

```bash
./setid.py https://soundcloud.com/artist/some-set
```

To run it from any folder as `setid`, link it into a directory on your PATH (`~/.local/bin` here):

```bash
ln -s ~/Documents/Projects/Code/setid/setid.py ~/.local/bin/setid
setid https://soundcloud.com/artist/some-set
```

Output and the download cache stay in this project folder wherever you run it from.

To find one track, analyse only the minutes around it, with snippets close together:

```bash
setid https://soundcloud.com/artist/some-set --start 1:50:00 --end 2:05:00 --step 30
```

The markdown tracklist prints in the terminal and is saved to `tracklists/<set title>.md`, with the full data in `.json`. Downloaded audio is cached in `.cache/`, so a re-run skips the download.

Options:

| Flag | Default | Meaning |
|---|---|---|
| `--start` | 0:00 | analyse from this time (`h:mm:ss`, `mm:ss` or seconds) |
| `--end` | end of set | analyse up to this time |
| `--budget` | 20 | target run time in minutes. The script spaces the snippets so the whole set fits, never closer than 90 s apart, which gives every track of 3 minutes or more two snippets. |
| `--step` | from `--budget` | seconds between snippets. Overrides `--budget`; lower is more precise and slower. |
| `--snippet` | 12 | snippet length sent to Shazam |
| `--pace` | 15 | seconds between Shazam requests, about 3 per minute. Shazam blocks at about 5 per minute per IP. |
| `--min-unknown` | 2 x step | a gap of at least this many seconds becomes an `Unknown ID` row |
| `--copy` | off | also copy the markdown tracklist to the clipboard |
| `--copy-spotify` | off | copy the Spotify track links, one per line. Paste them into a playlist in the Spotify desktop app to add every track. Needs Spotify credentials, see below. |
| `--notion` | off | also create a Notion page with the tracklist. The set title becomes the page title. Needs a Notion token, see below. |
| `--strict` | off | keep a track only when two neighbouring snippets agree. Fewer false positives, but it drops any track that only one snippet matched clearly. |

Snippets go to Shazam one at a time, about one every 18 seconds, which keeps well under Shazam's rate limit. A set up to about 100 minutes is sampled every 90 seconds (a 90-minute set takes about 18 minutes). Longer sets get wider spacing so the run stays near 20 minutes: a 2-hour set is sampled every 110 seconds. The spacing assumes tracks play for at least 3 minutes; for sets with faster mixing, pass `--step 30`. Rate-limit waits come on top of the budget: the script waits a minute and retries, and a block from an earlier burst can take a while to clear.

## Spotify track links

Shazam only gives Spotify search links, and a playlist ignores those. With Spotify credentials set, setid looks up each track by its ISRC (from Shazam) and uses the exact `open.spotify.com/track/...` link in the tracklist and for `--copy-spotify`. Tracks Spotify doesn't have keep the search link and are left out of the copied list.

1. Sign in at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) and create an app. Any name works; tick Web API. If it asks for a redirect URI, use `http://127.0.0.1:8888/callback` (setid never uses it).
2. Open the app's settings and copy the Client ID and Client secret.
3. Add them to `~/.zshrc` and open a new terminal:

```bash
export SPOTIFY_CLIENT_ID=your-client-id
export SPOTIFY_CLIENT_SECRET=your-client-secret
```

Without them setid works as before, with search links.

## Notion pages

`--notion` creates one page per run, with the set title as the page title and the rest of the markdown as its content. It uses a Notion personal access token, which acts as you, so it can write anywhere you can.

1. Open Personal access tokens in the [Notion developer portal](https://developers.notion.com), select **New token**, give it a name, tick the **Notion API** capability and create it. Copy the token; Notion shows it only once.
2. Pick the page the tracklists should go under and copy its ID: the 32 characters at the end of the page's link.
3. Add both to `~/.zshrc` and open a new terminal:

```bash
export NOTION_TOKEN=your-token
export NOTION_SOUNDCLOUD_PAGE_ID=your-page-id
```

Without `NOTION_SOUNDCLOUD_PAGE_ID` the pages land in your Private section. If Notion rejects a page, setid prints Notion's error; the tracklist files are saved either way.

## Limits

- Shazam's catalog decides what gets found. Unreleased tracks, edits and bootlegs come back as `Unknown ID`.
- Start times are on the `--step` grid and long blends can shift them by up to one step.
- Links are whatever Shazam returns: the Shazam page, Apple Music when known, and a Spotify search link when Shazam says the track is on Spotify. The `.md` file shows the Spotify and Shazam links; the terminal and `.json` also have Apple Music. No SoundCloud or YouTube search.
- yt-dlp downloads and the unofficial Shazam endpoint sit outside those services' terms. Personal, local use only.

## Test

```bash
python3 test_setid.py
```
