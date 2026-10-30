"""Dependency-free automatic updates of yt-dlp.exe from its official releases.

Each verified update is stored in its own version folder under
%LOCALAPPDATA%\\StreamDL\\yt-dlp. A copy used by a running download is
therefore never overwritten, and the yt-dlp.exe bundled with the application
stays the fallback whenever no newer verified copy is available.
"""

from __future__ import annotations

import glob
import hashlib
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


RELEASES_API_URL = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
RELEASES_LATEST_PAGE_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest"
RELEASE_ASSET_URL = "https://github.com/yt-dlp/yt-dlp/releases/download/{version}/{name}"
EXE_ASSET_NAME = "yt-dlp.exe"
CHECKSUMS_ASSET_NAME = "SHA2-256SUMS"
USER_AGENT = "StreamDL (+https://github.com/Clemzyy/StreamDL)"

# Stable releases are dated (2026.10.26); nightly builds add a time component.
VERSION_RE = re.compile(r"^\d{4}\.\d{1,2}\.\d{1,2}(?:\.\d+)?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class UpdateError(Exception):
    """A release could not be found, downloaded or verified."""


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    exe_url: str
    checksums_url: str

    @classmethod
    def for_version(cls, version: str) -> "ReleaseInfo":
        return cls(
            version=version,
            exe_url=RELEASE_ASSET_URL.format(version=version, name=EXE_ASSET_NAME),
            checksums_url=RELEASE_ASSET_URL.format(version=version, name=CHECKSUMS_ASSET_NAME),
        )


@dataclass(frozen=True)
class YtDlpCopy:
    path: str
    version: Optional[str]

    @property
    def version_key(self) -> tuple[int, ...]:
        return parse_version(self.version) or (0,)


def parse_version(text: Optional[str]) -> Optional[tuple[int, ...]]:
    if not text or not VERSION_RE.match(text.strip()):
        return None
    return tuple(int(part) for part in text.strip().split("."))


def default_storage_dir(app_name: str = "StreamDL") -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if not local_app_data:
        local_app_data = str(Path.home() / "AppData" / "Local")
    return Path(local_app_data) / app_name / "yt-dlp"


def describe_error(exc: BaseException) -> str:
    """Short French explanation suitable for the application journal."""
    if isinstance(exc, UpdateError):
        return str(exc)
    if isinstance(exc, urllib.error.HTTPError):
        return f"GitHub a répondu avec le code HTTP {exc.code}"
    if isinstance(exc, TimeoutError):
        return "GitHub ne répond pas (délai dépassé)"
    if isinstance(exc, urllib.error.URLError):
        return "connexion à GitHub impossible (hors ligne ?)"
    return f"{type(exc).__name__} : {exc}"


def _open_url(url: str, timeout: float):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=timeout)


