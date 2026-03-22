
from pathlib import Path
import argparse
import shutil
import os
from urllib.request import Request, urlopen
from playwright.sync_api import sync_playwright

# ==============================
# PATH CONFIG (ROBUSTO)
# ==============================
BASE_DIR = Path(__file__).resolve().parent
CWD = Path.cwd()

print("BASE_DIR =", BASE_DIR)
print("CWD =", CWD)
print("FILES BASE_DIR =", [p.name for p in BASE_DIR.iterdir()])

if os.environ.get("GITHUB_ACTIONS") == "true":
    # prova principale
    PLAYLIST_FILE = BASE_DIR / "memo.m3u8"

    # fallback se non trovato
    if not PLAYLIST_FILE.exists():
        PLAYLIST_FILE = CWD / "memo.m3u8"

    BACKUP_FILE = PLAYLIST_FILE.parent / "memo_backup.m3u8"
    DEBUG_FILE = PLAYLIST_FILE.parent / "debug_streams.txt"
    GIT_REPO_DIR = PLAYLIST_FILE.parent
    HEADLESS_MODE = True
else:
    PLAYLIST_FILE = Path(r"C:\Users\Memix\Documents\TV\IPTV\memo.m3u8")
    BACKUP_FILE = Path(r"C:\Users\Memix\Documents\TV\IPTV\memo_backup.m3u8")
    DEBUG_FILE = Path(r"C:\Users\Memix\Documents\TV\IPTV\debug_streams.txt")
    GIT_REPO_DIR = Path(r"C:\Users\Memix\Documents\TV\IPTV")
    HEADLESS_MODE = False

print("PLAYLIST_FILE =", PLAYLIST_FILE)
print("EXISTS =", PLAYLIST_FILE.exists())

# ==============================
# BROWSER
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
            user_data_dir=r"C:\Users\Memix\AppData\Local\BraveSoftware\Brave-Browser\User Data\Profile 1",
            executable_path=r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            headless=False,
            slow_mo=300,
            args=["--autoplay-policy=no-user-gesture-required"],
            no_viewport=True,
        )

# ==============================
# STREAM
# ==============================
def validate_stream_url(url: str) -> bool:
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10):
            return True
    except:
        return False


def extract_stream(url):
    with sync_playwright() as p:
        context = launch_browser_context(p)
        page = context.new_page()

        found = []

        def on_response(r):
            if ".m3u8" in r.url.lower():
                found.append(r.url)

        page.on("response", on_response)

        print("Apro pagina:", url)
        page.goto(url, timeout=60000)
        page.wait_for_timeout(5000)

        context.close()

    if not found:
        return ""

    for f in found:
        if validate_stream_url(f):
            return f

    return found[0]

# ==============================
# GIT
# ==============================
def run_git(cmd):
    import subprocess
    subprocess.run(cmd, cwd=str(GIT_REPO_DIR))


def publish():
    run_git(["git", "add", "."])
    run_git(["git", "commit", "-m", "auto update"])
    run_git(["git", "push"])

# ==============================
# MAIN
# ==============================
def main():
    if not PLAYLIST_FILE.exists():
        print("Playlist non trovata")
        return

    shutil.copy2(PLAYLIST_FILE, BACKUP_FILE)
    content = PLAYLIST_FILE.read_text()

    stream = extract_stream("https://www.atresplayer.com/directos/antena3")

    if stream:
        print("STREAM:", stream)
        content = content.replace("ANTENA3_PLACEHOLDER", stream)

    PLAYLIST_FILE.write_text(content)

    publish()

    print("DONE")

if __name__ == "__main__":
    main()
