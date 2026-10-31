import hashlib
import http.client
import io
import json
import os
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest import mock

import tools_manager
from tools_manager import (
    DENO,
    FFMPEG,
    YTDLP,
    YTDLP_SINGLE_FILE,
    ChecksumMismatch,
    ReleaseInfo,
    ToolCopy,
    UpdateError,
    fetch_latest_release,
    find_installed_copies,
    install_release,
    is_check_due,
    is_newer_release,
    parse_checksums,
    parse_version,
    record_check,
    remove_legacy_copies,
    remove_superseded_copies,
    resolve_tool,
)


FAKE_EXE = b"MZ fake executable"

# Captured from deno-x86_64-pc-windows-msvc.zip.sha256sum (PowerShell Get-FileHash output).
DENO_SHA256SUM_TEMPLATE = (
    "\r\nAlgorithm : SHA256\r\n"
    "Hash      : {digest}\r\n"
    "Path      : C:\\a\\deno\\deno\\target\\release\\deno-x86_64-pc-windows-msvc.zip\r\n\r\n"
)


class FakeResponse(io.BytesIO):
    def __init__(self, data=b"", url="", fail_after=None):
        super().__init__(data)
        self.url = url
        self.headers = {"Content-Length": str(len(data))}
        self.fail_after = fail_after
        self.sent = 0

    def geturl(self):
        return self.url

    def read(self, size=-1):
        chunk = super().read(size)
        self.sent += len(chunk)
        if self.fail_after is not None and self.sent > self.fail_after:
            raise http.client.IncompleteRead(chunk)
        return chunk


def fake_github(responses):
    """Patch tools_manager._open_url with a {url: bytes | FakeResponse | Exception} table."""
    def open_url(url, timeout):
        value = responses[url]
        if isinstance(value, Exception):
            raise value
        if isinstance(value, FakeResponse):
            return value
        return FakeResponse(value, url)
    return mock.patch.object(tools_manager, "_open_url", side_effect=open_url)


def classic_checksums(data, name):
    digest = hashlib.sha256(data).hexdigest()
    return f"{'0' * 64}  other.zip\n{digest}  {name}\n".encode()


