#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["imageio-ffmpeg>=0.6,<0.9", "shazamio==0.8.1", "shazamio-core>=1.1,<2", "yt-dlp", "audioop-lts; python_version >= '3.13'"]
# ///
"""Identify the tracks in a SoundCloud DJ set, set79-style, from the command line.

Pipeline: yt-dlp download -> ffmpeg snippets -> Shazam -> merge -> table + JSON + Markdown.
"""
import argparse
import asyncio
import base64
import io
import json
import math
import os
import re
import subprocess
import sys
import warnings
import wave
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

CACHE_DIR = Path.home() / "Library" / "Caches" / "setid"
OUT_DIR = Path.home() / "Music" / "setid"
UNKNOWN = "Unknown ID"
RATE_LIMIT_WAIT = 60
SAMPLE_RATE = 16000
NOTION_VERSION = "2026-03-11"
MIN_STEP = 90  # two snippets per track for sets whose tracks play at least 3 minutes
REQUEST_OVERHEAD = 3  # ffmpeg + fingerprint + HTTP per snippet, measured: a 90-min set at step 30 and pace 12 took 45 min
warnings.filterwarnings("ignore", category=SyntaxWarning)  # pydub, pulled in by shazamio, trips this on Python 3.13
warnings.filterwarnings("ignore", message="Couldn't find ffmpeg", category=RuntimeWarning)  # pydub looks for a system ffmpeg setid never uses


@dataclass
class Hit:
    offset: int
    key: str | None = None
    title: str = ""
    artist: str = ""
    links: dict[str, str] = field(default_factory=dict)
    isrc: str | None = None


@dataclass
class Entry:
    start: int
    title: str
    artist: str
    links: dict[str, str]
    isrc: str | None = None


