"""Download, verify and update the external tools used by StreamDL.

The light executable does not bundle yt-dlp, Deno or ffmpeg. Each tool is
downloaded from its official GitHub releases into its own version folder under
%LOCALAPPDATA%\\StreamDL\\tools\\<tool>\\<version>, checked against the SHA-256
published with the release before it is ever executed, then kept up to date.
A folder is used only once its installed.json marker exists, so an interrupted
download is never selected, and a copy used by a running download is never
overwritten.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Optional


MB = 1024 * 1024
CHUNK_SIZE = MB
USER_AGENT = "StreamDL (+https://github.com/Clemzyy/StreamDL)"
MARKER_NAME = "installed.json"
# Private folder of an installation in progress, renamed into place at the end.
STAGING_PREFIX = ".installing-"
STAGING_MAX_AGE = 3600
STATE_NAME = "state.json"
RETRY_ATTEMPTS = 3
RETRY_DELAY = 0.5

# Downloads and their redirects may only reach GitHub over HTTPS.
ALLOWED_HOSTS = {"github.com", "api.github.com"}
ALLOWED_HOST_SUFFIX = ".githubusercontent.com"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
POWERSHELL_HASH_RE = re.compile(r"^\s*Hash\s*:\s*([0-9A-Fa-f]{64})\s*$")
POWERSHELL_PATH_RE = re.compile(r"^\s*Path\s*:\s*(.+?)\s*$")
TAG_RE = re.compile(r"^[A-Za-z0-9._-]+$")
# Each part of a path written into a tool folder: no separator, drive letter or "..".
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
# Names Windows opens as devices (NUL, CON...), whatever their extension.
WINDOWS_DEVICE_RE = re.compile(r"^(?:CON|PRN|AUX|NUL|COM\d|LPT\d)(?:\..*)?$", re.IGNORECASE)
NUMERIC_VERSION_RE = re.compile(r"^\d+(?:\.\d+)*$")

# Stable yt-dlp releases are dated (2026.10.26); nightly builds add a time component.
YTDLP_VERSION_RE = re.compile(r"^\d{4}\.\d{1,2}\.\d{1,2}(?:\.\d+)?$")
DENO_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
# The yt-dlp FFmpeg builds use a rolling "latest" tag; the build date names the version.
FFMPEG_VERSION_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d{4}$")
FFMPEG_BUILD_NAME_RE = re.compile(r"\((\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})\)")
# Only FFmpeg's own libraries: a DLL named like a Windows one (version.dll)
# would be loaded from the tool folder first.
FFMPEG_MEMBER_RE = re.compile(
    r"^[^/]+/bin/((?:ffmpeg|ffprobe)\.exe"
    r"|(?:avcodec|avdevice|avfilter|avformat|avutil|postproc|swresample|swscale)-\d+\.dll)$"
)
METADATA_MAX_BYTES = 5 * MB

ProgressCallback = Callable[[int, Optional[int]], None]


class UpdateError(Exception):
    """A release could not be found, downloaded or verified."""


class ChecksumMismatch(UpdateError):
    """The downloaded file differs from the SHA-256 published with the release."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    exe_name: str
    repository: str
    asset_name: str
    checksums_name: str
    version_pattern: re.Pattern[str]
    version_from_release: Callable[[str, Optional[str]], Optional[str]]
    version_args: tuple[str, ...]
    version_from_output: Callable[[str], Optional[str]]
    required_free_bytes: int
    max_download_bytes: int
    max_unpacked_bytes: int = 0
    # Zip member name -> path to extract ("/"-separated), or None to skip it.
    select_member: Optional[Callable[[str], Optional[str]]] = None
    # Folders a complete copy has beside its executable.
    required_dirs: tuple[str, ...] = ()
    # False when the executable cannot report the release version (ffmpeg).
    exact_version_check: bool = True
    # 0 checks for updates at each launch.
    check_interval_days: int = 0

    @property
    def api_url(self) -> str:
        return f"https://api.github.com/repos/{self.repository}/releases/latest"

    @property
    def latest_page_url(self) -> str:
        return f"https://github.com/{self.repository}/releases/latest"

    def asset_url(self, tag: str, name: str) -> str:
        return f"https://github.com/{self.repository}/releases/download/{tag}/{name}"


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    asset_url: str
    checksums_url: str
    # SHA-256 that GitHub computed for the asset, when the API provided it.
    published_digest: Optional[str] = None

    @classmethod
    def for_tag(cls, spec: ToolSpec, tag: str, version: str,
                published_digest: Optional[str] = None) -> "ReleaseInfo":
        return cls(
            version=version,
            asset_url=spec.asset_url(tag, spec.asset_name),
            checksums_url=spec.asset_url(tag, spec.checksums_name),
            published_digest=published_digest,
        )


