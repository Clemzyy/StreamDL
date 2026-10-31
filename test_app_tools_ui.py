"""First-launch tool behaviour of the real App, in a hidden Tk window with a fake GitHub.

Run: py -3.13 -m unittest -v test_app_tools_ui.py
"""
import glob
import importlib.machinery
import importlib.util
import json
import re
import tempfile
import threading
import time
import tkinter as tk
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from tools_manager import (
    DENO,
    FFMPEG,
    MARKER_NAME,
    YTDLP,
    ReleaseInfo,
    ToolCopy,
    is_check_due,
    record_check,
)


PROJECT_DIR = Path(__file__).resolve().parent
RELEASES = {
    "yt-dlp": ReleaseInfo.for_tag(YTDLP, "2026.10.26", "2026.10.26"),
    "deno": ReleaseInfo.for_tag(DENO, "v2.9.8", "2.9.8"),
    "ffmpeg": ReleaseInfo.for_tag(FFMPEG, "latest", "2026.10.30.1913"),
}


def load_app_module():
    def source_version(path):
        match = re.search(r"_v(\d+)\.(\d+)", path)
        return (int(match.group(1)), int(match.group(2))) if match else (0, 0)

    source = max(glob.glob(str(PROJECT_DIR / "telechargeur_youtube_v*.pyw")), key=source_version)
    loader = importlib.machinery.SourceFileLoader("streamdl_app", source)
    spec = importlib.util.spec_from_loader("streamdl_app", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


APP = load_app_module()


def add_managed_copy(storage, spec, version):
    folder = storage / spec.name / version
    folder.mkdir(parents=True)
    (folder / spec.exe_name).write_bytes(b"MZ")
    (folder / MARKER_NAME).write_text(json.dumps({"version": version}))
    return ToolCopy(str(folder / spec.exe_name), version, "managed")


class AppToolsTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.storage = Path(self.temp.name) / "StreamDL" / "tools"
        empty_app_dir = Path(self.temp.name) / "app"
        empty_app_dir.mkdir()
        self.dialogs = []
        self.tk_errors = []
        self.installed = []
        self.install_gate = {}

        for target, value in (
            ("default_storage_dir", lambda: self.storage),
            ("get_local_tool_dirs", lambda: [str(empty_app_dir)]),
        ):
            patcher = mock.patch.object(APP, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for patcher in (
            mock.patch("shutil.which", return_value=None),
            mock.patch.object(APP.messagebox, "showerror", lambda *a, **k: self.dialogs.append(a)),
            mock.patch.object(APP.messagebox, "showwarning", lambda *a, **k: self.dialogs.append(a)),
            mock.patch.object(APP.messagebox, "showinfo", lambda *a, **k: self.dialogs.append(a)),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

        self.fetch = mock.patch.object(APP, "fetch_latest_release", side_effect=self.fake_fetch)
        self.fetch_mock = self.fetch.start()
        self.addCleanup(self.fetch.stop)
        self.install = mock.patch.object(APP, "install_release", side_effect=self.fake_install)
        self.install_mock = self.install.start()
        self.addCleanup(self.install.stop)
        self.offline = False

    def fake_fetch(self, spec, timeout=15):
        if self.offline:
            raise urllib.error.URLError("offline")
        return RELEASES[spec.name]

    def fake_install(self, spec, release, storage, progress=None):
        gate = self.install_gate.get(spec.name)
        if gate:
            gate.wait(10)
        if progress:
            progress(50 * 1024 * 1024, 100 * 1024 * 1024)
            progress(100 * 1024 * 1024, 100 * 1024 * 1024)
        self.installed.append(spec.name)
        return add_managed_copy(storage, spec, release.version)

    def start_app(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.report_callback_exception = (
            lambda exc, value, tb: self.tk_errors.append(f"{exc.__name__}: {value}")
        )
        self.app = APP.App(self.root)
        self.addCleanup(self.close_quietly, self.app)

    def close_quietly(self, app):
        try:
            app.on_application_close()
        except tk.TclError:
            pass  # already closed by the test

    def pump_until(self, condition, timeout=10.0):
        # A real mainloop is required for root.after() calls made from threads.
        deadline = time.monotonic() + timeout

        def check():
            if condition() or time.monotonic() > deadline:
                self.root.quit()
            else:
                self.root.after(20, check)

        self.root.after(20, check)
        self.root.mainloop()
        self.assertTrue(condition(), "condition not reached in time")

    def worker_done(self):
        return not self.app.tools_worker_running and self.app.tools_status_var.get() != ""

    def wait_for_worker(self):
        self.pump_until(lambda: self.fetch_mock.called or self.install_mock.called)
        self.pump_until(self.worker_done)

    def state(self, button):
        return str(button["state"])


class FirstLaunchTests(AppToolsTestCase):
    def test_buttons_disabled_until_tools_installed(self):
        self.start_app()
        self.assertEqual(self.state(self.app.choose_format_btn), "disabled")
        self.assertIn("yt-dlp : à installer", self.app.tools_status_var.get())
        self.wait_for_worker()
        self.assertEqual(self.installed, ["yt-dlp", "deno", "ffmpeg"])
        self.assertEqual(self.state(self.app.choose_format_btn), "normal")
        self.assertEqual(self.app.tools_status_var.get(), "yt-dlp 2026.10.26 · Deno 2.9.8 · ffmpeg ✓")
        log = self.app.log_box.get("1.0", "end")
        self.assertIn("n'a lieu qu'une fois", log)
        self.assertIn("Deno 2.9.8 installé (empreinte SHA-256 vérifiée).", log)
        self.assertIn("ffmpeg installé (empreinte SHA-256 vérifiée).", log)
        self.assertEqual(self.tk_errors, [])

    def test_offline_first_launch_offers_retry(self):
        self.offline = True
        self.start_app()
        self.wait_for_worker()
        self.assertEqual(self.state(self.app.choose_format_btn), "disabled")
        self.assertEqual(self.state(self.app.start_btn), "disabled")
        self.assertEqual(self.app.tools_retry_btn.winfo_manager(), "pack")
        self.assertIn("Réessayer", self.app.status_label["text"])
        self.assertIn("connexion à GitHub impossible", self.app.log_box.get("1.0", "end"))
        self.assertEqual(self.dialogs, [])
        self.assertEqual(self.tk_errors, [])

        self.offline = False
        self.app.tools_retry_btn.invoke()
        self.pump_until(lambda: self.installed == ["yt-dlp", "deno", "ffmpeg"])
        self.pump_until(self.worker_done)
        self.assertEqual(self.state(self.app.choose_format_btn), "normal")
        self.assertEqual(self.app.tools_retry_btn.winfo_manager(), "")
        self.assertEqual(self.tk_errors, [])

    def test_launch_button_waits_for_ffmpeg(self):
        add_managed_copy(self.storage, YTDLP, "2026.10.26")
        add_managed_copy(self.storage, DENO, "2.9.8")
        record_check(DENO, self.storage)
        self.install_gate["ffmpeg"] = threading.Event()
        self.start_app()
        self.assertEqual(self.state(self.app.choose_format_btn), "normal")

        # A format is chosen while ffmpeg is still downloading.
        self.app.enable_start_button()
        self.assertEqual(self.state(self.app.start_btn), "disabled")

        self.pump_until(lambda: self.app.tools_worker_running)
        self.assertEqual(self.state(self.app.start_btn), "disabled")
        self.install_gate["ffmpeg"].set()
        self.pump_until(lambda: self.installed == ["ffmpeg"])
        self.pump_until(self.worker_done)
        self.assertEqual(self.state(self.app.start_btn), "normal")
        self.assertEqual(self.tk_errors, [])

    def test_running_step_is_not_unlocked_by_a_new_tool(self):
        add_managed_copy(self.storage, YTDLP, "2026.10.26")
        add_managed_copy(self.storage, DENO, "2.9.8")
        record_check(DENO, self.storage)
        self.install_gate["ffmpeg"] = threading.Event()
        self.start_app()
        self.app.enable_start_button()
        # A format list is being read when ffmpeg finishes installing.
        self.app.disable_action_buttons()
        self.install_gate["ffmpeg"].set()
        self.pump_until(lambda: self.installed == ["ffmpeg"])
        self.pump_until(self.worker_done)
        self.assertEqual(self.state(self.app.choose_format_btn), "disabled")
        self.assertEqual(self.state(self.app.start_btn), "disabled")

    def test_replaced_ffmpeg_build_is_downloaded_again_once(self):
        add_managed_copy(self.storage, YTDLP, "2026.10.26")
        add_managed_copy(self.storage, DENO, "2.9.8")
        record_check(DENO, self.storage)
        attempts = []

        def rolling_build(spec, release, storage, progress=None):
            attempts.append(spec.name)
            if len(attempts) == 1:
                raise APP.ChecksumMismatch("build remplacé pendant le téléchargement")
            return self.fake_install(spec, release, storage, progress)

        self.install_mock.side_effect = rolling_build
        self.start_app()
        self.wait_for_worker()
        self.assertEqual(attempts, ["ffmpeg", "ffmpeg"])
        self.assertEqual([c.args[0].name for c in self.fetch_mock.call_args_list].count("ffmpeg"), 2)
        self.assertIsNotNone(self.app.tool_path("ffmpeg"))


class LaterLaunchTests(AppToolsTestCase):
    def test_up_to_date_tools_download_nothing(self):
        for spec, version in ((YTDLP, "2026.10.26"), (DENO, "2.9.8"), (FFMPEG, "2026.10.30.1913")):
            add_managed_copy(self.storage, spec, version)
            record_check(spec, self.storage)
        self.start_app()
        self.assertEqual(self.state(self.app.choose_format_btn), "normal")
        self.wait_for_worker()
        # Only yt-dlp is checked at each launch; Deno and ffmpeg every 30 days.
        self.assertEqual([c.args[0].name for c in self.fetch_mock.call_args_list], ["yt-dlp"])
        self.assertEqual(self.installed, [])
        self.assertEqual(self.app.tools_retry_btn.winfo_manager(), "")
        self.assertEqual(self.tk_errors, [])

    def test_offline_with_tools_present_keeps_working(self):
        for spec, version in ((YTDLP, "2026.10.20"), (DENO, "2.9.8"), (FFMPEG, "2026.10.30.1913")):
            add_managed_copy(self.storage, spec, version)
            record_check(spec, self.storage)
        self.offline = True
        self.start_app()
        self.wait_for_worker()
        self.assertEqual(self.state(self.app.choose_format_btn), "normal")
        self.assertIn("yt-dlp 2026.10.20 (non vérifié)", self.app.tools_status_var.get())
        self.assertEqual(self.app.tools_retry_btn.winfo_manager(), "")
        self.assertEqual(self.tk_errors, [])

    def test_newer_ytdlp_replaces_the_installed_one(self):
        old = add_managed_copy(self.storage, YTDLP, "2026.10.20")
        for spec, version in ((DENO, "2.9.8"), (FFMPEG, "2026.10.30.1913")):
            add_managed_copy(self.storage, spec, version)
            record_check(spec, self.storage)
        self.start_app()
        self.wait_for_worker()
        self.assertEqual(self.installed, ["yt-dlp"])
        self.assertIn("2026.10.26", self.app.tool_path("yt-dlp"))
        # A download started before the update may still use the old copy.
        self.assertTrue(Path(old.path).exists())
        self.assertEqual(self.tk_errors, [])

        self.app.on_application_close()
        self.fetch_mock.reset_mock()
        self.install_mock.reset_mock()
        self.start_app()
        self.wait_for_worker()
        self.assertFalse(Path(old.path).exists())

    def test_newer_managed_ytdlp_beats_an_older_local_copy(self):
        local = Path(self.temp.name) / "app" / "yt-dlp.exe"
        local.write_bytes(b"MZ")
        managed = add_managed_copy(self.storage, YTDLP, "2026.10.26")
        for spec, version in ((DENO, "2.9.8"), (FFMPEG, "2026.10.30.1913")):
            add_managed_copy(self.storage, spec, version)
            record_check(spec, self.storage)
        with mock.patch.object(APP, "run_version_command", return_value="2026.10.20"):
            self.start_app()
            self.assertEqual(self.app.tool_path("yt-dlp"), str(local))
            self.wait_for_worker()
        self.assertEqual(self.app.tool_path("yt-dlp"), managed.path)
        self.assertEqual(self.installed, [])

    def test_failed_update_keeps_the_tool_and_retries_next_launch(self):
        add_managed_copy(self.storage, YTDLP, "2026.10.26")
        old_deno = add_managed_copy(self.storage, DENO, "2.9.7")
        add_managed_copy(self.storage, FFMPEG, "2026.10.30.1913")
        record_check(FFMPEG, self.storage)

        def deno_fails(spec, release, storage, progress=None):
            raise RuntimeError("disque plein")

        self.install_mock.side_effect = deno_fails
        self.start_app()
        self.wait_for_worker()
        self.assertEqual(self.app.tool_path("deno"), old_deno.path)
        self.assertIn("Deno 2.9.7 (mise à jour échouée)", self.app.tools_status_var.get())
        self.assertEqual(self.state(self.app.choose_format_btn), "normal")
        self.assertTrue(is_check_due(DENO, self.storage))


class AppCacheTests(unittest.TestCase):
    def test_only_other_builds_of_streamdl_are_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp) / "StreamDL" / "app"
            current, previous = cache / "aaaaaaaaaaaa", cache / "bbbbbbbbbbbb"
            current.mkdir(parents=True)
            previous.mkdir()
            with mock.patch.object(APP, "is_nuitka_build", return_value=True), \
                    mock.patch.object(APP, "get_base_dir", return_value=str(current)):
                APP.remove_old_app_caches()
            self.assertTrue(current.exists())
            self.assertFalse(previous.exists())

    def test_unexpected_location_is_left_alone(self):
        with tempfile.TemporaryDirectory() as temp:
            current, neighbour = Path(temp) / "Downloads" / "x", Path(temp) / "Downloads" / "photos"
            current.mkdir(parents=True)
            neighbour.mkdir()
            with mock.patch.object(APP, "is_nuitka_build", return_value=True), \
                    mock.patch.object(APP, "get_base_dir", return_value=str(current)):
                APP.remove_old_app_caches()
            self.assertTrue(neighbour.exists())


if __name__ == "__main__":
    unittest.main()