def hms(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_time(value: str) -> int:
    """Accept seconds, mm:ss or h:mm:ss."""
    parts = value.split(":")
    if len(parts) > 3 or not all(p.isdigit() for p in parts):
        raise argparse.ArgumentTypeError(f"not a time: {value!r} (use h:mm:ss, mm:ss or seconds)")
    seconds = 0
    for p in parts:
        seconds = seconds * 60 + int(p)
    return seconds


def auto_step(duration: int, pace: float, budget_min: float) -> int:
    """Widest snippet spacing needed to finish within the budget, never denser than MIN_STEP."""
    max_snippets = max(int(budget_min * 60 // (pace + REQUEST_OVERHEAD)), 1)
    return max(MIN_STEP, math.ceil(duration / max_snippets))


def confirm(hits: list[Hit]) -> list[Hit]:
    """Keep a match only when a neighbouring snippet agrees; lone hits are usually blend noise."""
    out = []
    for i, h in enumerate(hits):
        prev_key = hits[i - 1].key if i > 0 else None
        next_key = hits[i + 1].key if i + 1 < len(hits) else None
        keep = h.key is not None and h.key in (prev_key, next_key)
        out.append(h if keep else Hit(offset=h.offset))
    return out


def merge(hits: list[Hit], step: int, min_unknown: int | None = None, strict: bool = False) -> list[Entry]:
    """Collapse per-snippet hits into one entry per track, with Unknown ID rows for long gaps."""
    min_unknown = min_unknown or 2 * step
    entries: list[Entry] = []
    current: str | None = None
    gap_start: int | None = None
    for h in confirm(hits) if strict else hits:
        if h.key is None:
            if gap_start is None:
                gap_start = h.offset
            continue
        if gap_start is not None and h.offset - gap_start >= min_unknown:
            entries.append(Entry(gap_start, UNKNOWN, "", {}))
            current = None
        gap_start = None
        if h.key != current:
            entries.append(Entry(h.offset, h.title, h.artist, h.links, h.isrc))
            current = h.key
    if gap_start is not None and hits and hits[-1].offset + step - gap_start >= min_unknown:
        entries.append(Entry(gap_start, UNKNOWN, "", {}))
    return entries


def download(url: str) -> tuple[str, int, Path]:
    import yt_dlp

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(CACHE_DIR / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info))
    duration = int(info.get("duration") or 0)
    if not path.exists() or duration <= 0:
        sys.exit(f"download failed or no duration for {url}")
    return info.get("title") or path.stem, duration, path


def pcm_to_wav(pcm: bytes, rate: int) -> bytes:
    """Wrap 16-bit mono PCM in a WAV with real lengths; a piped WAV has none and makes shazamio-core shell out to ffmpeg."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


async def snippet(audio: Path, offset: int, length: int) -> bytes:
    import imageio_ffmpeg  # bundled ffmpeg, so nothing needs installing system-wide

    proc = await asyncio.create_subprocess_exec(
        imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-ss", str(offset), "-t", str(length), "-i", str(audio),
        "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "pipe:1",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed at {hms(offset)}: {err.decode().strip()}")
    return pcm_to_wav(out, SAMPLE_RATE)


@contextmanager
def quiet_stderr():
    """The Rust decoder prints format-probing noise straight to fd 2; hide it."""
    saved = os.dup(2)
    with open(os.devnull, "w") as null:
        os.dup2(null.fileno(), 2)
        try:
            yield
        finally:
            os.dup2(saved, 2)
            os.close(saved)


def to_hit(offset: int, result: dict) -> Hit:
    if not result.get("matches") or not result.get("track"):
        return Hit(offset=offset)
    t = result["track"]
    hub = t.get("hub", {})
    links = {"shazam": t.get("url")}
    for opt in hub.get("options", []):
        uri = opt.get("actions", [{}])[0].get("uri", "").split("?")[0]
        if opt.get("caption") == "OPEN IN" and uri.startswith("https://music.apple.com/") and "/album/" in uri:
            links["apple_music"] = uri
    if any(p.get("type") == "SPOTIFY" for p in hub.get("providers", [])):
        links["spotify"] = f"https://open.spotify.com/search/{quote(t['title'] + ' ' + t['subtitle'])}"
    links = {k: v for k, v in links.items() if v}
    return Hit(offset=offset, key=str(t["key"]), title=t["title"], artist=t["subtitle"], links=links, isrc=t.get("isrc"))


async def analyse(audio: Path, start: int, end: int, step: int, length: int, pace: float) -> list[Hit]:
    """Sequential on purpose: Shazam allows roughly 5 recognitions per minute per IP."""
    from aiohttp_retry import ExponentialRetry
    from shazamio import HTTPClient, Shazam
    from shazamio.exceptions import FailedDecodeJson

    shazam = Shazam(http_client=HTTPClient(retry_options=ExponentialRetry(attempts=1)))
    offsets = list(range(start, max(end - length, start + 1), step))
    hits: list[Hit] = []
    for i, offset in enumerate(offsets, 1):
        data = await snippet(audio, offset, length)
        with quiet_stderr():
            sig = await shazam.core_recognizer.recognize_bytes(value=data)
        for attempt in range(6):
            try:
                result = await asyncio.wait_for(shazam.send_recognize_request_v2(sig=sig), 30)
                hits.append(to_hit(offset, result))
                break
            except (FailedDecodeJson, asyncio.TimeoutError) as exc:  # 429 shows up as a JSON decode failure
                wait = RATE_LIMIT_WAIT * (attempt + 1)
                print(f"\n  {hms(offset)}: rate limited ({type(exc).__name__}), waiting {wait}s", file=sys.stderr)
                await asyncio.sleep(wait)
        else:
            print(f"\n  {hms(offset)}: gave up", file=sys.stderr)
            hits.append(Hit(offset=offset))
        last = hits[-1]
        label = f"{last.artist} - {last.title}" if last.key else "no match"
        print(f"\r  {i}/{len(offsets)} {hms(offset)} {label[:60]:<60}", end="", file=sys.stderr, flush=True)
        if i < len(offsets):
            await asyncio.sleep(pace)
    print(file=sys.stderr)
    return hits


def spotify_token() -> str | None:
    """App-only token from SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET; None when unset or rejected."""
    cid, secret = os.environ.get("SPOTIFY_CLIENT_ID"), os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not (cid and secret):
        return None
    auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    req = Request("https://accounts.spotify.com/api/token", data=b"grant_type=client_credentials",
                  headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urlopen(req, timeout=15) as r:
            return json.load(r)["access_token"]
    except (URLError, KeyError, ValueError) as exc:
        print(f"Spotify login failed ({exc}); keeping search links", file=sys.stderr)
        return None


def spotify_track(token: str, isrc: str) -> str | None:
    req = Request(f"https://api.spotify.com/v1/search?{urlencode({'q': f'isrc:{isrc}', 'type': 'track', 'limit': 1})}",
                  headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(req, timeout=15) as r:
            items = json.load(r)["tracks"]["items"]
    except (URLError, KeyError, ValueError) as exc:
        print(f"Spotify lookup failed for ISRC {isrc} ({exc})", file=sys.stderr)
        return None
    return items[0]["external_urls"]["spotify"] if items else None


def with_spotify_tracks(entries: list[Entry], lookup) -> list[Entry]:
    """Swap Shazam's Spotify search link for the exact track link, one lookup per ISRC."""
    found: dict[str, str | None] = {}
    out = []
    for e in entries:
        if e.isrc and e.isrc not in found:
            found[e.isrc] = lookup(e.isrc)
        url = found.get(e.isrc) if e.isrc else None
        out.append(replace(e, links={**e.links, "spotify": url}) if url else e)
    return out


def spotify_track_list(entries: list[Entry]) -> str:
    """Track links only, deduplicated: pasting them into a Spotify playlist adds the tracks."""
    urls = [e.links["spotify"] for e in entries if "/track/" in e.links.get("spotify", "")]
    return "\n".join(dict.fromkeys(urls))


def split_title(markdown: str) -> tuple[str, str]:
    """Pull the leading '# title' line off the markdown; Notion takes it as the page title instead."""
    first, _, rest = markdown.partition("\n")
    if not first.startswith("# "):
        return "", markdown
    return first[2:].strip(), rest.lstrip("\n")


def create_notion_page(markdown: str) -> str | None:
    """Create a page under NOTION_SOUNDCLOUD_PAGE_ID, or in the Private section when unset; returns its URL."""
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        print("No Notion page created: set NOTION_TOKEN (see README)", file=sys.stderr)
        return None
    title, body = split_title(markdown)
    payload: dict = {"icon": {"emoji": "💿"}, "properties": {"title": {"title": [{"text": {"content": title or "Tracklist"}}]}}, "markdown": body}
    if parent := os.environ.get("NOTION_SOUNDCLOUD_PAGE_ID"):
        payload["parent"] = {"page_id": parent}
    req = Request("https://api.notion.com/v1/pages", data=json.dumps(payload).encode(), method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Notion-Version": NOTION_VERSION})
    try:
        with urlopen(req, timeout=60) as r:
            return json.load(r).get("url")
    except HTTPError as exc:
        print(f"Notion page failed ({exc.code}): {exc.read().decode(errors='replace')[:300]}", file=sys.stderr)
    except (URLError, ValueError) as exc:
        print(f"Notion page failed ({exc})", file=sys.stderr)
    return None


def copy_to_clipboard(text: str, what: str) -> None:
    try:
        # pbcopy reads bytes in the locale encoding; without UTF-8 it mangles accents
        subprocess.run(["pbcopy"], input=text.encode(), check=True, env={**os.environ, "LANG": "en_US.UTF-8"})
        print(f"Copied {what} to the clipboard", file=sys.stderr)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Could not copy to the clipboard ({exc})", file=sys.stderr)


def render_markdown(title: str, url: str, duration: int, snippets: int, length: int, entries: list[Entry]) -> str:
    lines = [
        f"# {title}", "", f"[Open in soundcloud →]({url})", "", f"* Set duration: {hms(duration)}", "",
        f"* Snippet count: {snippets}", f"* Snippet length: {length}s", "", "",
        "| Time | Track | Spotify | Shazam |", "| --- | --- | --- | --- |",
    ]
    for e in entries:
        name = (f"{e.artist} - {e.title}" if e.artist else e.title).replace("|", "\\|")
        spotify = f"[Spotify]({e.links['spotify']})" if "spotify" in e.links else ""
        shazam = f"[Shazam]({e.links['shazam']})" if "shazam" in e.links else ""
        lines.append(f"| {hms(e.start)} | {name} | {spotify} | {shazam} |")
    return "\n".join(lines) + "\n"


HELP_EPILOG = """\
Examples:
  setid https://soundcloud.com/artist/some-set --step 90
      a whole set; every track of 3+ minutes gets two snippets
  setid https://soundcloud.com/artist/some-set --start 1:50:00 --end 2:05:00 --step 30
      find one track: only the minutes around it, snippets close together
  setid https://soundcloud.com/artist/some-set --step 90 --copy-spotify
      copy Spotify track links; paste them into a playlist in the Spotify app
  setid https://soundcloud.com/artist/some-set --step 90 --notion
      also create a Notion page with the tracklist

Settings (optional, add to ~/.zshrc as export NAME=value):
  SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
      exact Spotify track links instead of search links; needed for --copy-spotify
  NOTION_TOKEN
      Notion personal access token; needed for --notion
  NOTION_SOUNDCLOUD_PAGE_ID
      Notion page to create tracklists under (default: your Private section)

Tracklists are saved to ~/Music/setid.
"""


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="setid", description=__doc__.splitlines()[0], epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("url", help="SoundCloud set URL")
    ap.add_argument("--start", type=parse_time, default=0, help="analyse from this time, h:mm:ss (default: the beginning)")
    ap.add_argument("--end", type=parse_time, default=None, help="analyse up to this time, h:mm:ss (default: the end)")
    ap.add_argument("--budget", type=float, default=20, help="target run time in minutes; sets the step (default 20)")
    ap.add_argument("--step", type=int, default=None, help="seconds between snippets; overrides --budget")
    ap.add_argument("--snippet", type=int, default=12, help="snippet length in seconds (default 12)")
    ap.add_argument("--pace", type=float, default=15, help="seconds to wait between Shazam requests (default 15, about 3/min; Shazam blocks at about 5/min)")
    ap.add_argument("--min-unknown", type=int, default=None, help="gap in seconds that becomes an Unknown ID row (default 2 x step)")
    copy = ap.add_mutually_exclusive_group()
    copy.add_argument("--copy", action="store_true", help="also copy the markdown tracklist to the clipboard")
    copy.add_argument("--copy-spotify", action="store_true", help="copy the Spotify track links, one per line, to paste into a playlist")
    ap.add_argument("--notion", action="store_true", help="also create a Notion page with the tracklist (needs NOTION_TOKEN)")
    ap.add_argument("--strict", action="store_true", help="only keep a track when two neighbouring snippets agree; needs at least two snippets per track")
    return ap


def main() -> None:
    args = build_parser().parse_args()

    print("Downloading...", file=sys.stderr)
    title, duration, audio = download(args.url)
    end = min(args.end or duration, duration)
    if args.start >= end:
        sys.exit(f"--start {hms(args.start)} must be before --end {hms(end)} (the set is {hms(duration)} long)")
    step = args.step or auto_step(end - args.start, args.pace, args.budget)
    n = max(end - args.start - args.snippet, 1) // step + 1
    print(f"{title} ({hms(duration)}): {n} snippets every {step}s, about {hms(int(n * (args.pace + REQUEST_OVERHEAD)))} at Shazam's rate limit", file=sys.stderr)
    hits = asyncio.run(analyse(audio, args.start, end, step, args.snippet, args.pace))
    entries = merge(hits, step, args.min_unknown, args.strict)
    token = spotify_token()
    if token:
        print("Looking up Spotify track links...", file=sys.stderr)
        entries = with_spotify_tracks(entries, lambda isrc: spotify_track(token, isrc))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^\w-]+", "-", title).strip("-")[:80] or "set"
    if args.start or end < duration:  # keep partial runs from overwriting the full-set tracklist
        slug += f"_{hms(args.start)}-{hms(end)}".replace(":", "")
    (OUT_DIR / f"{slug}.json").write_text(json.dumps([asdict(e) for e in entries], indent=2, ensure_ascii=False))
    markdown = render_markdown(title, args.url, duration, len(hits), args.snippet, entries)
    (OUT_DIR / f"{slug}.md").write_text(markdown)
    print(markdown)
    print(f"Saved to {OUT_DIR / slug}.md and .json", file=sys.stderr)
    if args.copy:
        copy_to_clipboard(markdown, "the markdown tracklist")
    elif args.copy_spotify:
        tracks = spotify_track_list(entries)
        if tracks:
            copy_to_clipboard(tracks + "\n", f"{tracks.count(chr(10)) + 1} Spotify track links")
        else:
            print("No Spotify track links to copy: set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET (see README)", file=sys.stderr)
    if args.notion and (page := create_notion_page(markdown)):
        print(f"Created Notion page: {page}", file=sys.stderr)


if __name__ == "__main__":
    main()
