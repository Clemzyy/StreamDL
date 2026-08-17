"""Small, dependency-free helpers for StreamDL authentication recovery.

This module deliberately never reads browser databases or cookie values itself.
It only validates a user-selected Netscape cookie file and prepares the options
that yt-dlp natively understands.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class AuthErrorType(str, Enum):
    AGE_RESTRICTED = "AGE_RESTRICTED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    COOKIES_REQUIRED = "COOKIES_REQUIRED"
    COOKIE_EXTRACTION_FAILED = "COOKIE_EXTRACTION_FAILED"
    COOKIE_DECRYPTION_FAILED = "COOKIE_DECRYPTION_FAILED"
    COOKIES_EXPIRED_OR_INVALID = "COOKIES_EXPIRED_OR_INVALID"
    UNKNOWN_AUTH_ERROR = "UNKNOWN_AUTH_ERROR"


class CookieSourceKind(str, Enum):
    NONE = "none"
    BROWSER = "browser"
    FILE = "file"


@dataclass(frozen=True)
class CookieSource:
    kind: CookieSourceKind = CookieSourceKind.NONE
    browser: Optional[str] = None
    file_path: Optional[str] = None

    @classmethod
    def none(cls) -> "CookieSource":
        return cls()

    @classmethod
    def browser_source(cls, browser: str) -> "CookieSource":
        return cls(kind=CookieSourceKind.BROWSER, browser=browser)

    @classmethod
    def file_source(cls, file_path: str) -> "CookieSource":
        return cls(kind=CookieSourceKind.FILE, file_path=file_path)

    @property
    def uses_cookies(self) -> bool:
        return self.kind is not CookieSourceKind.NONE

    def label(self) -> str:
        if self.kind is CookieSourceKind.BROWSER:
            return f"navigateur {self.browser or 'inconnu'}"
        if self.kind is CookieSourceKind.FILE:
            return "fichier cookies.txt"
        return "aucun cookie"


@dataclass(frozen=True)
class AuthErrorInfo:
    error_type: AuthErrorType
    returncode: int
    original_output: str
    safe_output: str
    cookie_source: CookieSource


# The patterns are intentionally grouped by cause rather than by one exact
# version-specific error message. yt-dlp changes wording occasionally, but its
# cookie and authentication diagnostics retain these key concepts.
COOKIE_EXTRACTION_PATTERNS = (
    re.compile(r"could not copy .*cookie database", re.I),
    re.compile(r"could not find .*cookies? database", re.I),
    re.compile(r"failed to (?:load|extract|read).*cookies?", re.I),
    re.compile(r"permission denied.*(?:cookies?|cookie database)", re.I),
    re.compile(r"(?:cookies?|cookie database).*permission denied", re.I),
    re.compile(r"browser .* does not support profiles", re.I),
)

COOKIE_DECRYPTION_PATTERNS = (
    re.compile(r"failed to decrypt", re.I),
    re.compile(r"could not be decrypted", re.I),
    re.compile(r"failed to decrypt with dpapi", re.I),
    re.compile(r"(?:dpapi|app[ -]?bound encryption)", re.I),
    re.compile(r"aes-gcm.*(?:mac check failed|key is wrong)", re.I),
    re.compile(r"possibly the key is wrong", re.I),
)

AGE_RESTRICTED_PATTERNS = (
    re.compile(r"sign in to confirm (?:your|you'?re) age", re.I),
    re.compile(r"(?:this )?video is age[- ]restricted", re.I),
    re.compile(r"confirm your age", re.I),
    re.compile(r"age verification", re.I),
)

COOKIES_REQUIRED_PATTERNS = (
    re.compile(r"use --cookies(?:-from-browser)? .*authentication", re.I),
    re.compile(r"cookies? (?:are )?required", re.I),
    re.compile(r"requires? (?:valid )?cookies", re.I),
)

LOGIN_REQUIRED_PATTERNS = (
    re.compile(r"sign in to confirm (?:you(?:'|’)re|you are) not a bot", re.I),
    re.compile(r"(?:login|log in|sign in) (?:is )?required", re.I),
    re.compile(r"(?:must|need to) (?:log|sign) in", re.I),
    re.compile(r"(?:members?|subscribers?)[ -]?only", re.I),
    re.compile(r"available only to (?:logged|signed)[ -]?in", re.I),
)

COOKIE_INVALID_PATTERNS = (
    re.compile(r"(?:cookies?|session) (?:have )?(?:expired|are expired|invalid)", re.I),
    re.compile(r"invalid (?:cookies?|session)", re.I),
)

GENERIC_AUTH_PATTERN = re.compile(
    r"(?:authenticat|sign in|log in|age[- ]restrict|confirm .*age|not a bot|(?:use|requires?) .*cookies?)",
    re.I,
)

SENSITIVE_LINE_PATTERN = re.compile(
    r"(?im)^.*(?:^|[\s:])(?:cookie|set-cookie|authorization|token|password)\s*[:=].*$"
)


def _matches_any(patterns, text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def combine_ytdlp_output(stdout_text: str, stderr_text: str) -> str:
    """Keep both streams: yt-dlp uses either depending on its execution mode."""
    parts = [part.strip() for part in (stderr_text, stdout_text) if part and part.strip()]
    return "\n".join(parts)


def sanitize_technical_text(text: str) -> str:
    """Redact accidental header-style secrets before a log or clipboard export."""
    cleaned = SENSITIVE_LINE_PATTERN.sub("[donnée sensible masquée]", text or "")
    cleaned = re.sub(r"(?i)(cookie|authorization|token|password)=[^\s;&]+", r"\1=[masqué]", cleaned)
    return cleaned.strip()


class AuthErrorDetector:
    """Classify a failed yt-dlp invocation without relying on one exact string."""

    @classmethod
    def detect(
        cls,
        returncode: int,
        stdout_text: str = "",
        stderr_text: str = "",
        cookie_source: Optional[CookieSource] = None,
    ) -> Optional[AuthErrorInfo]:
        if returncode == 0:
            return None

        source = cookie_source or CookieSource.none()
        original = combine_ytdlp_output(stdout_text, stderr_text)
        safe = sanitize_technical_text(original)

        # Browser extraction errors are distinct from an expired login: users
        # should be redirected to Firefox/cookies.txt, not asked to reconnect.
        if _matches_any(COOKIE_EXTRACTION_PATTERNS, original):
            category = AuthErrorType.COOKIE_EXTRACTION_FAILED
        elif _matches_any(COOKIE_DECRYPTION_PATTERNS, original):
            category = AuthErrorType.COOKIE_DECRYPTION_FAILED
        elif _matches_any(COOKIE_INVALID_PATTERNS, original):
            category = AuthErrorType.COOKIES_EXPIRED_OR_INVALID
        elif source.uses_cookies and (
            _matches_any(AGE_RESTRICTED_PATTERNS, original)
            or _matches_any(COOKIES_REQUIRED_PATTERNS, original)
            or _matches_any(LOGIN_REQUIRED_PATTERNS, original)
        ):
            category = AuthErrorType.COOKIES_EXPIRED_OR_INVALID
        elif _matches_any(AGE_RESTRICTED_PATTERNS, original):
            category = AuthErrorType.AGE_RESTRICTED
        elif _matches_any(COOKIES_REQUIRED_PATTERNS, original):
            category = AuthErrorType.COOKIES_REQUIRED
        elif _matches_any(LOGIN_REQUIRED_PATTERNS, original):
            category = AuthErrorType.LOGIN_REQUIRED
        elif GENERIC_AUTH_PATTERN.search(original):
            category = AuthErrorType.UNKNOWN_AUTH_ERROR
        else:
            return None

        return AuthErrorInfo(category, returncode, original, safe, source)


def find_firefox() -> Optional[str]:
    """Find standard Windows Firefox installations; do not install or alter it."""
    which_path = shutil.which("firefox.exe") or shutil.which("firefox")
    if which_path:
        return which_path

    roots = [
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramW6432"),
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("LOCALAPPDATA"),
    ]
    candidates = []
    for root in filter(None, roots):
        candidates.append(os.path.join(root, "Mozilla Firefox", "firefox.exe"))
    for candidate in dict.fromkeys(candidates):
        if os.path.isfile(candidate):
            return candidate
    return None


def validate_netscape_cookie_file(file_path: str) -> tuple[bool, str]:
    """Check only the structure, never expose or store the cookie contents."""
    try:
        path = Path(file_path)
        if not path.is_file():
            return False, "Le fichier sélectionné est introuvable."
        if path.stat().st_size > 16 * 1024 * 1024:
            return False, "Le fichier est anormalement volumineux pour un cookies.txt."
        content = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        return False, f"Impossible de lire le fichier : {exc}"

    lines = [line for line in content.splitlines() if line.strip()]
    if not lines or lines[0].strip() not in {"# HTTP Cookie File", "# Netscape HTTP Cookie File"}:
        return False, "Ce fichier ne semble pas être un cookies.txt Netscape valide."

    # #HttpOnly_ is a Netscape cookie line, not an ordinary comment.
    cookie_lines = [
        line for line in lines
        if not line.lstrip().startswith("#") or line.startswith("#HttpOnly_")
    ]
    if not any(len(line.split("\t")) >= 7 for line in cookie_lines):
        return False, "Le fichier ne contient pas de ligne de cookie Netscape exploitable."
    return True, "Fichier cookies.txt valide."


def _is_youtube_cookie_domain(domain: str) -> bool:
    """Allow only youtube.com and its subdomains; never broad Google cookies."""
    normalized = domain.lower().lstrip(".")
    return normalized == "youtube.com" or normalized.endswith(".youtube.com")


def create_youtube_only_cookie_copy(source_path: str) -> tuple[str, int]:
    """Create a user-temp Netscape file containing only YouTube-domain cookies.

    The source file is never changed. Cookie values are copied only into the
    short-lived file required by yt-dlp and are never logged or returned.
    """
    valid, message = validate_netscape_cookie_file(source_path)
    if not valid:
        raise ValueError(message)

    try:
        source_lines = Path(source_path).read_text(
            encoding="utf-8-sig", errors="replace"
        ).splitlines()
    except OSError as exc:
        raise OSError(f"Impossible de lire le fichier : {exc}") from exc

    selected_lines = []
    for line in source_lines:
        # A Netscape HttpOnly cookie begins with #HttpOnly_, while other #
        # lines are comments and must not be copied because they may reveal
        # information about the original export.
        cookie_line = line
        if line.startswith("#HttpOnly_"):
            cookie_line = line[len("#HttpOnly_"):]
        elif line.lstrip().startswith("#"):
            continue

        fields = cookie_line.split("\t")
        if len(fields) >= 7 and _is_youtube_cookie_domain(fields[0]):
            selected_lines.append(line)

    if not selected_lines:
        raise ValueError(
            "Le fichier ne contient aucun cookie pour youtube.com. "
            "Exportez les cookies du site YouTube, puis réessayez."
        )

    handle, temporary_path = tempfile.mkstemp(
        prefix="streamdl-youtube-",
        suffix=".cookies.txt",
    )
    try:
        # mkstemp creates a file with user-only permissions where supported.
        os.chmod(temporary_path, stat.S_IREAD | stat.S_IWRITE)
        with os.fdopen(handle, "w", encoding="utf-8", newline="\r\n") as output:
            output.write("# Netscape HTTP Cookie File\n")
            output.write("\n".join(selected_lines))
            output.write("\n")
    except Exception:
        try:
            os.remove(temporary_path)
        except OSError:
            pass
        raise

    return temporary_path, len(selected_lines)


def delete_temporary_cookie_file(file_path: str) -> bool:
    """Best-effort removal of a temporary cookie file; never overwrite data."""
    try:
        os.remove(file_path)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


class CookiePreferenceStore:
    """Persist only the optional file path; cookie contents are never copied."""

    def __init__(self, app_name: str = "StreamDL"):
        local_app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if not local_app_data:
            local_app_data = str(Path.home() / "AppData" / "Local")
        self.folder = Path(local_app_data) / app_name
        self.path = self.folder / "authentication.json"

    def get_cookie_file_path(self) -> Optional[str]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            value = data.get("cookies_file_path")
            return value if isinstance(value, str) and value else None
        except (OSError, ValueError, TypeError):
            return None

    def remember_cookie_file_path(self, file_path: str) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"cookies_file_path": file_path}, ensure_ascii=False, indent=2)
        handle, temporary_path = tempfile.mkstemp(prefix="auth-", suffix=".json", dir=str(self.folder))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as output:
                output.write(payload)
            os.replace(temporary_path, self.path)
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)

    def forget_cookie_file_path(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