@dataclass(frozen=True)
class ToolCopy:
    path: str
    version: Optional[str]
    # "local" (beside the application), "managed" or "path".
    source: str

    @property
    def version_key(self) -> tuple[int, ...]:
        return version_key(self.version)


def parse_version(
    text: Optional[str], pattern: re.Pattern[str] = YTDLP_VERSION_RE
) -> Optional[tuple[int, ...]]:
    if not text or not pattern.fullmatch(text.strip()):
        return None
    return tuple(int(part) for part in text.strip().split("."))


def version_key(version: Optional[str]) -> tuple[int, ...]:
    if not version or not NUMERIC_VERSION_RE.fullmatch(version):
        return (0,)
    return tuple(int(part) for part in version.split("."))


def _ytdlp_version_from_release(tag: str, name: Optional[str]) -> Optional[str]:
    return tag if YTDLP_VERSION_RE.fullmatch(tag) else None


def _ytdlp_version_from_output(output: str) -> Optional[str]:
    lines = output.strip().splitlines()
    version = lines[-1].strip() if lines else ""
    return version if YTDLP_VERSION_RE.fullmatch(version) else None


def _ytdlp_member(member: str) -> Optional[str]:
    if member == "yt-dlp.exe" or member.startswith("_internal/"):
        return member
    return None


def _deno_version_from_release(tag: str, name: Optional[str]) -> Optional[str]:
    version = tag[1:] if tag.startswith("v") else tag
    return version if DENO_VERSION_RE.fullmatch(version) else None


def _deno_version_from_output(output: str) -> Optional[str]:
    match = re.match(r"\s*deno (\d+\.\d+\.\d+)", output)
    return match.group(1) if match else None


def _deno_member(member: str) -> Optional[str]:
    return "deno.exe" if member == "deno.exe" else None


def _ffmpeg_version_from_release(tag: str, name: Optional[str]) -> Optional[str]:
    match = FFMPEG_BUILD_NAME_RE.search(name or "")
    if not match:
        return None
    year, month, day, hour, minute = match.groups()
    return f"{year}.{month}.{day}.{hour}{minute}"


def _ffmpeg_version_from_output(output: str) -> Optional[str]:
    return "ffmpeg" if output.lstrip().startswith("ffmpeg version") else None


def _ffmpeg_member(member: str) -> Optional[str]:
    match = FFMPEG_MEMBER_RE.fullmatch(member)
    return match.group(1) if match else None


# The folder build: yt-dlp.exe beside its _internal libraries. It starts in
# 0.5 s, against 1.5 s for the single yt-dlp.exe, which unpacks itself into a
# temporary folder at every run, and StreamDL runs it twice per video.
YTDLP = ToolSpec(
    name="yt-dlp",
    exe_name="yt-dlp.exe",
    repository="yt-dlp/yt-dlp",
    asset_name="yt-dlp_win.zip",
    checksums_name="SHA2-256SUMS",
    version_pattern=YTDLP_VERSION_RE,
    version_from_release=_ytdlp_version_from_release,
    version_args=("--version",),
    version_from_output=_ytdlp_version_from_output,
    required_free_bytes=200 * MB,
    max_download_bytes=100 * MB,
    max_unpacked_bytes=200 * MB,
    select_member=_ytdlp_member,
    required_dirs=("_internal",),
)

# The single yt-dlp.exe, embedded by the full build (build_exe.py --full).
YTDLP_SINGLE_FILE = replace(
    YTDLP,
    asset_name="yt-dlp.exe",
    max_unpacked_bytes=0,
    select_member=None,
    required_dirs=(),
)