def fetch_latest_release(timeout: float = 15) -> ReleaseInfo:
    """Return the latest stable release published on github.com/yt-dlp/yt-dlp."""
    try:
        with _open_url(RELEASES_API_URL, timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        version = str(data.get("tag_name") or "").strip()
        asset_names = {asset.get("name") for asset in data.get("assets") or []}
        if parse_version(version) and {EXE_ASSET_NAME, CHECKSUMS_ASSET_NAME} <= asset_names:
            return ReleaseInfo.for_version(version)
        if parse_version(version):
            # Assets are uploaded a few minutes after the tag is published.
            raise UpdateError(f"la version {version} est en cours de publication sur GitHub")
    except urllib.error.HTTPError as exc:
        # The anonymous API quota is 60 requests per hour; the public releases
        # page below is not subject to it.
        if exc.code not in (403, 429):
            raise
    except (ValueError, AttributeError):
        pass

    with _open_url(RELEASES_LATEST_PAGE_URL, timeout) as response:
        final_url = response.geturl()
    version = final_url.rstrip("/").rsplit("/", 1)[-1]
    if not parse_version(version):
        raise UpdateError("impossible de lire la dernière version sur la page des releases GitHub")
    return ReleaseInfo.for_version(version)


def parse_checksums(text: str, asset_name: str) -> Optional[str]:
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and parts[1].lstrip("*") == asset_name:
            digest = parts[0].lower()
            if SHA256_RE.match(digest):
                return digest
    return None


def _hidden_process_kwargs() -> dict:
    kwargs = {
        "capture_output": True,
        "stdin": subprocess.DEVNULL,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


def read_exe_version(exe_path: str, timeout: float = 90) -> Optional[str]:
    """Run ``yt-dlp --version``; None when the executable does not start."""
    try:
        result = subprocess.run(
            [exe_path, "--version"],
            timeout=timeout,
            **_hidden_process_kwargs(),
        )
    except (OSError, subprocess.SubprocessError):
        return None

    lines = (result.stdout or "").strip().splitlines()
    if result.returncode != 0 or not lines:
        return None
    version = lines[-1].strip()
    return version if parse_version(version) else None


def find_installed_copies(storage_dir: Path) -> list[YtDlpCopy]:
    """Managed copies, newest first. Partial downloads are never listed."""
    copies = []
    try:
        entries = list(storage_dir.iterdir())
    except OSError:
        return copies

    for entry in entries:
        exe_path = entry / EXE_ASSET_NAME
        if parse_version(entry.name) and exe_path.is_file():
            copies.append(YtDlpCopy(str(exe_path), entry.name))

    copies.sort(key=lambda copy: copy.version_key, reverse=True)
    return copies


def find_best_local_copy(bundled_path: Optional[str], storage_dir: Path) -> Optional[YtDlpCopy]:
    """Pick the newest working copy between the bundled exe and managed updates."""
    bundled = None
    if bundled_path and os.path.isfile(bundled_path):
        bundled = YtDlpCopy(bundled_path, read_exe_version(bundled_path))

    for copy in find_installed_copies(storage_dir):
        if bundled and copy.version_key <= bundled.version_key:
            break
        # A managed copy is trusted only while it starts and reports its folder version.
        if parse_version(read_exe_version(copy.path)) == parse_version(copy.version):
            return copy
        shutil.rmtree(Path(copy.path).parent, ignore_errors=True)

    return bundled


def is_newer_release(release: ReleaseInfo, current: Optional[YtDlpCopy]) -> bool:
    return current is None or (parse_version(release.version) or (0,)) > current.version_key


def install_release(release: ReleaseInfo, storage_dir: Path, timeout: float = 60) -> YtDlpCopy:
    """Download yt-dlp.exe, check the published SHA-256, then check that it starts."""
    try:
        with _open_url(release.checksums_url, timeout) as response:
            checksums_text = response.read().decode("utf-8", errors="replace")
    except http.client.HTTPException as exc:
        raise UpdateError(f"lecture de {CHECKSUMS_ASSET_NAME} interrompue") from exc

    expected_digest = parse_checksums(checksums_text, EXE_ASSET_NAME)
    if not expected_digest:
        raise UpdateError(f"empreinte de {EXE_ASSET_NAME} absente de {CHECKSUMS_ASSET_NAME}")

    target_dir = storage_dir / release.version
    target_dir.mkdir(parents=True, exist_ok=True)
    for stale_part in glob.glob(str(target_dir / "*.part")):
        try:
            os.remove(stale_part)
        except OSError:
            pass

    # The partial file stays in the version folder, which is listed only once
    # yt-dlp.exe exists there, so an interrupted download is never selected.
    handle, partial_path = tempfile.mkstemp(prefix="yt-dlp-", suffix=".part", dir=str(target_dir))
    target_path = target_dir / EXE_ASSET_NAME
    try:
        digest = hashlib.sha256()
        with os.fdopen(handle, "wb") as output, _open_url(release.exe_url, timeout) as response:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                output.write(chunk)

        if digest.hexdigest() != expected_digest:
            raise UpdateError(
                "le fichier téléchargé ne correspond pas à l'empreinte SHA-256 publiée par yt-dlp"
            )

        os.replace(partial_path, target_path)
    except http.client.HTTPException as exc:
        raise UpdateError(f"téléchargement de {EXE_ASSET_NAME} interrompu") from exc
    finally:
        if os.path.exists(partial_path):
            try:
                os.remove(partial_path)
            except OSError:
                pass

    reported_version = read_exe_version(str(target_path))
    if parse_version(reported_version) != parse_version(release.version):
        shutil.rmtree(target_dir, ignore_errors=True)
        raise UpdateError(
            f"la nouvelle version ne démarre pas correctement (version lue : {reported_version or 'aucune'})"
        )

    return YtDlpCopy(str(target_path), release.version)


def remove_superseded_copies(storage_dir: Path, keep_path: Optional[str]) -> None:
    """Best-effort cleanup; a copy still used by a download is removed next launch."""
    keep_dir = Path(keep_path).parent if keep_path else None
    try:
        entries = list(storage_dir.iterdir())
    except OSError:
        return

    for entry in entries:
        if entry.is_dir() and parse_version(entry.name) and entry != keep_dir:
            shutil.rmtree(entry, ignore_errors=True)
