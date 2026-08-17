import os
import tempfile
import unittest

from auth_support import (
    AuthErrorDetector,
    AuthErrorType,
    CookiePreferenceStore,
    CookieSource,
    create_youtube_only_cookie_copy,
    delete_temporary_cookie_file,
    sanitize_technical_text,
    validate_netscape_cookie_file,
)


class AuthErrorDetectorTests(unittest.TestCase):
    def detect(self, text, source=None):
        return AuthErrorDetector.detect(1, stderr_text=text, cookie_source=source)

    def test_age_restriction(self):
        result = self.detect("ERROR: Sign in to confirm your age")
        self.assertEqual(result.error_type, AuthErrorType.AGE_RESTRICTED)

    def test_login_required(self):
        result = self.detect("ERROR: Login required to access this members-only content")
        self.assertEqual(result.error_type, AuthErrorType.LOGIN_REQUIRED)

    def test_cookies_required(self):
        result = self.detect("ERROR: Use --cookies-from-browser or --cookies for the authentication")
        self.assertEqual(result.error_type, AuthErrorType.COOKIES_REQUIRED)

    def test_chromium_copy_failure(self):
        result = self.detect("ERROR: Could not copy Chrome cookie database. See issue 7271")
        self.assertEqual(result.error_type, AuthErrorType.COOKIE_EXTRACTION_FAILED)

    def test_decryption_failure(self):
        result = self.detect("WARNING: failed to decrypt with DPAPI")
        self.assertEqual(result.error_type, AuthErrorType.COOKIE_DECRYPTION_FAILED)

    def test_cookie_file_rejected_by_site(self):
        result = self.detect(
            "ERROR: Sign in to confirm you're not a bot. Use --cookies for the authentication",
            CookieSource.file_source(r"C:\temp\cookies.txt"),
        )
        self.assertEqual(result.error_type, AuthErrorType.COOKIES_EXPIRED_OR_INVALID)

    def test_non_auth_error_is_ignored(self):
        self.assertIsNone(self.detect("ERROR: Unsupported URL"))

    def test_cookie_word_alone_is_not_an_auth_error(self):
        self.assertIsNone(self.detect("[Cookies] Extracted 12 cookies from firefox\nERROR: No video formats found"))

    def test_unknown_auth_error(self):
        result = self.detect("ERROR: Authentication challenge could not be completed")
        self.assertEqual(result.error_type, AuthErrorType.UNKNOWN_AUTH_ERROR)

    def test_sensitive_header_is_redacted(self):
        text = sanitize_technical_text("Authorization: Bearer secret-value\nERROR: Login required")
        self.assertNotIn("secret-value", text)
        self.assertIn("Login required", text)


class CookieFileValidationTests(unittest.TestCase):
    def test_valid_netscape_file(self):
        handle, path = tempfile.mkstemp(suffix=".txt")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as output:
                output.write("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tvalue\n")
            valid, _ = validate_netscape_cookie_file(path)
            self.assertTrue(valid)
        finally:
            os.remove(path)

    def test_invalid_file(self):
        handle, path = tempfile.mkstemp(suffix=".txt")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as output:
                output.write("not a Netscape file")
            valid, _ = validate_netscape_cookie_file(path)
            self.assertFalse(valid)
        finally:
            os.remove(path)

    def test_youtube_only_temporary_copy_excludes_other_sites(self):
        handle, source_path = tempfile.mkstemp(suffix=".txt")
        temporary_path = None
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as output:
                output.write(
                    "# Netscape HTTP Cookie File\n"
                    ".youtube.com\tTRUE\t/\tTRUE\t0\tSID\tyoutube-secret\n"
                    "#HttpOnly_.m.youtube.com\tTRUE\t/\tTRUE\t0\tHSID\tyoutube-http-only\n"
                    ".example.com\tTRUE\t/\tTRUE\t0\tSID\tother-secret\n"
            )
            temporary_path, count = create_youtube_only_cookie_copy(source_path)
            with open(temporary_path, encoding="utf-8") as temporary_file:
                content = temporary_file.read()
            self.assertEqual(count, 2)
            self.assertIn("youtube-secret", content)
            self.assertIn("youtube-http-only", content)
            self.assertNotIn("example.com", content)
            self.assertNotIn("other-secret", content)
            self.assertTrue(delete_temporary_cookie_file(temporary_path))
            self.assertFalse(os.path.exists(temporary_path))
            temporary_path = None
        finally:
            if temporary_path:
                delete_temporary_cookie_file(temporary_path)
            os.remove(source_path)


class CookiePreferenceTests(unittest.TestCase):
    def test_only_the_path_is_persisted(self):
        with tempfile.TemporaryDirectory() as local_app_data:
            original = os.environ.get("LOCALAPPDATA")
            os.environ["LOCALAPPDATA"] = local_app_data
            try:
                store = CookiePreferenceStore("StreamDL-test")
                cookie_path = r"C:\Utilisateurs\Alice\cookies.txt"
                store.remember_cookie_file_path(cookie_path)
                self.assertEqual(store.get_cookie_file_path(), cookie_path)
                self.assertIn("cookies_file_path", store.path.read_text(encoding="utf-8"))
                self.assertNotIn("SID", store.path.read_text(encoding="utf-8"))
                store.forget_cookie_file_path()
                self.assertIsNone(store.get_cookie_file_path())
            finally:
                if original is None:
                    os.environ.pop("LOCALAPPDATA", None)
                else:
                    os.environ["LOCALAPPDATA"] = original

if __name__ == "__main__":
    unittest.main()
