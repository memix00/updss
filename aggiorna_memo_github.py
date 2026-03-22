from pathlib import Path
import argparse
import re
import shutil
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from playwright.sync_api import sync_playwright

PLAYLIST_FILE = Path(r"C:\Users\Memix\Documents\TV\IPTV\memo.m3u8")
BACKUP_FILE = Path(r"C:\Users\Memix\Documents\TV\IPTV\memo_backup.m3u8")
DEBUG_FILE = Path(r"C:\Users\Memix\Documents\TV\IPTV\debug_streams.txt")

BRAVE_EXE = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
BRAVE_PROFILE_PATH = r"C:\Users\Memix\AppData\Local\BraveSoftware\Brave-Browser\User Data\Profile 1"

# ==============================
# GITHUB CONFIG
# ==============================
GIT_MODE = "push"  # "none" | "push"
GIT_REPO_DIR = Path(r"C:\Users\Memix\Documents\TV\IPTV")
GIT_BRANCH = "main"
GIT_REMOTE = "origin"
GIT_COMMIT_PREFIX = "auto-update playlist"
VERSION_FILE = GIT_REPO_DIR / "playlist_version.txt"

LIVE_CHANNELS = {
    "La Sexta": {
        "page": "https://www.atresplayer.com/directos/lasexta",
        "tokens": ["atres-live", "lasexta_usp", ".m3u8", ".isml", "chunklist", "manifest"],
        "aliases": ["La Sexta", "laSexta"],
        "wait_ms": 3000,
    },
    "Antena 3": {
        "page": "https://www.atresplayer.com/directos/antena3",
        "tokens": ["atres-live", "antena3_usp", ".m3u8", ".isml", "chunklist", "manifest"],
        "aliases": ["Antena 3", "A3", "Antena3"],
        "wait_ms": 3000,
    },
    "Neox": {
        "page": "https://www.atresplayer.com/directos/neox",
        "tokens": ["atres-live", "neox_usp", ".m3u8", ".isml", "chunklist", "manifest"],
        "aliases": ["Neox"],
        "wait_ms": 3000,
    },
    "Mega": {
        "page": "https://www.atresplayer.com/directos/mega",
        "tokens": ["atres-live", "mega_usp", ".m3u8", ".isml", "chunklist", "manifest"],
        "aliases": ["Mega"],
        "wait_ms": 3000,
    },
    "DMAX": {
        "page": "https://dmax.marca.com/en-directo",
        "tokens": [".m3u8", ".mpd", "playlist", "manifest", "dmax", "disco"],
        "aliases": ["DMAX", "DMax"],
        "wait_ms": 8000,
        "frame_autoplay": True,
    },
    "Sardegna 1": {
        "page": "https://www.sardegna1.it/live/diretta-live/",
        "tokens": ["dmcdn.net", ".m3u8", "live-", "sardegna1"],
        "aliases": ["Sardegna 1", "Sardegna1"],
        "wait_ms": 12000,
        "frame_autoplay": True,
    },
}

VIDEOLINA = {
    "page": "https://www.videolina.it/live",
    "aliases": ["Videolina"],
    "wait_ms": 3000,
}


def replace_channel(content: str, aliases: list[str], url: str) -> str:
    lines = content.splitlines()
    for name in aliases:
        for i, line in enumerate(lines[:-1]):
            if not line.startswith("#EXTINF:-1"):
                continue
            if name.lower() not in line.lower():
                continue
            if name.lower() in ("dmax", "dmax es", "dmax españa", "dmax espana"):
                up = line.upper()
                if "DMAX IT" in up or "DMAX ITA" in up or "DMAX ITALIA" in up:
                    continue
            lines[i + 1] = url
            print("Aggiornato:", name)
            return "\n".join(lines)
    print("Canale non trovato nella playlist:", aliases)
    return content


