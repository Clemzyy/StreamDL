"""Build the portable single-file StreamDL executable.

Usage:
    py -3.13 build_exe.py                light build: yt-dlp, Deno and ffmpeg are
                                         downloaded and verified at first launch
    py -3.13 build_exe.py --full         also embeds them, for 100% offline use
    py -3.13 build_exe.py --pyinstaller  PyInstaller instead of Nuitka

Nuitka in onefile "cached" mode is the default: the program is unpacked once
into %LOCALAPPDATA%\\StreamDL\\app\\<build id> and reused afterwards, so the
window opens in about 0.5 s instead of 2.5 s with PyInstaller, which unpacks
everything at every launch. Requirements: pip install "nuitka[onefile]" and the
Visual Studio Build Tools (MSVC). The result is written to dist\\StreamDL.exe.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import importlib.metadata
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tools_manager import (
    YTDLP_SINGLE_FILE,
    ToolCopy,
    describe_error,
    fetch_latest_release,
    install_release,
    is_newer_release,
    run_version_command,
)


PROJECT_DIR = Path(__file__).resolve().parent
EXE_NAME = "StreamDL"
# Outside OneDrive: it marks synced folders read-only, which breaks the build
# cleanup steps, and the 100+ MB intermediates need no sync.
WORK_DIR = Path(tempfile.gettempdir()) / "StreamDL-build"
APP_FILES = ("download.ico", "LICENSE")
TOOL_FILES = ("yt-dlp.exe", "ffmpeg.exe", "deno.exe", "DENO_LICENSE.md")
SOURCE_MODULES = ("auth_support.py", "tools_manager.py")


def find_latest_source() -> Path:
    def source_version(path):
        match = re.search(r"_v(\d+)\.(\d+)", path)
        return (int(match.group(1)), int(match.group(2))) if match else (0, 0)

    sources = glob.glob(str(PROJECT_DIR / "telechargeur_youtube_v*.pyw"))
    if not sources:
        sys.exit("Aucun fichier telechargeur_youtube_v*.pyw trouvé.")
    return Path(max(sources, key=source_version))


def source_version_number(source: Path) -> str:
    match = re.search(r"_v(\d+)\.(\d+)", source.name)
    return f"{match.group(1)}.{match.group(2)}.0.0" if match else "1.0.0.0"


def data_files(full: bool) -> list[Path]:
    names = list(APP_FILES) + (list(TOOL_FILES) if full else [])
    return [PROJECT_DIR / name for name in names] + sorted(PROJECT_DIR.glob("social_*.png"))


def toolchain_id() -> str:
    try:
        nuitka_version = importlib.metadata.version("nuitka")
    except importlib.metadata.PackageNotFoundError:
        nuitka_version = "?"
    return f"python {sys.version} | nuitka {nuitka_version}"


def build_id(files: list[Path], extra: str = "") -> str:
    # The unpack folder must change with the content and the compiler, or
    # Nuitka would keep reusing the files unpacked by a previous build.
    digest = hashlib.sha256(extra.encode())
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def nuitka_arguments(source: Path, full: bool, output_dir: Path) -> list[str]:
    files = data_files(full)
    version = source_version_number(source)
    arguments = [
        str(source),
        "--onefile",
        "--onefile-cache-mode=cached",
        "--onefile-tempdir-spec={CACHE_DIR}/StreamDL/app/"
        + build_id(files + source_files(source), toolchain_id()),
        "--windows-console-mode=disable",
        "--enable-plugin=tk-inter",
        # Windows 11 theme files (Tcl scripts and images).
        "--include-package-data=sv_ttk",
        "--msvc=latest",
        f"--windows-icon-from-ico={PROJECT_DIR / 'download.ico'}",
        "--company-name=Clemzy",
        "--product-name=StreamDL",
        "--file-description=Téléchargeur Vidéo",
        f"--file-version={version}",
        f"--product-version={version}",
        f"--output-dir={output_dir}",
        f"--output-filename={EXE_NAME}.exe",
        "--remove-output",
    ]
    arguments += [f"--include-data-files={path}={path.name}" for path in files]
    return arguments


def pyinstaller_arguments(source: Path, full: bool) -> list[str]:
    # Absolute paths: PyInstaller resolves relative --add-data paths from --specpath.
    arguments = [
        str(source),
        "--name", EXE_NAME,
        "--onefile",
        "--windowed",
        "--noupx",
        "--clean",
        "--noconfirm",
        "--collect-data", "sv_ttk",
        "--icon", str(PROJECT_DIR / "download.ico"),
        "--distpath", str(PROJECT_DIR / "dist"),
        "--workpath", str(WORK_DIR / "pyinstaller"),
        "--specpath", str(WORK_DIR / "pyinstaller"),
    ]
    for path in data_files(full):
        arguments += ["--add-data", f"{path}{os.pathsep}."]
    return arguments


def source_files(source: Path) -> list[Path]:
    return [source] + [PROJECT_DIR / name for name in SOURCE_MODULES]


def refresh_bundled_ytdlp() -> None:
    # The full build embeds the single yt-dlp.exe: the folder build installed
    # by the light build would add its 140 files to the executable.
    spec = YTDLP_SINGLE_FILE
    bundled_path = PROJECT_DIR / "yt-dlp.exe"
    current = ToolCopy(str(bundled_path), run_version_command(spec, str(bundled_path)), "local")

    try:
        release = fetch_latest_release(spec)
    except Exception as exc:
        print(f"Vérification de yt-dlp impossible ({describe_error(exc)}), version locale conservée.")
        return

    if not is_newer_release(release, current):
        print(f"yt-dlp {current.version} est déjà la dernière version.")
        return

    print(f"Mise à jour de yt-dlp {current.version} -> {release.version}...")
    with tempfile.TemporaryDirectory() as temporary_dir:
        updated = install_release(spec, release, Path(temporary_dir))
        shutil.copy2(updated.path, bundled_path)
    print(f"yt-dlp {release.version} vérifié (SHA-256) et copié dans le projet.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile dist\\StreamDL.exe")
    parser.add_argument("--full", action="store_true", help="embarquer yt-dlp, Deno et ffmpeg")
    parser.add_argument("--pyinstaller", action="store_true", help="utiliser PyInstaller au lieu de Nuitka")
    options = parser.parse_args()

    if options.full:
        refresh_bundled_ytdlp()
    missing = [path.name for path in data_files(options.full) if not path.is_file()]
    if missing:
        sys.exit("Fichiers manquants pour le build : " + ", ".join(missing))

    source = find_latest_source()
    target = PROJECT_DIR / "dist" / f"{EXE_NAME}.exe"
    edition = "complète (outils embarqués)" if options.full else "légère"
    print(f"Compilation de {source.name}, édition {edition}...")

    if options.pyinstaller:
        import PyInstaller.__main__  # type: ignore[import-untyped]

        PyInstaller.__main__.run(pyinstaller_arguments(source, options.full))
    else:
        output_dir = WORK_DIR / "nuitka"
        command = [sys.executable, "-m", "nuitka", *nuitka_arguments(source, options.full, output_dir)]
        if subprocess.run(command, check=False).returncode != 0:
            sys.exit("La compilation Nuitka a échoué.")
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(output_dir / f"{EXE_NAME}.exe", target)

    print(f"Exécutable créé : {target} ({target.stat().st_size / 1024 / 1024:.1f} Mo)")


if __name__ == "__main__":
    main()
