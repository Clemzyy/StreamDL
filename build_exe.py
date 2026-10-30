"""Build the portable single-file StreamDL executable with PyInstaller.

Usage: py -3.13 build_exe.py

The newest verified yt-dlp.exe is fetched first so that a freshly built
executable starts with the current release; the application itself then keeps
yt-dlp up to date on each launch. ffmpeg.exe and deno.exe must be present
beside this script. The result is written to dist\\StreamDL.exe.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import PyInstaller.__main__

from ytdlp_updater import (
    describe_error,
    fetch_latest_release,
    install_release,
    is_newer_release,
    read_exe_version,
    YtDlpCopy,
)


PROJECT_DIR = Path(__file__).resolve().parent
EXE_NAME = "StreamDL"
# Outside OneDrive: it marks synced folders read-only, which makes the
# PyInstaller --clean step fail, and the 100+ MB intermediates need no sync.
WORK_DIR = Path(tempfile.gettempdir()) / "StreamDL-build"
BUNDLED_FILES = (
    "yt-dlp.exe",
    "ffmpeg.exe",
    "deno.exe",
    "download.ico",
    "download.png",
    "LICENSE",
    "DENO_LICENSE.md",
)


def find_latest_source() -> Path:
    def source_version(path):
        match = re.search(r"_v(\d+)\.(\d+)", path)
        return (int(match.group(1)), int(match.group(2))) if match else (0, 0)

    sources = glob.glob(str(PROJECT_DIR / "telechargeur_youtube_v*.pyw"))
    if not sources:
        sys.exit("Aucun fichier telechargeur_youtube_v*.pyw trouvé.")
    return Path(max(sources, key=source_version))


def refresh_bundled_ytdlp() -> None:
    bundled_path = PROJECT_DIR / "yt-dlp.exe"
    current = YtDlpCopy(str(bundled_path), read_exe_version(str(bundled_path)))

    try:
        release = fetch_latest_release()
    except Exception as exc:
        print(f"Vérification de yt-dlp impossible ({describe_error(exc)}), version locale conservée.")
        return

    if not is_newer_release(release, current):
        print(f"yt-dlp {current.version} est déjà la dernière version.")
        return

    print(f"Mise à jour de yt-dlp {current.version} -> {release.version}...")
    with tempfile.TemporaryDirectory() as temporary_dir:
        updated = install_release(release, Path(temporary_dir))
        shutil.copy2(updated.path, bundled_path)
    print(f"yt-dlp {release.version} vérifié (SHA-256) et copié dans le projet.")


def main() -> None:
    refresh_bundled_ytdlp()

    missing = [name for name in BUNDLED_FILES if not (PROJECT_DIR / name).is_file()]
    if missing:
        sys.exit("Fichiers manquants pour le build : " + ", ".join(missing))

    source = find_latest_source()
    data_files = [PROJECT_DIR / name for name in BUNDLED_FILES]
    data_files += sorted(PROJECT_DIR.glob("social_*.png"))

    # Absolute paths: PyInstaller resolves relative --add-data paths from --specpath.
    arguments = [
        str(source),
        "--name", EXE_NAME,
        "--onefile",
        "--windowed",
        "--noupx",
        "--clean",
        "--noconfirm",
        "--icon", str(PROJECT_DIR / "download.ico"),
        "--distpath", str(PROJECT_DIR / "dist"),
        "--workpath", str(WORK_DIR),
        "--specpath", str(WORK_DIR),
    ]
    for data_file in data_files:
        arguments += ["--add-data", f"{data_file}{os.pathsep}."]

    print(f"Compilation de {source.name}...")
    PyInstaller.__main__.run(arguments)
    print(f"Exécutable créé : {PROJECT_DIR / 'dist' / (EXE_NAME + '.exe')}")


if __name__ == "__main__":
    main()