def score_url(url: str, tokens: list[str]) -> int:
    u = url.lower()
    score = 0
    for t in tokens:
        if t.lower() in u:
            score += 1
    if ".m3u8" in u:
        score += 5
    if ".mpd" in u:
        score += 2
    if "master" in u:
        score += 2
    if "playlist" in u:
        score += 2
    if "chunklist" in u:
        score += 1
    if "manifest.mpd" in u:
        score += 2
    if "manifest.webmanifest" in u:
        score -= 20
    if ".json" in u or ".js" in u or ".css" in u:
        score -= 20
    if "my-ip" in u:
        score -= 5
    return score


def is_stream_candidate(url: str) -> bool:
    u = url.lower()
    if "my-ip" in u or "manifest.webmanifest" in u:
        return False
    if u.endswith(".js") or u.endswith(".css") or u.endswith(".json"):
        return False
    return any(x in u for x in [".m3u8", ".mpd", ".isml", "chunklist", "manifest"])


def validate_stream_url(url: str) -> bool:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Range": "bytes=0-1023",
        },
    )
    try:
        with urlopen(req, timeout=12) as resp:
            code = getattr(resp, "status", 200)
            return code in (200, 206)
    except HTTPError as e:
        return e.code in (200, 206, 302, 403, 405)
    except (URLError, TimeoutError, ValueError):
        return False


def launch_browser_context(p):
    import os

    if os.environ.get("GITHUB_ACTIONS") == "true":
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--autoplay-policy=no-user-gesture-required",
            ],
        )
        return browser.new_context()

    return p.chromium.launch_persistent_context(
        user_data_dir=BRAVE_PROFILE_PATH,
        executable_path=BRAVE_EXE,
        headless=False,
        slow_mo=300,
        args=[
            "--autoplay-policy=no-user-gesture-required",
            "--window-position=50,50",
            "--window-size=1366,768",
        ],
        no_viewport=True,
    )


def try_autoplay(page) -> bool:
    selectors = [
        'button[aria-label*="play" i]',
        'button[title*="play" i]',
        '[data-testid*="play" i]',
        'button:has-text("Ver ahora")',
        'button:has-text("Directo")',
        'button:has-text("Play")',
        'button:has-text("Reproducir")',
        '.vjs-big-play-button',
        '.jw-display-icon-container',
        '.jw-icon-display',
        '.atresplayer-Player-buttonPlay',
        '.player-button-play',
        '.play-button',
    ]

    for sel in selectors:
        try:
            locator = page.locator(sel).first
            if locator.is_visible(timeout=1500):
                locator.click(timeout=2000, force=True)
                print(f"Autoplay: click su {sel}")
                return True
        except Exception:
            pass

    try:
        page.mouse.click(640, 360)
        print("Autoplay: click al centro del player")
        return True
    except Exception:
        pass

    return False


def accept_popups(page) -> None:
    selectors = [
        '#didomi-notice-agree-button',
        'button:has-text("Aceptar todo")',
        'button:has-text("Aceptar")',
        'button:has-text("Accept")',
        'button:has-text("Agree")',
        'button:has-text("Accetta")',
    ]
    for sel in selectors:
        try:
            locator = page.locator(sel).first
            if locator.is_visible(timeout=1500):
                locator.click(timeout=2000, force=True)
                print(f"Popup chiuso: {sel}")
                page.wait_for_timeout(1000)
                break
        except Exception:
            pass


def autoplay_frames(page) -> None:
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            frame.locator("button, .vjs-big-play-button, .jw-display-icon-container, .jw-icon-display").first.click(timeout=1200, force=True)
            print(f"Autoplay iframe: {frame.url}")
        except Exception:
            pass
        try:
            frame.evaluate("""
                () => {
                    const v = document.querySelector('video');
                    if (v) {
                        v.muted = true;
                        v.play().catch(() => {});
                    }
                }
            """)
        except Exception:
            pass