DENO = ToolSpec(
    name="deno",
    exe_name="deno.exe",
    repository="denoland/deno",
    asset_name="deno-x86_64-pc-windows-msvc.zip",
    checksums_name="deno-x86_64-pc-windows-msvc.zip.sha256sum",
    version_pattern=DENO_VERSION_RE,
    version_from_release=_deno_version_from_release,
    version_args=("--version",),
    version_from_output=_deno_version_from_output,
    required_free_bytes=400 * MB,
    max_download_bytes=150 * MB,
    max_unpacked_bytes=300 * MB,
    select_member=_deno_member,
    check_interval_days=30,
)

FFMPEG = ToolSpec(
    name="ffmpeg",
    exe_name="ffmpeg.exe",
    repository="yt-dlp/FFmpeg-Builds",
    asset_name="ffmpeg-master-latest-win64-gpl-shared.zip",
    checksums_name="checksums.sha256",
    version_pattern=FFMPEG_VERSION_RE,
    version_from_release=_ffmpeg_version_from_release,
    version_args=("-version",),
    version_from_output=_ffmpeg_version_from_output,
    required_free_bytes=700 * MB,
    max_download_bytes=250 * MB,
    max_unpacked_bytes=400 * MB,
    select_member=_ffmpeg_member,
    exact_version_check=False,
    check_interval_days=30,
)

TOOL_SPECS = (YTDLP, DENO, FFMPEG)


def default_storage_dir(app_name: str = "StreamDL") -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if not local_app_data:
        local_app_data = str(Path.home() / "AppData" / "Local")
    return Path(local_app_data) / app_name / "tools"


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


def _check_url(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not (
        host in ALLOWED_HOSTS or host.endswith(ALLOWED_HOST_SUFFIX)
    ):
        raise UpdateError(f"adresse de téléchargement refusée : {url}")


class _GitHubOnlyRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Checked before following, so no connection is made to another host.
        _check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_GitHubOnlyRedirects)


def _open_url(url: str, timeout: float):
    """Open an HTTPS GitHub URL; any other scheme or host is refused."""
    _check_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    response = _OPENER.open(request, timeout=timeout)
    try:
        _check_url(response.geturl())
    except UpdateError:
        response.close()
        raise
    return response


def _read_metadata(response) -> bytes:
    data = response.read(METADATA_MAX_BYTES + 1)
    if len(data) > METADATA_MAX_BYTES:
        raise UpdateError("réponse de GitHub anormalement volumineuse")
    return data


def _github_digest(asset: dict) -> Optional[str]:
    digest = str(asset.get("digest") or "").lower()
    if digest.startswith("sha256:") and SHA256_RE.fullmatch(digest[7:]):
        return digest[7:]
    return None


def fetch_latest_release(spec: ToolSpec, timeout: float = 15) -> ReleaseInfo:
    """Return the latest release published on github.com/<spec.repository>."""
    try:
        with _open_url(spec.api_url, timeout) as response:
            data = json.loads(_read_metadata(response).decode("utf-8"))
        tag = str(data.get("tag_name") or "")
        version = spec.version_from_release(tag, data.get("name"))
        assets = {asset.get("name"): asset for asset in data.get("assets") or []}
        if version and TAG_RE.fullmatch(tag):
            if spec.asset_name in assets and spec.checksums_name in assets:
                return ReleaseInfo.for_tag(
                    spec, tag, version, _github_digest(assets[spec.asset_name])
                )
            # Assets are uploaded a few minutes after the tag is published.
            raise UpdateError(f"la version {version} de {spec.name} est en cours de publication sur GitHub")
    except urllib.error.HTTPError as exc:
        # The anonymous API quota is 60 requests per hour; the public releases
        # page below is not subject to it.
        if exc.code not in (403, 429):
            raise
    except (ValueError, AttributeError, TypeError):
        pass

    with _open_url(spec.latest_page_url, timeout) as response:
        final_url = response.geturl()
    tag = urllib.parse.unquote(final_url.rstrip("/").rsplit("/", 1)[-1])
    version = spec.version_from_release(tag, None) if TAG_RE.fullmatch(tag) else None
    if not version:
        raise UpdateError(f"impossible de lire la dernière version de {spec.name} sur GitHub")
    return ReleaseInfo.for_tag(spec, tag, version)


