import hashlib
import io
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import ytdlp_updater
from ytdlp_updater import (
    ReleaseInfo,
    UpdateError,
    YtDlpCopy,
    fetch_latest_release,
    find_best_local_copy,
    find_installed_copies,
    install_release,
    is_newer_release,
    parse_checksums,
    parse_version,
    remove_superseded_copies,
)


FAKE_EXE = b"MZ fake yt-dlp executable"


class FakeResponse(io.BytesIO):
    def __init__(self, data=b"", url=""):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


def fake_github(responses):
    """Patch ytdlp_updater._open_url with a {url: bytes | Exception} table."""
    def open_url(url, timeout):
        value = responses[url]
        if isinstance(value, Exception):
            raise value
        if isinstance(value, FakeResponse):
            return value
        return FakeResponse(value, url)
    return mock.patch.object(ytdlp_updater, "_open_url", side_effect=open_url)


def checksums_for(data, name="yt-dlp.exe"):
    digest = hashlib.sha256(data).hexdigest()
    return (
        f"{'0' * 64}  yt-dlp_x86.exe\n"
        f"{digest}  {name}\n"
        f"{'1' * 64}  yt-dlp_linux\n"
    ).encode()


class VersionTests(unittest.TestCase):
    def test_stable_and_nightly_versions(self):
        self.assertEqual(parse_version("2026.10.26"), (2026, 10, 26))
        self.assertEqual(parse_version(" 2026.10.26.232920\n"), (2026, 10, 26, 232920))
        self.assertLess(parse_version("2026.9.30"), parse_version("2026.10.1"))

    def test_invalid_versions(self):
        for text in (None, "", "latest", "v2026.10.26", "2026.10"):
            self.assertIsNone(parse_version(text))

    def test_newer_release(self):
        release = ReleaseInfo.for_version("2026.10.26")
        self.assertTrue(is_newer_release(release, None))
        self.assertTrue(is_newer_release(release, YtDlpCopy("a", "2026.10.20")))
        self.assertTrue(is_newer_release(release, YtDlpCopy("a", None)))
        self.assertFalse(is_newer_release(release, YtDlpCopy("a", "2026.10.26")))


class ChecksumTests(unittest.TestCase):
    def test_finds_exact_asset(self):
        text = checksums_for(FAKE_EXE).decode()
        self.assertEqual(parse_checksums(text, "yt-dlp.exe"), hashlib.sha256(FAKE_EXE).hexdigest())

    def test_missing_or_malformed_digest(self):
        self.assertIsNone(parse_checksums("abc  yt-dlp.exe\n", "yt-dlp.exe"))
        self.assertIsNone(parse_checksums(f"{'0' * 64}  yt-dlp_x86.exe\n", "yt-dlp.exe"))


class FetchLatestReleaseTests(unittest.TestCase):
    def test_reads_api(self):
        api = b'{"tag_name": "2026.10.26", "assets": [{"name": "yt-dlp.exe"}, {"name": "SHA2-256SUMS"}]}'
        with fake_github({ytdlp_updater.RELEASES_API_URL: api}):
            release = fetch_latest_release()
        self.assertEqual(release.version, "2026.10.26")
        self.assertTrue(release.exe_url.endswith("/download/2026.10.26/yt-dlp.exe"))

    def test_release_without_assets_yet(self):
        api = b'{"tag_name": "2026.10.26", "assets": []}'
        with fake_github({ytdlp_updater.RELEASES_API_URL: api}):
            with self.assertRaises(UpdateError):
                fetch_latest_release()

    def test_rate_limited_api_falls_back_to_releases_page(self):
        rate_limited = urllib.error.HTTPError(ytdlp_updater.RELEASES_API_URL, 403, "rate limit", {}, None)
        page = FakeResponse(b"<html>", "https://github.com/yt-dlp/yt-dlp/releases/tag/2026.10.26")
        with fake_github({
            ytdlp_updater.RELEASES_API_URL: rate_limited,
            ytdlp_updater.RELEASES_LATEST_PAGE_URL: page,
        }):
            release = fetch_latest_release()
        self.assertEqual(release.version, "2026.10.26")


class StorageTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.storage = Path(self.temp.name) / "yt-dlp"

    def tearDown(self):
        self.temp.cleanup()

    def add_copy(self, version, with_exe=True):
        folder = self.storage / version
        folder.mkdir(parents=True)
        if with_exe:
            (folder / "yt-dlp.exe").write_bytes(FAKE_EXE)
        return str(folder / "yt-dlp.exe")


class StorageTests(StorageTestCase):
    def test_lists_complete_copies_newest_first(self):
        self.add_copy("2026.9.1")
        self.add_copy("2026.10.26")
        self.add_copy("2026.11.1", with_exe=False)
        self.add_copy("notes")
        versions = [copy.version for copy in find_installed_copies(self.storage)]
        self.assertEqual(versions, ["2026.10.26", "2026.9.1"])

    def test_missing_storage(self):
        self.assertEqual(find_installed_copies(self.storage), [])

    def test_cleanup_keeps_selected_copy_and_unknown_folders(self):
        old = self.add_copy("2026.9.1")
        keep = self.add_copy("2026.10.26")
        self.add_copy("notes")
        remove_superseded_copies(self.storage, keep)
        self.assertFalse(Path(old).exists())
        self.assertTrue(Path(keep).exists())
        self.assertTrue((self.storage / "notes").exists())

    def test_prefers_newer_working_managed_copy(self):
        managed = self.add_copy("2026.10.26")
        with mock.patch.object(ytdlp_updater, "read_exe_version", side_effect=lambda path: {
            "bundled.exe": "2026.10.1",
            managed: "2026.10.26",
        }[path]), mock.patch("os.path.isfile", return_value=True):
            best = find_best_local_copy("bundled.exe", self.storage)
        self.assertEqual(best.path, managed)

    def test_broken_managed_copy_is_discarded(self):
        managed = self.add_copy("2026.10.26")
        with mock.patch.object(ytdlp_updater, "read_exe_version", side_effect=lambda path: {
            "bundled.exe": "2026.10.1",
            managed: None,
        }[path]), mock.patch("os.path.isfile", return_value=True):
            best = find_best_local_copy("bundled.exe", self.storage)
        self.assertEqual(best.path, "bundled.exe")
        self.assertFalse(Path(managed).parent.exists())

    def test_newer_bundled_copy_wins(self):
        self.add_copy("2026.9.1")
        with mock.patch.object(ytdlp_updater, "read_exe_version", return_value="2026.10.26"), \
                mock.patch("os.path.isfile", return_value=True):
            best = find_best_local_copy("bundled.exe", self.storage)
        self.assertEqual((best.path, best.version), ("bundled.exe", "2026.10.26"))


class InstallReleaseTests(StorageTestCase):
    release = ReleaseInfo.for_version("2026.10.26")

    def github(self, exe_data, checksums=None):
        return fake_github({
            self.release.checksums_url: checksums if checksums is not None else checksums_for(FAKE_EXE),
            self.release.exe_url: exe_data,
        })

    def test_installs_verified_copy(self):
        with self.github(FAKE_EXE), \
                mock.patch.object(ytdlp_updater, "read_exe_version", return_value="2026.10.26"):
            copy = install_release(self.release, self.storage)
        self.assertEqual(Path(copy.path).read_bytes(), FAKE_EXE)
        self.assertEqual(Path(copy.path).parent.name, "2026.10.26")
        self.assertEqual(list(Path(copy.path).parent.glob("*.part")), [])

    def test_rejects_checksum_mismatch(self):
        with self.github(b"tampered"):
            with self.assertRaises(UpdateError):
                install_release(self.release, self.storage)
        self.assertEqual(find_installed_copies(self.storage), [])
        self.assertEqual(list(self.storage.rglob("*")), [self.storage / "2026.10.26"])

    def test_rejects_missing_checksum(self):
        with self.github(FAKE_EXE, checksums=b""):
            with self.assertRaises(UpdateError):
                install_release(self.release, self.storage)

    def test_rejects_copy_that_does_not_start(self):
        with self.github(FAKE_EXE), \
                mock.patch.object(ytdlp_updater, "read_exe_version", return_value=None):
            with self.assertRaises(UpdateError):
                install_release(self.release, self.storage)
        self.assertFalse((self.storage / "2026.10.26").exists())


if __name__ == "__main__":
    unittest.main()