def extract_live_stream(channel_name: str, page_url: str, tokens: list[str], wait_ms: int, frame_autoplay: bool = False) -> str:
    found_urls = []

    with sync_playwright() as p:
        context = launch_browser_context(p)
        page = context.new_page()

        def add_url(url: str):
            if url and url not in found_urls:
                found_urls.append(url)

        def on_request(request):
            if is_stream_candidate(request.url):
                add_url(request.url)

        def on_response(response):
            if is_stream_candidate(response.url):
                add_url(response.url)

        page.on("request", on_request)
        page.on("response", on_response)

        print(f"\nApro pagina: {page_url}")
        page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)

        accept_popups(page)

        autoplay_ok = try_autoplay(page)
        if not autoplay_ok:
            print(f">>> AUTOPLAY NON TROVATO: CLICCA TU SUL PLAYER ({channel_name}) <<<")
        else:
            print(f"Autoplay tentato su {channel_name}")

        if frame_autoplay:
            autoplay_frames(page)

        print(f"attendo {wait_ms // 1000} secondi...")
        page.wait_for_timeout(wait_ms)

        if frame_autoplay and not found_urls:
            for _ in range(3):
                try_autoplay(page)
                autoplay_frames(page)
                page.wait_for_timeout(2500)
                if found_urls:
                    break

        context.close()

    with DEBUG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"\n===== {channel_name} =====\n")
        for u in found_urls:
            f.write(u + "\n")

    preferred = [u for u in found_urls if is_stream_candidate(u)]

    if not preferred:
        return ""

    ranked = sorted(preferred, key=lambda x: score_url(x, tokens), reverse=True)
    fallback = ranked[0]

    for candidate in ranked[:8]:
        if validate_stream_url(candidate):
            print("Stream validato:", candidate)
            return candidate

    print("Validazione HTTP non conclusiva, uso miglior candidato trovato")
    return fallback


def extract_dmax_stream() -> str:
    found_urls = []
    checked_urls = set()

    with sync_playwright() as p:
        context = launch_browser_context(p)
        page = context.new_page()

        def add_url(url: str):
            if url and url not in found_urls:
                found_urls.append(url)

        def is_dmax_candidate(url: str) -> bool:
            u = url.lower()
            if "manifest.webmanifest" in u or "my-ip" in u:
                return False
            if u.endswith(".js") or u.endswith(".css") or u.endswith(".json"):
                return False
            if ".m3u8" in u or ".mpd" in u:
                return True
            return any(x in u for x in ["playlist", "manifest.mpd", "vod-akc", "linear", "dmax", "disco"])

        def ranked_candidates():
            preferred = [u for u in found_urls if is_dmax_candidate(u)]
            return sorted(preferred, key=lambda x: score_url(x, LIVE_CHANNELS["DMAX"]["tokens"]), reverse=True)

        def try_fast_pick():
            ranked = ranked_candidates()
            for candidate in ranked[:4]:
                if candidate in checked_urls:
                    continue
                checked_urls.add(candidate)
                if validate_stream_url(candidate):
                    print("DMAX validato rapido:", candidate)
                    return candidate
            return ""

        def on_request(request):
            if is_dmax_candidate(request.url):
                add_url(request.url)

        def on_response(response):
            if is_dmax_candidate(response.url):
                add_url(response.url)

        page.on("request", on_request)
        page.on("response", on_response)

        print("\nApro pagina: DMAX")
        page.goto("https://dmax.marca.com/en-directo", wait_until="domcontentloaded", timeout=60000)

        page.wait_for_timeout(2000)
        accept_popups(page)
        try_autoplay(page)
        autoplay_frames(page)

        early = try_fast_pick()
        if early:
            context.close()
            with DEBUG_FILE.open("a", encoding="utf-8") as f:
                f.write("\n===== DMAX =====\n")
                for u in found_urls:
                    f.write(u + "\n")
            return early

        for _ in range(6):
            page.wait_for_timeout(700)
            early = try_fast_pick()
            if early:
                context.close()
                with DEBUG_FILE.open("a", encoding="utf-8") as f:
                    f.write("\n===== DMAX =====\n")
                    for u in found_urls:
                        f.write(u + "\n")
                return early

        for _ in range(4):
            try_autoplay(page)
            autoplay_frames(page)
            page.wait_for_timeout(1200)
            early = try_fast_pick()
            if early:
                context.close()
                with DEBUG_FILE.open("a", encoding="utf-8") as f:
                    f.write("\n===== DMAX =====\n")
                    for u in found_urls:
                        f.write(u + "\n")
                return early

        context.close()

    with DEBUG_FILE.open("a", encoding="utf-8") as f:
        f.write("\n===== DMAX =====\n")
        for u in found_urls:
            f.write(u + "\n")

    preferred = [u for u in found_urls if is_dmax_candidate(u)]
    if not preferred:
        return ""

    ranked = sorted(preferred, key=lambda x: score_url(x, LIVE_CHANNELS["DMAX"]["tokens"]), reverse=True)
    for candidate in ranked[:12]:
        if candidate in checked_urls:
            continue
        if validate_stream_url(candidate):
            print("DMAX validato:", candidate)
            return candidate

    for candidate in ranked:
        cl = candidate.lower()
        if ".m3u8" in cl or ".mpd" in cl:
            print("DMAX fallback:", candidate)
            return candidate

    return ranked[0]