def parse_checksums(text: str, asset_name: str) -> Optional[str]:
    """Read "<sha256>  <name>" lines or PowerShell Get-FileHash output (Deno)."""
    lines = text.splitlines()
    for line in lines:
        parts = line.strip().split()
        if len(parts) == 2 and parts[1].lstrip("*") == asset_name:
            digest = parts[0].lower()
            if SHA256_RE.fullmatch(digest):
                return digest

    digest_for_next_path = None
    for line in lines:
        hash_match = POWERSHELL_HASH_RE.match(line)
        if hash_match:
            digest_for_next_path = hash_match.group(1).lower()
            continue
        path_match = POWERSHELL_PATH_RE.match(line)
        if path_match and digest_for_next_path:
            if re.split(r"[\\/]", path_match.group(1))[-1] == asset_name:
                return digest_for_next_path
            digest_for_next_path = None
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


def run_version_command(spec: ToolSpec, exe_path: str, timeout: float = 90) -> Optional[str]:
    """Run the tool's version command; None when it does not start."""
    try:
        result = subprocess.run(
            [exe_path, *spec.version_args],
            timeout=timeout,
            **_hidden_process_kwargs(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return spec.version_from_output(result.stdout or "")


def _is_complete(spec: ToolSpec, folder: Path) -> bool:
    # A single yt-dlp.exe installed by StreamDL 1.84 to 1.88 has no _internal
    # folder: it is not used, and the folder build replaces it.
    return (
        (folder / MARKER_NAME).is_file()
        and (folder / spec.exe_name).is_file()
        and all((folder / name).is_dir() for name in spec.required_dirs)
    )


def find_installed_copies(spec: ToolSpec, storage_dir: Path) -> list[ToolCopy]:
    """Complete managed copies, newest first. Unfinished installs are never listed."""
    copies: list[ToolCopy] = []
    try:
        entries = list((storage_dir / spec.name).iterdir())
    except OSError:
        return copies

    for entry in entries:
        if parse_version(entry.name, spec.version_pattern) and _is_complete(spec, entry):
            copies.append(ToolCopy(str(entry / spec.exe_name), entry.name, "managed"))

    copies.sort(key=lambda copy: copy.version_key, reverse=True)
    return copies


def find_exe_on_path(name: str) -> Optional[str]:
    """A real .exe found through PATH; never a .bat/.cmd shim or a relative path."""
    found = shutil.which(name)
    if found and os.path.isabs(found) and found.lower().endswith(".exe"):
        return found
    return None


def resolve_tool(spec: ToolSpec, local_dirs: list[str], storage_dir: Path,
                 allow_path: bool = True) -> Optional[ToolCopy]:
    """Instant lookup without running anything: local folders, managed copy, then PATH."""
    for folder in local_dirs:
        candidate = os.path.join(folder, spec.exe_name)
        if os.path.isfile(candidate):
            return ToolCopy(candidate, None, "local")

    installed = find_installed_copies(spec, storage_dir)
    if installed:
        return installed[0]

    on_path = find_exe_on_path(Path(spec.exe_name).stem) if allow_path else None
    return ToolCopy(on_path, None, "path") if on_path else None


def is_newer_release(release: ReleaseInfo, current: Optional[ToolCopy]) -> bool:
    return current is None or version_key(release.version) > current.version_key


def _retry(func, *args):
    # Antivirus scanners briefly lock freshly written executables.
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return func(*args)
        except PermissionError:
            if attempt == RETRY_ATTEMPTS - 1:
                raise
            time.sleep(RETRY_DELAY)
    return None


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _check_free_space(spec: ToolSpec, storage_dir: Path) -> None:
    storage_dir.mkdir(parents=True, exist_ok=True)
    try:
        free = shutil.disk_usage(storage_dir).free
    except OSError:
        return
    if free < spec.required_free_bytes:
        raise UpdateError(
            f"espace disque insuffisant pour {spec.name} : {free // MB} Mo libres, "
            f"{spec.required_free_bytes // MB} Mo nécessaires"
        )


def _content_length(response) -> Optional[int]:
    value = str(response.headers.get("Content-Length") or "")
    return int(value) if value.isdigit() else None


def _download(spec: ToolSpec, url: str, handle: int, expected_digest: str,
              progress: Optional[ProgressCallback], timeout: float) -> None:
    digest = hashlib.sha256()
    done = 0
    with os.fdopen(handle, "wb") as output, _open_url(url, timeout) as response:
        total = _content_length(response)
        if total is not None and total > spec.max_download_bytes:
            raise UpdateError(f"le fichier de {spec.name} est anormalement volumineux")
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            done += len(chunk)
            if done > spec.max_download_bytes:
                raise UpdateError(f"le fichier de {spec.name} est anormalement volumineux")
            digest.update(chunk)
            output.write(chunk)
            if progress:
                progress(done, total)

    if digest.hexdigest() != expected_digest:
        raise ChecksumMismatch(
            f"le fichier de {spec.name} ne correspond pas à l'empreinte SHA-256 publiée"
        )


def _extract_members(spec: ToolSpec, zip_path: str, target_dir: Path) -> None:
    """Extract only whitelisted members into target_dir, at the paths select_member gives."""
    select_member = spec.select_member
    assert select_member is not None
    written = 0
    found_exe = False
    try:
        with zipfile.ZipFile(zip_path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                name = select_member(info.filename)
                if name is None:
                    continue
                parts = name.split("/")
                if name == MARKER_NAME or not all(
                    SAFE_NAME_RE.fullmatch(part) and not WINDOWS_DEVICE_RE.fullmatch(part)
                    for part in parts
                ):
                    raise UpdateError(f"nom de fichier refusé dans l'archive : {info.filename}")
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise UpdateError(f"lien symbolique refusé dans l'archive : {info.filename}")
                if written + info.file_size > spec.max_unpacked_bytes:
                    raise UpdateError(f"l'archive de {spec.name} est anormalement volumineuse")
                target = target_dir.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, open(target, "xb") as output:
                    while True:
                        chunk = source.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > spec.max_unpacked_bytes:
                            raise UpdateError(f"l'archive de {spec.name} est anormalement volumineuse")
                        output.write(chunk)
                found_exe = found_exe or name == spec.exe_name
    except zipfile.BadZipFile as exc:
        raise UpdateError(f"l'archive de {spec.name} est invalide") from exc
    except FileExistsError as exc:
        raise UpdateError(f"l'archive de {spec.name} contient des fichiers en double") from exc

    if not found_exe:
        raise UpdateError(f"{spec.exe_name} est absent de l'archive de {spec.name}")
    for folder in spec.required_dirs:
        if not (target_dir / folder).is_dir():
            raise UpdateError(f"le dossier {folder} est absent de l'archive de {spec.name}")


def _complete_copy(spec: ToolSpec, folder: Path, version: str) -> Optional[ToolCopy]:
    if _is_complete(spec, folder):
        return ToolCopy(str(folder / spec.exe_name), version, "managed")
    return None


def _check_starts(spec: ToolSpec, exe_path: Path, version: str) -> None:
    # Retried: an antivirus may briefly block a freshly written executable.
    reported = None
    for attempt in range(RETRY_ATTEMPTS):
        reported = run_version_command(spec, str(exe_path))
        if reported is not None and (
            not spec.exact_version_check
            or parse_version(reported, spec.version_pattern)
            == parse_version(version, spec.version_pattern)
        ):
            return
        if attempt < RETRY_ATTEMPTS - 1:
            time.sleep(RETRY_DELAY)
    raise UpdateError(
        f"{spec.name} {version} ne démarre pas correctement "
        f"(version lue : {reported or 'aucune'})"
    )


def install_release(spec: ToolSpec, release: ReleaseInfo, storage_dir: Path,
                    progress: Optional[ProgressCallback] = None, timeout: float = 60) -> ToolCopy:
    """Download, check the published SHA-256, unpack, then check that the tool starts.

    Everything happens in a private staging folder renamed into place at the
    end, so two StreamDL windows installing at the same time never collide.
    """
    tool_dir = storage_dir / spec.name
    target_dir = tool_dir / release.version
    existing = _complete_copy(spec, target_dir, release.version)
    if existing:
        return existing

    _check_free_space(spec, storage_dir)
    try:
        with _open_url(release.checksums_url, timeout) as response:
            checksums_text = _read_metadata(response).decode("utf-8", errors="replace")
    except http.client.HTTPException as exc:
        raise UpdateError(f"lecture de {spec.checksums_name} interrompue") from exc

    expected_digest = parse_checksums(checksums_text, spec.asset_name)
    if not expected_digest:
        raise UpdateError(f"empreinte de {spec.asset_name} absente de {spec.checksums_name}")
    if release.published_digest and release.published_digest != expected_digest:
        # Two independent publications disagree, or the rolling ffmpeg build
        # changed since the release was read.
        raise ChecksumMismatch(
            f"l'empreinte de {spec.asset_name} diffère entre GitHub et {spec.checksums_name}"
        )

    tool_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=str(tool_dir)))
    try:
        handle, partial_path = tempfile.mkstemp(suffix=".part", dir=str(staging_dir))
        try:
            _download(spec, release.asset_url, handle, expected_digest, progress, timeout)
            if spec.select_member:
                _extract_members(spec, partial_path, staging_dir)
            else:
                _retry(os.replace, partial_path, str(staging_dir / spec.exe_name))
        except http.client.HTTPException as exc:
            raise UpdateError(f"téléchargement de {spec.name} interrompu") from exc
        finally:
            _remove_quietly(partial_path)

        _check_starts(spec, staging_dir / spec.exe_name, release.version)
        # Written last: its presence is what makes a folder selectable.
        (staging_dir / MARKER_NAME).write_text(
            json.dumps({"version": release.version, "sha256": expected_digest}, indent=2),
            encoding="utf-8",
        )

        if target_dir.exists() and not _complete_copy(spec, target_dir, release.version):
            shutil.rmtree(target_dir, ignore_errors=True)
        try:
            _retry(os.replace, str(staging_dir), str(target_dir))
        except OSError:
            # Another StreamDL window finished installing the same version first.
            existing = _complete_copy(spec, target_dir, release.version)
            if existing is None:
                raise
            return existing
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

    return ToolCopy(str(target_dir / spec.exe_name), release.version, "managed")


def remove_superseded_copies(spec: ToolSpec, storage_dir: Path, keep_path: Optional[str]) -> None:
    """Best-effort cleanup, run before any download of the session can use a copy.

    Abandoned staging folders are removed once they are an hour old, so an
    installation running in another StreamDL window is left alone.
    """
    keep_dir = Path(keep_path).parent if keep_path else None
    try:
        entries = list((storage_dir / spec.name).iterdir())
    except OSError:
        return

    for entry in entries:
        if not entry.is_dir() or entry == keep_dir:
            continue
        if parse_version(entry.name, spec.version_pattern):
            shutil.rmtree(entry, ignore_errors=True)
        elif entry.name.startswith(STAGING_PREFIX):
            try:
                abandoned = time.time() - entry.stat().st_mtime > STAGING_MAX_AGE
            except OSError:
                continue
            if abandoned:
                shutil.rmtree(entry, ignore_errors=True)


def remove_legacy_copies(storage_dir: Path) -> None:
    """Remove %LOCALAPPDATA%\\StreamDL\\yt-dlp, used by versions 1.82 and 1.83."""
    shutil.rmtree(storage_dir.parent / "yt-dlp", ignore_errors=True)


def _read_state(storage_dir: Path) -> dict:
    try:
        data = json.loads((storage_dir / STATE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def is_check_due(spec: ToolSpec, storage_dir: Path, now: Optional[float] = None) -> bool:
    if spec.check_interval_days <= 0:
        return True
    now = time.time() if now is None else now
    entry = _read_state(storage_dir).get(spec.name)
    last_check = entry.get("last_check") if isinstance(entry, dict) else None
    if (
        not isinstance(last_check, (int, float))
        or not math.isfinite(last_check)
        or last_check > now
    ):
        return True
    return now - last_check >= spec.check_interval_days * 86400


def record_check(spec: ToolSpec, storage_dir: Path, now: Optional[float] = None) -> None:
    state = _read_state(storage_dir)
    state[spec.name] = {"last_check": time.time() if now is None else now}
    storage_dir.mkdir(parents=True, exist_ok=True)
    handle, temporary_path = tempfile.mkstemp(prefix="state-", suffix=".json", dir=str(storage_dir))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            json.dump(state, output, indent=2)
        _retry(os.replace, temporary_path, str(storage_dir / STATE_NAME))
    finally:
        _remove_quietly(temporary_path)