def make_zip(members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def api_release(tag, assets, name=None):
    return json.dumps({
        "tag_name": tag,
        "name": name or tag,
        "assets": [{"name": asset} for asset in assets],
    }).encode()


# yt-dlp_win.zip, the folder build: yt-dlp.exe beside its _internal libraries.
YTDLP_ZIP = make_zip({
    "yt-dlp.exe": FAKE_EXE,
    "_internal/python314.dll": b"python",
    "_internal/certifi/cacert.pem": b"certificates",
})
YTDLP_SUMS = classic_checksums(YTDLP_ZIP, YTDLP.asset_name)


class VersionTests(unittest.TestCase):
    def test_stable_and_nightly_versions(self):
        self.assertEqual(parse_version("2026.10.26"), (2026, 10, 26))
        self.assertEqual(parse_version(" 2026.10.26.232920\n"), (2026, 10, 26, 232920))
        self.assertLess(parse_version("2026.9.30"), parse_version("2026.10.1"))

    def test_invalid_versions(self):
        for text in (None, "", "latest", "v2026.10.26", "2026.10", "../2026.10.26"):
            self.assertIsNone(parse_version(text))

    def test_tool_specific_versions(self):
        self.assertEqual(parse_version("2.9.8", DENO.version_pattern), (2, 9, 8))
        self.assertIsNone(parse_version("2.9", DENO.version_pattern))
        self.assertEqual(parse_version("2026.10.30.1913", FFMPEG.version_pattern), (2026, 10, 30, 1913))

    def test_newer_release(self):
        release = ReleaseInfo.for_tag(YTDLP, "2026.10.26", "2026.10.26")
        self.assertTrue(is_newer_release(release, None))
        self.assertTrue(is_newer_release(release, ToolCopy("a", "2026.10.20", "managed")))
        self.assertTrue(is_newer_release(release, ToolCopy("a", None, "local")))
        self.assertFalse(is_newer_release(release, ToolCopy("a", "2026.10.26", "managed")))


class ChecksumTests(unittest.TestCase):
    def test_classic_format(self):
        text = classic_checksums(FAKE_EXE, "yt-dlp.exe").decode()
        self.assertEqual(parse_checksums(text, "yt-dlp.exe"), hashlib.sha256(FAKE_EXE).hexdigest())

    def test_powershell_format(self):
        digest = hashlib.sha256(b"deno").hexdigest()
        text = DENO_SHA256SUM_TEMPLATE.format(digest=digest.upper())
        self.assertEqual(parse_checksums(text, "deno-x86_64-pc-windows-msvc.zip"), digest)
        self.assertIsNone(parse_checksums(text, "deno-aarch64-pc-windows-msvc.zip"))

    def test_missing_or_malformed_digest(self):
        self.assertIsNone(parse_checksums("abc  yt-dlp.exe\n", "yt-dlp.exe"))
        self.assertIsNone(parse_checksums(f"{'0' * 64}  yt-dlp_x86.exe\n", "yt-dlp.exe"))


class FetchLatestReleaseTests(unittest.TestCase):
    def test_reads_ytdlp_api(self):
        api = json.dumps({"tag_name": "2026.10.26", "assets": [
            {"name": "yt-dlp.exe", "digest": "sha256:" + "B" * 64},
            {"name": "yt-dlp_win.zip", "digest": "sha256:" + "A" * 64},
            {"name": "SHA2-256SUMS"},
        ]}).encode()
        with fake_github({YTDLP.api_url: api}):
            release = fetch_latest_release(YTDLP)
        self.assertEqual(release.version, "2026.10.26")
        self.assertTrue(release.asset_url.endswith("/download/2026.10.26/yt-dlp_win.zip"))
        self.assertEqual(release.published_digest, "a" * 64)

    def test_tag_with_trailing_newline_is_refused(self):
        api = api_release("2026.10.26\n", ["yt-dlp.exe", "SHA2-256SUMS"])
        page = FakeResponse(b"<html>", "https://github.com/yt-dlp/yt-dlp/releases/tag/latest")
        with fake_github({YTDLP.api_url: api, YTDLP.latest_page_url: page}):
            with self.assertRaises(UpdateError):
                fetch_latest_release(YTDLP)

    def test_deno_tag_prefix_is_removed(self):
        api = api_release("v2.9.8", [DENO.asset_name, DENO.checksums_name])
        with fake_github({DENO.api_url: api}):
            release = fetch_latest_release(DENO)
        self.assertEqual(release.version, "2.9.8")
        self.assertIn("/download/v2.9.8/", release.asset_url)

    def test_ffmpeg_version_comes_from_rolling_release_name(self):
        api = api_release("latest", [FFMPEG.asset_name, FFMPEG.checksums_name],
                          name="Latest Auto-Build (2026-10-30 19:13)")
        with fake_github({FFMPEG.api_url: api}):
            release = fetch_latest_release(FFMPEG)
        self.assertEqual(release.version, "2026.10.30.1913")
        self.assertIn("/download/latest/", release.asset_url)

    def test_release_without_assets_yet(self):
        with fake_github({YTDLP.api_url: api_release("2026.10.26", [])}):
            with self.assertRaises(UpdateError):
                fetch_latest_release(YTDLP)

    def test_rate_limited_api_falls_back_to_releases_page(self):
        rate_limited = urllib.error.HTTPError(YTDLP.api_url, 403, "rate limit", {}, None)
        page = FakeResponse(b"<html>", "https://github.com/yt-dlp/yt-dlp/releases/tag/2026.10.26")
        with fake_github({YTDLP.api_url: rate_limited, YTDLP.latest_page_url: page}):
            release = fetch_latest_release(YTDLP)
        self.assertEqual(release.version, "2026.10.26")

    def test_rolling_tag_cannot_use_the_page_fallback(self):
        rate_limited = urllib.error.HTTPError(FFMPEG.api_url, 403, "rate limit", {}, None)
        page = FakeResponse(b"<html>", "https://github.com/yt-dlp/FFmpeg-Builds/releases/tag/latest")
        with fake_github({FFMPEG.api_url: rate_limited, FFMPEG.latest_page_url: page}):
            with self.assertRaises(UpdateError):
                fetch_latest_release(FFMPEG)


class OpenUrlTests(unittest.TestCase):
    def test_rejects_non_https_and_foreign_hosts(self):
        with mock.patch.object(tools_manager._OPENER, "open") as opener:
            for url in ("http://github.com/a", "https://example.com/a", "file:///C:/a.exe",
                        "https://github.com.evil.example/a"):
                with self.assertRaises(UpdateError):
                    tools_manager._open_url(url, 5)
            opener.assert_not_called()

    def test_redirect_to_foreign_host_is_not_followed(self):
        handler = tools_manager._GitHubOnlyRedirects()
        request = urllib.request.Request("https://github.com/a")
        with self.assertRaises(UpdateError):
            handler.redirect_request(request, None, 302, "Found", {}, "https://evil.example/a.exe")

    def test_rejects_final_url_on_foreign_host(self):
        response = FakeResponse(b"x", "https://evil.example/yt-dlp.exe")
        with mock.patch.object(tools_manager._OPENER, "open", return_value=response):
            with self.assertRaises(UpdateError):
                tools_manager._open_url("https://github.com/yt-dlp/yt-dlp/releases/download/a/b", 5)
        self.assertTrue(response.closed)

    def test_accepts_github_release_cdn(self):
        response = FakeResponse(b"x", "https://release-assets.githubusercontent.com/a")
        with mock.patch.object(tools_manager._OPENER, "open", return_value=response):
            self.assertIs(tools_manager._open_url("https://github.com/a", 5), response)


class StorageTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.storage = Path(self.temp.name) / "StreamDL" / "tools"

    def tearDown(self):
        self.temp.cleanup()

    def add_copy(self, spec, version, complete=True):
        folder = self.storage / spec.name / version
        folder.mkdir(parents=True)
        (folder / spec.exe_name).write_bytes(FAKE_EXE)
        for name in spec.required_dirs:
            (folder / name).mkdir()
        if complete:
            (folder / tools_manager.MARKER_NAME).write_text(json.dumps({"version": version}))
        return str(folder / spec.exe_name)


class StorageTests(StorageTestCase):
    def test_lists_complete_copies_newest_first(self):
        self.add_copy(YTDLP, "2026.9.1")
        self.add_copy(YTDLP, "2026.10.26")
        self.add_copy(YTDLP, "2026.11.1", complete=False)
        (self.storage / "yt-dlp" / "notes").mkdir()
        versions = [copy.version for copy in find_installed_copies(YTDLP, self.storage)]
        self.assertEqual(versions, ["2026.10.26", "2026.9.1"])

    def test_missing_storage(self):
        self.assertEqual(find_installed_copies(YTDLP, self.storage), [])

    def test_single_file_ytdlp_of_older_versions_is_not_used(self):
        # StreamDL 1.84 to 1.88 installed the single yt-dlp.exe, which starts
        # 1 s slower than the folder build that replaces it.
        folder = self.storage / "yt-dlp" / "2026.10.26"
        folder.mkdir(parents=True)
        (folder / "yt-dlp.exe").write_bytes(FAKE_EXE)
        (folder / tools_manager.MARKER_NAME).write_text(json.dumps({"version": "2026.10.26"}))
        self.assertEqual(find_installed_copies(YTDLP, self.storage), [])
        self.assertIsNone(resolve_tool(YTDLP, [], self.storage, allow_path=False))

    def test_cleanup_keeps_selected_copy_and_unknown_folders(self):
        old = self.add_copy(YTDLP, "2026.9.1")
        keep = self.add_copy(YTDLP, "2026.10.26")
        (self.storage / "yt-dlp" / "notes").mkdir()
        remove_superseded_copies(YTDLP, self.storage, keep)
        self.assertFalse(Path(old).exists())
        self.assertTrue(Path(keep).exists())
        self.assertTrue((self.storage / "yt-dlp" / "notes").exists())

    def test_cleanup_without_kept_copy_removes_all_versions(self):
        self.add_copy(YTDLP, "2026.9.1")
        self.add_copy(YTDLP, "2026.10.26")
        remove_superseded_copies(YTDLP, self.storage, None)
        self.assertEqual(find_installed_copies(YTDLP, self.storage), [])

    def test_only_abandoned_staging_folders_are_removed(self):
        tool_dir = self.storage / "deno"
        abandoned = tool_dir / (tools_manager.STAGING_PREFIX + "old")
        running = tool_dir / (tools_manager.STAGING_PREFIX + "now")
        abandoned.mkdir(parents=True)
        running.mkdir()
        two_hours_ago = time.time() - 7200
        os.utime(abandoned, (two_hours_ago, two_hours_ago))
        remove_superseded_copies(DENO, self.storage, None)
        self.assertFalse(abandoned.exists())
        self.assertTrue(running.exists())

    def test_resolution_order_local_then_managed_then_path(self):
        managed = self.add_copy(DENO, "2.9.8")
        local_dir = Path(self.temp.name) / "app"
        local_dir.mkdir()
        with mock.patch("shutil.which", return_value="C:/path/deno.exe"):
            self.assertEqual(resolve_tool(DENO, [str(local_dir)], self.storage).path, managed)
            (local_dir / "deno.exe").write_bytes(FAKE_EXE)
            local = resolve_tool(DENO, [str(local_dir)], self.storage)
            self.assertEqual((local.path, local.source), (str(local_dir / "deno.exe"), "local"))
            on_path = resolve_tool(FFMPEG, [], self.storage)
            self.assertEqual((on_path.path, on_path.source), ("C:/path/deno.exe", "path"))
        with mock.patch("shutil.which", return_value=None):
            self.assertIsNone(resolve_tool(FFMPEG, [], self.storage))

    def test_path_lookup_accepts_only_absolute_exe(self):
        for found in ("C:/tools/ffmpeg.cmd", "C:/tools/ffmpeg.bat", "ffmpeg.exe"):
            with mock.patch("shutil.which", return_value=found):
                self.assertIsNone(resolve_tool(FFMPEG, [], self.storage))
        with mock.patch("shutil.which", return_value="C:/tools/ffmpeg.exe"):
            self.assertIsNone(resolve_tool(FFMPEG, [], self.storage, allow_path=False))

    def test_legacy_ytdlp_folder_is_removed(self):
        legacy = self.storage.parent / "yt-dlp" / "2026.10.26"
        legacy.mkdir(parents=True)
        (legacy / "yt-dlp.exe").write_bytes(FAKE_EXE)
        remove_legacy_copies(self.storage)
        self.assertFalse(legacy.parent.exists())


class CheckIntervalTests(StorageTestCase):
    def test_ytdlp_is_checked_at_each_launch(self):
        record_check(YTDLP, self.storage, now=1000)
        self.assertTrue(is_check_due(YTDLP, self.storage, now=1001))

    def test_other_tools_are_checked_every_30_days(self):
        self.assertTrue(is_check_due(DENO, self.storage, now=1000))
        record_check(DENO, self.storage, now=1000)
        self.assertFalse(is_check_due(DENO, self.storage, now=1000 + 29 * 86400))
        self.assertTrue(is_check_due(DENO, self.storage, now=1000 + 30 * 86400))
        self.assertTrue(is_check_due(FFMPEG, self.storage, now=1000))

    def test_corrupted_state_means_check_due(self):
        self.storage.mkdir(parents=True)
        (self.storage / tools_manager.STATE_NAME).write_text("{not json")
        self.assertTrue(is_check_due(DENO, self.storage, now=1000))
        for value in ("NaN", "Infinity", '"yesterday"'):
            (self.storage / tools_manager.STATE_NAME).write_text(f'{{"deno": {{"last_check": {value}}}}}')
            self.assertTrue(is_check_due(DENO, self.storage, now=1000), value)


class InstallReleaseTests(StorageTestCase):
    def setUp(self):
        super().setUp()
        for patcher in (
            mock.patch("shutil.disk_usage", return_value=mock.Mock(free=10 ** 12)),
            mock.patch.object(tools_manager, "RETRY_DELAY", 0),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def install(self, spec, version, tag, asset, checksums, reported=None, **kwargs):
        release = ReleaseInfo.for_tag(spec, tag, version)
        responses = {release.checksums_url: checksums, release.asset_url: asset}
        with fake_github(responses), mock.patch.object(
            tools_manager, "run_version_command", return_value=reported or version
        ) as runner:
            try:
                return install_release(spec, release, self.storage, **kwargs)
            finally:
                self.runner = runner

    def test_installs_verified_ytdlp(self):
        progress = []
        copy = self.install(YTDLP, "2026.10.26", "2026.10.26", YTDLP_ZIP,
                            YTDLP_SUMS,
                            progress=lambda done, total: progress.append((done, total)))
        self.assertEqual(Path(copy.path).read_bytes(), FAKE_EXE)
        self.assertEqual([c.version for c in find_installed_copies(YTDLP, self.storage)], ["2026.10.26"])
        self.assertEqual(list(Path(copy.path).parent.glob("*.part")), [])
        self.assertEqual(progress[-1], (len(YTDLP_ZIP), len(YTDLP_ZIP)))

    def test_checksum_mismatch_never_runs_the_file(self):
        with self.assertRaises(ChecksumMismatch):
            self.install(YTDLP, "2026.10.26", "2026.10.26", b"tampered",
                         YTDLP_SUMS)
        self.runner.assert_not_called()
        self.assertEqual(find_installed_copies(YTDLP, self.storage), [])
        self.assertEqual([p for p in self.storage.rglob("*") if p.is_file()], [])

    def test_missing_checksum(self):
        with self.assertRaises(UpdateError):
            self.install(YTDLP, "2026.10.26", "2026.10.26", YTDLP_ZIP, b"")

    def test_interrupted_download_leaves_nothing_usable(self):
        release_asset = FakeResponse(FAKE_EXE * 1000, fail_after=100)
        with self.assertRaises(UpdateError):
            self.install(YTDLP, "2026.10.26", "2026.10.26", release_asset,
                         classic_checksums(FAKE_EXE * 1000, YTDLP.asset_name))
        self.assertEqual(find_installed_copies(YTDLP, self.storage), [])
        self.assertEqual([p for p in self.storage.rglob("*") if p.is_file()], [])

    def test_download_size_is_capped(self):
        big = b"x" * 2048
        spec = replace(YTDLP, max_download_bytes=1024)
        with self.assertRaises(UpdateError):
            self.install(spec, "2026.10.26", "2026.10.26", big, classic_checksums(big, YTDLP.asset_name))
        self.assertEqual([p for p in self.storage.rglob("*") if p.is_file()], [])

    def test_copy_that_does_not_start_is_removed(self):
        with self.assertRaises(UpdateError):
            self.install(YTDLP, "2026.10.26", "2026.10.26", YTDLP_ZIP,
                         YTDLP_SUMS, reported="none")
        self.assertFalse((self.storage / "yt-dlp" / "2026.10.26").exists())

    def test_not_enough_disk_space(self):
        with mock.patch("shutil.disk_usage", return_value=mock.Mock(free=10)):
            with self.assertRaises(UpdateError):
                self.install(YTDLP, "2026.10.26", "2026.10.26", YTDLP_ZIP,
                             YTDLP_SUMS)

    def test_locked_file_is_retried(self):
        real_replace = os.replace
        attempts = []

        def flaky_replace(source, target):
            attempts.append(target)
            if len(attempts) < 3:
                raise PermissionError("locked by antivirus")
            return real_replace(source, target)

        with mock.patch("os.replace", side_effect=flaky_replace):
            copy = self.install(YTDLP, "2026.10.26", "2026.10.26", YTDLP_ZIP,
                                YTDLP_SUMS)
        self.assertTrue(Path(copy.path).is_file())
        self.assertGreaterEqual(len(attempts), 3)

    def test_slow_first_start_is_retried(self):
        release = ReleaseInfo.for_tag(YTDLP, "2026.10.26", "2026.10.26")
        responses = {release.checksums_url: YTDLP_SUMS,
                     release.asset_url: YTDLP_ZIP}
        with fake_github(responses), mock.patch.object(
            tools_manager, "run_version_command", side_effect=[None, None, "2026.10.26"]
        ):
            copy = install_release(YTDLP, release, self.storage)
        self.assertEqual(copy.version, "2026.10.26")

    def test_install_happens_in_a_private_staging_folder(self):
        seen = []

        def record_folder(spec, path):
            seen.append(Path(path).parent.name)
            return "2026.10.26"

        release = ReleaseInfo.for_tag(YTDLP, "2026.10.26", "2026.10.26")
        responses = {release.checksums_url: YTDLP_SUMS,
                     release.asset_url: YTDLP_ZIP}
        with fake_github(responses), mock.patch.object(tools_manager, "run_version_command",
                                                       side_effect=record_folder):
            install_release(YTDLP, release, self.storage)
        self.assertTrue(seen[0].startswith(tools_manager.STAGING_PREFIX))
        self.assertEqual(sorted(p.name for p in (self.storage / "yt-dlp").iterdir()), ["2026.10.26"])

    def test_other_window_finishing_first_is_reused(self):
        release = ReleaseInfo.for_tag(YTDLP, "2026.10.26", "2026.10.26")
        responses = {release.checksums_url: YTDLP_SUMS,
                     release.asset_url: YTDLP_ZIP}

        def other_window_installs(spec, path):
            # While this install checks its copy, another StreamDL window
            # completes the same version.
            self.add_copy(YTDLP, "2026.10.26")
            return "2026.10.26"

        with fake_github(responses), mock.patch.object(tools_manager, "run_version_command",
                                                       side_effect=other_window_installs):
            copy = install_release(YTDLP, release, self.storage)
        self.assertEqual(copy.path, str(self.storage / "yt-dlp" / "2026.10.26" / "yt-dlp.exe"))
        self.assertEqual(sorted(p.name for p in (self.storage / "yt-dlp").iterdir()), ["2026.10.26"])

    def test_ytdlp_folder_build_keeps_its_internal_folder(self):
        archive = make_zip({
            "yt-dlp.exe": FAKE_EXE,
            "_internal/python314.dll": b"python",
            "_internal/certifi/cacert.pem": b"certificates",
            "README.txt": b"doc",
        })
        copy = self.install(YTDLP, "2026.10.26", "2026.10.26", archive,
                            classic_checksums(archive, YTDLP.asset_name))
        folder = Path(copy.path).parent
        self.assertEqual(
            sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()),
            ["_internal/certifi/cacert.pem", "_internal/python314.dll",
             tools_manager.MARKER_NAME, "yt-dlp.exe"],
        )

    def test_ytdlp_folder_build_replaces_the_single_file_copy(self):
        folder = self.storage / "yt-dlp" / "2026.10.26"
        folder.mkdir(parents=True)
        (folder / "yt-dlp.exe").write_bytes(b"single file")
        (folder / tools_manager.MARKER_NAME).write_text(json.dumps({"version": "2026.10.26"}))
        copy = self.install(YTDLP, "2026.10.26", "2026.10.26", YTDLP_ZIP, YTDLP_SUMS)
        self.assertEqual(copy.path, str(folder / "yt-dlp.exe"))
        self.assertTrue((folder / "_internal" / "python314.dll").is_file())
        self.assertEqual([c.path for c in find_installed_copies(YTDLP, self.storage)], [copy.path])

    def test_ytdlp_zip_paths_stay_inside_the_tool_folder(self):
        for member in ("_internal/../../evil.dll", "_internal//evil.dll", "_internal/C:/evil.dll",
                       "_internal/NUL.dll", "_internal/sub/con"):
            with self.subTest(member=member):
                archive = make_zip({"yt-dlp.exe": FAKE_EXE, "_internal/ok.dll": b"ok", member: b"x"})
                with self.assertRaises(UpdateError):
                    self.install(YTDLP, "2026.10.26", "2026.10.26", archive,
                                 classic_checksums(archive, YTDLP.asset_name))
                self.runner.assert_not_called()
                self.assertEqual(find_installed_copies(YTDLP, self.storage), [])
        self.assertEqual(list(self.storage.parent.rglob("evil.dll")), [])

    def test_ytdlp_zip_without_its_internal_folder_is_refused(self):
        archive = make_zip({"yt-dlp.exe": FAKE_EXE})
        with self.assertRaises(UpdateError):
            self.install(YTDLP, "2026.10.26", "2026.10.26", archive,
                         classic_checksums(archive, YTDLP.asset_name))
        self.runner.assert_not_called()
        self.assertEqual(find_installed_copies(YTDLP, self.storage), [])

    def test_single_file_ytdlp_for_full_builds(self):
        copy = self.install(YTDLP_SINGLE_FILE, "2026.10.26", "2026.10.26", FAKE_EXE,
                            classic_checksums(FAKE_EXE, "yt-dlp.exe"))
        folder = Path(copy.path).parent
        self.assertEqual(sorted(p.name for p in folder.iterdir()), [tools_manager.MARKER_NAME, "yt-dlp.exe"])

    def test_deno_zip_extracts_only_deno(self):
        archive = make_zip({"deno.exe": FAKE_EXE, "README.md": b"doc", "../evil.exe": b"x"})
        sha256sum = DENO_SHA256SUM_TEMPLATE.format(digest=hashlib.sha256(archive).hexdigest().upper())
        copy = self.install(DENO, "2.9.8", "v2.9.8", archive, sha256sum.encode())
        folder = Path(copy.path).parent
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["deno.exe", tools_manager.MARKER_NAME])
        self.assertFalse((self.storage / "deno" / "evil.exe").exists())
        self.assertFalse((self.storage / "evil.exe").exists())

    def test_ffmpeg_zip_extracts_ffmpeg_files_only(self):
        root = "ffmpeg-master-latest-win64-gpl-shared"
        archive = make_zip({
            f"{root}/bin/ffmpeg.exe": FAKE_EXE,
            f"{root}/bin/ffprobe.exe": b"probe",
            f"{root}/bin/avcodec-62.dll": b"dll",
            f"{root}/bin/ffplay.exe": b"player",
            f"{root}/bin/version.dll": b"named like a Windows DLL",
            f"{root}/bin/../../evil.dll": b"x",
            f"{root}/doc/readme.txt": b"doc",
            "C:/Windows/evil.dll": b"x",
        })
        copy = self.install(FFMPEG, "2026.10.30.1913", "latest", archive,
                            classic_checksums(archive, FFMPEG.asset_name), reported="ffmpeg")
        folder = Path(copy.path).parent
        self.assertEqual(sorted(p.name for p in folder.iterdir()),
                         ["avcodec-62.dll", "ffmpeg.exe", "ffprobe.exe", tools_manager.MARKER_NAME])

    def test_github_digest_must_match_the_published_checksum(self):
        release = replace(ReleaseInfo.for_tag(YTDLP, "2026.10.26", "2026.10.26"),
                          published_digest="f" * 64)
        responses = {release.checksums_url: YTDLP_SUMS,
                     release.asset_url: YTDLP_ZIP}
        with fake_github(responses), mock.patch.object(tools_manager, "run_version_command") as runner:
            with self.assertRaises(ChecksumMismatch):
                install_release(YTDLP, release, self.storage)
        runner.assert_not_called()
        self.assertEqual(find_installed_copies(YTDLP, self.storage), [])

    def test_oversized_checksum_file_is_rejected(self):
        huge = b"0" * (tools_manager.METADATA_MAX_BYTES + 1)
        with self.assertRaises(UpdateError):
            self.install(YTDLP, "2026.10.26", "2026.10.26", YTDLP_ZIP, huge)

    def test_zip_without_the_executable(self):
        archive = make_zip({"README.md": b"doc"})
        with self.assertRaises(UpdateError):
            self.install(DENO, "2.9.8", "v2.9.8", archive, classic_checksums(archive, DENO.asset_name))
        self.assertEqual(find_installed_copies(DENO, self.storage), [])

    def test_zip_bomb_is_rejected(self):
        archive = make_zip({"deno.exe": b"\0" * 4096})
        spec = replace(DENO, max_unpacked_bytes=1024)
        with self.assertRaises(UpdateError):
            self.install(spec, "2.9.8", "v2.9.8", archive, classic_checksums(archive, DENO.asset_name))
        self.assertEqual(find_installed_copies(DENO, self.storage), [])

    def test_symlink_member_is_rejected(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zip_file:
            info = zipfile.ZipInfo("deno.exe")
            info.external_attr = 0o120777 << 16
            zip_file.writestr(info, "C:/Windows/System32/cmd.exe")
        archive = buffer.getvalue()
        with self.assertRaises(UpdateError):
            self.install(DENO, "2.9.8", "v2.9.8", archive, classic_checksums(archive, DENO.asset_name))


if __name__ == "__main__":
    unittest.main()