def extract_sardegna1_stream() -> str:
    found_urls = []

    with sync_playwright() as p:
        context = launch_browser_context(p)
        page = context.new_page()

        def add_url(url: str):
            if url and url not in found_urls:
                found_urls.append(url)

        def is_sardegna_candidate(url: str) -> bool:
            u = url.lower()
            return ".m3u8" in u and "dmcdn.net" in u

        def on_request(request):
            if is_sardegna_candidate(request.url):
                add_url(request.url)

        def on_response(response):
            if is_sardegna_candidate(response.url):
                add_url(response.url)

        page.on("request", on_request)
        page.on("response", on_response)

        print("\nApro pagina: Sardegna 1")
        page.goto("https://www.sardegna1.it/live/diretta-live/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)

        accept_popups(page)

        autoplay_ok = try_autoplay(page)
        if autoplay_ok:
            print("Autoplay tentato su Sardegna 1")
        else:
            print(">>> AUTOPLAY NON TROVATO: CLICCA TU SUL PLAYER (Sardegna 1) <<<")

        autoplay_frames(page)

        for _ in range(24):
            preferred = [
                u for u in found_urls
                if "dmcdn.net" in u.lower()
                and ".m3u8" in u.lower()
                and "live-" in u.lower()
            ]
            if preferred:
                context.close()

                for u in preferred:
                    if "live-720.m3u8" in u.lower() and validate_stream_url(u):
                        return u
                for u in preferred:
                    if validate_stream_url(u):
                        return u

                print("Sardegna 1: trovati URL ma nessuno validato, lascio il link attuale")
                return ""

            page.wait_for_timeout(500)

        context.close()

    with DEBUG_FILE.open("a", encoding="utf-8") as f:
        f.write("\n===== Sardegna 1 =====\n")
        for u in found_urls:
            f.write(u + "\n")

    preferred = [
        u for u in found_urls
        if "dmcdn.net" in u.lower()
        and ".m3u8" in u.lower()
        and "live-" in u.lower()
    ]
    if preferred:
        for u in preferred:
            if "live-720.m3u8" in u.lower() and validate_stream_url(u):
                return u
        for u in preferred:
            if validate_stream_url(u):
                return u

        print("Sardegna 1: nessun link validato nel fallback, lascio il link attuale")
        return ""

    return ""


def extract_videolina_stream() -> str:
    found_urls = []

    with sync_playwright() as p:
        context = launch_browser_context(p)
        page = context.new_page()

        def add_url(url: str):
            if url and url not in found_urls:
                found_urls.append(url)

        def on_request(request):
            url = request.url.lower()
            if ".m3u8" in url or "dmcdn.net" in url:
                add_url(request.url)

        def on_response(response):
            url = response.url.lower()
            if ".m3u8" in url or "dmcdn.net" in url:
                add_url(response.url)

        page.on("request", on_request)
        page.on("response", on_response)

        print("\nApro pagina: Videolina")
        page.goto(VIDEOLINA["page"], wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)

        try_autoplay(page)
        page.wait_for_timeout(3000)

        context.close()

    with DEBUG_FILE.open("a", encoding="utf-8") as f:
        f.write("\n===== Videolina =====\n")
        for u in found_urls:
            f.write(u + "\n")

    preferred = [
        u for u in found_urls
        if "dmcdn.net" in u.lower()
        and ".m3u8" in u.lower()
        and "live-" in u.lower()
    ]
    if preferred:
        for u in preferred:
            if "live-720.m3u8" in u.lower() and validate_stream_url(u):
                return u
        for u in preferred:
            if validate_stream_url(u):
                return u
        return preferred[0]

    return ""


def update_version_file() -> str:
    from datetime import datetime

    version = datetime.now().strftime("%Y%m%d-%H%M%S")
    VERSION_FILE.write_text(version + "\n", encoding="utf-8")
    print(f"Versione playlist aggiornata: {version}")
    return version


def run_git_command(args: list[str]) -> None:
    import subprocess

    result = subprocess.run(
        args,
        cwd=str(GIT_REPO_DIR),
        text=True,
        capture_output=True,
        shell=False,
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Comando git fallito")


def publish_playlist_to_github(mode: str, version: str) -> None:
    if mode == "none":
        print("Push GitHub disattivato")
        return
    if mode != "push":
        raise ValueError(f"Modalita GitHub non valida: {mode}")

    run_git_command(["git", "add", str(PLAYLIST_FILE.name), str(BACKUP_FILE.name), str(DEBUG_FILE.name), str(VERSION_FILE.name)])

    import subprocess
    status = subprocess.run(["git", "status", "--porcelain"], cwd=str(GIT_REPO_DIR), text=True, capture_output=True, shell=False)
    if status.returncode != 0:
        raise RuntimeError(status.stderr.strip() or "Impossibile leggere git status")

    if not status.stdout.strip():
        print("Nessuna modifica da pubblicare su GitHub")
        return

    commit_message = f"{GIT_COMMIT_PREFIX} {version}"
    run_git_command(["git", "commit", "-m", commit_message])
    run_git_command(["git", "push", GIT_REMOTE, GIT_BRANCH])
    print("Playlist pubblicata su GitHub")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggiorna la playlist TV e opzionalmente la pubblica su GitHub")
    parser.add_argument(
        "--github",
        choices=["none", "push"],
        default=GIT_MODE,
        help="Modalita pubblicazione GitHub",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    DEBUG_FILE.write_text("", encoding="utf-8")

    if not PLAYLIST_FILE.exists():
        print("Playlist non trovata")
        return

    shutil.copy2(PLAYLIST_FILE, BACKUP_FILE)
    content = PLAYLIST_FILE.read_text(encoding="utf-8", errors="ignore")

    for channel_name, cfg in LIVE_CHANNELS.items():
        if channel_name in ("Sardegna 1", "DMAX"):
            continue
        print("\n======", channel_name, "======")
        stream = extract_live_stream(
            channel_name,
            cfg["page"],
            cfg["tokens"],
            cfg["wait_ms"],
            cfg.get("frame_autoplay", False),
        )
        if stream:
            print("Trovato stream:")
            print(stream)
            content = replace_channel(content, cfg["aliases"], stream)
        else:
            print("stream non trovato")

    print("\n====== DMAX ======")
    dstream = extract_dmax_stream()
    if dstream:
        print("Trovato stream:")
        print(dstream)
        content = replace_channel(content, LIVE_CHANNELS["DMAX"]["aliases"], dstream)
    else:
        print("stream non trovato")

    print("\n====== Sardegna 1 ======")
    sstream = extract_sardegna1_stream()
    if sstream:
        print("Trovato stream:")
        print(sstream)
        content = replace_channel(content, ["Sardegna 1", "Sardegna1"], sstream)
    else:
        print("Sardegna 1 non aggiornato: tengo il link attuale")

    print("\n====== Videolina ======")
    vstream = extract_videolina_stream()
    if vstream:
        print("Trovato stream:")
        print(vstream)
        content = replace_channel(content, VIDEOLINA["aliases"], vstream)
    else:
        print("stream non trovato")

    PLAYLIST_FILE.write_text(content, encoding="utf-8")
    print("\nPlaylist aggiornata")

    try:
        version = update_version_file()
        publish_playlist_to_github(args.github, version)
    except Exception as e:
        print(f"GitHub: errore durante la pubblicazione -> {e}")


if __name__ == "__main__":
    main()
