
from pathlib import Path
import argparse
import re
import shutil
import os
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from playwright.sync_api import sync_playwright

# ==============================
# PATH CONFIG (LOCAL vs GITHUB)
# ==============================
BASE_DIR = Path(__file__).resolve().parent

if os.environ.get("GITHUB_ACTIONS") == "true":
    PLAYLIST_FILE = BASE_DIR / "memo.m3u8"
    BACKUP_FILE = BASE_DIR / "memo_backup.m3u8"
    DEBUG_FILE = BASE_DIR / "debug_streams.txt"
    GIT_REPO_DIR = BASE_DIR
    HEADLESS_MODE = True
else:
    import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

if os.environ.get("GITHUB_ACTIONS") == "true":
    PLAYLIST_FILE = BASE_DIR / "memo.m3u8"
    BACKUP_FILE = BASE_DIR / "memo_backup.m3u8"
    DEBUG_FILE = BASE_DIR / "debug_streams.txt"
    GIT_REPO_DIR = BASE_DIR
else:
    PLAYLIST_FILE = Path(r"C:\Users\Memix\Documents\TV\IPTV\memo.m3u8")
    BACKUP_FILE = Path(r"C:\Users\Memix\Documents\TV\IPTV\memo_backup.m3u8")
    DEBUG_FILE = Path(r"C:\Users\Memix\Documents\TV\IPTV\debug_streams.txt")
    GIT_REPO_DIR = Path(r"C:\Users\Memix\Documents\TV\IPTV")
    BACKUP_FILE = Path(r"C:\Users\Memix\Documents\TV\IPTV\memo_backup.m3u8")
    DEBUG_FILE = Path(r"C:\Users\Memix\Documents\TV\IPTV\debug_streams.txt")
    GIT_REPO_DIR = Path(r"C:\Users\Memix\Documents\TV\IPTV")
    HEADLESS_MODE = False

BRAVE_EXE = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
BRAVE_PROFILE_PATH = r"C:\Users\Memix\AppData\Local\BraveSoftware\Brave-Browser\User Data\Profile 1"

# ==============================
# GITHUB CONFIG
# ==============================
GIT_MODE = "push"
GIT_BRANCH = "main"
GIT_REMOTE = "origin"
GIT_COMMIT_PREFIX = "auto-update playlist"
VERSION_FILE = GIT_REPO_DIR / "playlist_version.txt"

# ==============================
# BROWSER LAUNCH (FIXED)
# ==============================
def launch_browser_context(p):
    if HEADLESS_MODE:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        return browser.new_context()
    else:
        return p.chromium.launch_persistent_context(
            user_data_dir=BRAVE_PROFILE_PATH,
            executable_path=BRAVE_EXE,
            headless=False,
            slow_mo=300,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--window-size=1366,768",
            ],
            no_viewport=True,
        )

# ==============================
# BASIC UTILS (unchanged core)
# ==============================

def validate_stream_url(url: str) -> bool:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=10) as resp:
            return True
    except Exception:
        return False


def extract_simple_stream(page_url: str):
    with sync_playwright() as p:
        context = launch_browser_context(p)
        page = context.new_page()

        found = []

        def on_response(resp):
            url = resp.url.lower()
            if ".m3u8" in url:
                found.append(resp.url)

        page.on("response", on_response)

        print(f"Apro pagina: {page_url}")
        page.goto(page_url, timeout=60000)
        page.wait_for_timeout(5000)

        context.close()

    if not found:
        return ""

    for u in found:
        if validate_stream_url(u):
            return u

    return found[0]


def update_version_file():
    from datetime import datetime
    version = datetime.now().strftime("%Y%m%d-%H%M%S")
    VERSION_FILE.write_text(version)
    return version


def run_git_command(args):
    import subprocess
    subprocess.run(args, cwd=str(GIT_REPO_DIR))


def publish_playlist_to_github(version):
    run_git_command(["git", "add", "."])
    run_git_command(["git", "commit", "-m", f"{GIT_COMMIT_PREFIX} {version}"])
    run_git_command(["git", "push"])


def main():
    if not PLAYLIST_FILE.exists():
        print("Playlist non trovata")
        return

    shutil.copy2(PLAYLIST_FILE, BACKUP_FILE)
    content = PLAYLIST_FILE.read_text()

    # Example channel (test)
    stream = extract_simple_stream("https://www.atresplayer.com/directos/antena3")

    if stream:
        print("Stream trovato:", stream)
        content = content.replace("ANTENA3_PLACEHOLDER", stream)

    PLAYLIST_FILE.write_text(content)

    version = update_version_file()
    publish_playlist_to_github(version)

    print("Playlist aggiornata!")


if __name__ == "__main__":
    main()
