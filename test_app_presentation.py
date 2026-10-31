"""Presentation of the main window: theme, blocks, conversion options, preview.

Run: py -3.13 -m unittest -v test_app_presentation.py
"""
import json
import tkinter as tk
import unittest
from tkinter import ttk
from unittest import mock

import build_exe
from test_app_ergonomics import ErgonomicsTestCase
from test_app_tools_ui import APP, add_managed_copy
from tools_manager import DENO, FFMPEG, YTDLP, record_check

VIDEO_INFO = {
    "title": "Me at the zoo",
    "uploader": "jawed",
    "duration": 19,
    "formats": [{"format_id": "251", "acodec": "opus", "vcodec": "none", "ext": "webm"}],
}


def block_of(widget):
    while widget is not None and not isinstance(widget, ttk.Labelframe):
        widget = widget.master
    return str(widget["text"]) if widget is not None else None


class ThemeTests(ErgonomicsTestCase):
    def start_with_windows_theme(self, dark):
        # "-auto" copies follow the Windows setting.
        with mock.patch.object(APP, "windows_prefers_dark", return_value=dark),                 mock.patch.object(APP, "get_launcher_path", return_value="C:/Apps/StreamDL-auto.exe"):
            self.start_ready_app()

    def assert_backgrounds_follow_theme(self, color):
        # Set before the window is first shown, so sv-ttk's own event never fires.
        style = ttk.Style(self.root)
        for element in (".", "TFrame", "TLabel", "TCheckbutton"):
            self.assertEqual(str(style.lookup(element, "background")), color, element)
        self.assertEqual(str(self.root["background"]), color)

    def test_light_windows_theme(self):
        self.start_with_windows_theme(dark=False)
        self.assertEqual(ttk.Style(self.root).theme_use(), "sun-valley-light")
        self.assert_backgrounds_follow_theme("#fafafa")
        self.assertEqual(str(self.app.log_box["background"]), APP.PALETTES["light"]["text_bg"])

    def test_dark_windows_theme(self):
        self.start_with_windows_theme(dark=True)
        self.assertEqual(ttk.Style(self.root).theme_use(), "sun-valley-dark")
        self.assert_backgrounds_follow_theme("#1c1c1c")
        self.assertEqual(str(self.app.log_box["background"]), APP.PALETTES["dark"]["text_bg"])
        self.app.on_download_cancelled()
        self.assertEqual(str(self.app.status_label["foreground"]), APP.PALETTES["dark"]["warning"])

    def test_without_the_theme_package_the_classic_look_is_used(self):
        with mock.patch.object(APP, "sv_ttk", None), \
                mock.patch.object(APP, "windows_prefers_dark", return_value=True):
            self.start_ready_app()
        self.assertFalse(ttk.Style(self.root).theme_use().startswith("sun-valley"))
        # Dark colors would be unreadable on the classic light widgets.
        self.assertEqual(str(self.app.log_box["background"]), APP.PALETTES["light"]["text_bg"])
        self.assertEqual(self.tk_errors, [])


class ThemeByExeNameTests(ErgonomicsTestCase):
    def test_exe_name_selects_the_theme(self):
        for name, expected in (
            ("StreamDL-clair.exe", "light"),
            ("StreamDL-sombre.exe", "dark"),
            ("StreamDL-natif.exe", "native"),
            ("STREAMDL-SOMBRE.EXE", "dark"),
            ("StreamDL-auto.exe", "auto"),
            ("StreamDL.exe", "light"),
            ("telechargeur_youtube_v1.88.pyw", "light"),
        ):
            with mock.patch.object(APP, "get_launcher_path", return_value=f"C:/Apps/{name}"):
                self.assertEqual(APP.requested_theme(), expected, name)

    def start_as(self, exe_name, windows_dark):
        with mock.patch.object(APP, "get_launcher_path", return_value=f"C:/Apps/{exe_name}"), \
                mock.patch.object(APP, "windows_prefers_dark", return_value=windows_dark):
            self.start_ready_app()
        return ttk.Style(self.root).theme_use()

    def test_default_exe_opens_light_even_on_a_dark_windows(self):
        self.assertEqual(self.start_as("StreamDL.exe", windows_dark=True), "sun-valley-light")

    def test_dark_copy_ignores_a_light_windows(self):
        self.assertEqual(self.start_as("StreamDL-sombre.exe", windows_dark=False), "sun-valley-dark")

    def test_light_copy_ignores_a_dark_windows(self):
        self.assertEqual(self.start_as("StreamDL-clair.exe", windows_dark=True), "sun-valley-light")

    def test_native_copy_uses_the_classic_look(self):
        theme = self.start_as("StreamDL-natif.exe", windows_dark=True)
        self.assertFalse(theme.startswith("sun-valley"))
        self.assertEqual(str(self.app.log_box["background"]), APP.PALETTES["light"]["text_bg"])


class WindowDisplayTests(ErgonomicsTestCase):
    def open_visible_window(self, exe_name):
        if not (self.storage / "yt-dlp").exists():
            for spec, version in ((YTDLP, "2026.10.26"), (DENO, "2.9.8"), (FFMPEG, "2026.10.30.1913")):
                add_managed_copy(self.storage, spec, version)
                record_check(spec, self.storage)
        root = tk.Tk()
        root.attributes("-alpha", 0.0)  # invisible while the test runs
        sizes, states = [], []
        set_geometry = root.geometry

        def geometry(*args):
            sizes.extend(args)
            return set_geometry(*args)

        def deiconify():
            states.append((root.winfo_ismapped(), list(sizes), len(root.winfo_children())))

        root.geometry = geometry
        root.deiconify = deiconify
        # These closures refer to the window: remove them so no cycle keeps it.
        self.addCleanup(root.__dict__.pop, "geometry", None)
        self.addCleanup(root.__dict__.pop, "deiconify", None)
        with mock.patch.object(APP, "get_launcher_path", return_value=f"C:/Apps/{exe_name}"):
            app = APP.App(root)
        self.addCleanup(self.close_quietly, app)
        return root, states

    def test_window_is_shown_once_complete(self):
        root, states = self.open_visible_window("StreamDL.exe")
        # Shown a single time, never before: no empty window of the default size.
        self.assertEqual(len(states), 1)
        mapped, sizes, children = states[0]
        self.assertEqual(mapped, 0)
        self.assertIn(APP.WINDOW_SIZE, sizes)
        self.assertGreater(children, 5)

    def test_dark_title_bar_is_set_once_the_window_is_shown(self):
        root, _ = self.open_visible_window("StreamDL-sombre.exe")
        self.assertNotEqual(root.bind("<Map>"), "")

    def test_light_title_bar_needs_nothing(self):
        root, _ = self.open_visible_window("StreamDL.exe")
        self.assertEqual(root.bind("<Map>"), "")


class BlockTests(ErgonomicsTestCase):
    def test_controls_are_grouped_in_three_blocks(self):
        self.start_ready_app()
        self.assertEqual(block_of(self.app.url_entry), "Vidéo")
        self.assertEqual(block_of(self.app.cookies_browser_combo), "Vidéo")
        self.assertEqual(block_of(self.app.video_preset_btn), "Format")
        self.assertEqual(block_of(self.app.audio_conversion_combo), "Format")
        self.assertEqual(block_of(self.app.folder_entry), "Destination")

    def test_every_row_fits_in_the_window_width(self):
        self.start_ready_app()
        self.app.toggle_conversion_options()
        self.root.update_idletasks()
        width = int(APP.WINDOW_SIZE.split("x")[0])
        for child in self.root.winfo_children():
            if child.winfo_manager() == "pack":
                self.assertLessEqual(child.winfo_reqwidth(), width - 24, child)


class BottomTabsTests(ErgonomicsTestCase):
    def test_journal_and_history_share_tabs(self):
        self.start_ready_app()
        tabs = self.app.bottom_tabs
        self.assertEqual([str(tabs.tab(tab, "text")) for tab in tabs.tabs()], ["Journal", "Historique"])
        self.assertTrue(str(self.app.log_box).startswith(tabs.tabs()[0]))
        self.assertTrue(str(self.app.history_tree).startswith(tabs.tabs()[1]))

    def test_history_tab_counts_downloads(self):
        self.start_ready_app()
        for name in ("a.mp4", "b.mp3"):
            self.app.add_history_entry(str(self.downloads / name), "Aucune")
        self.assertEqual(str(self.app.bottom_tabs.tab(self.app.history_tab, "text")), "Historique (2)")


class ThemedIconTests(ErgonomicsTestCase):
    def test_github_icon_is_light_on_the_dark_theme(self):
        with mock.patch.object(APP, "get_launcher_path", return_value="C:/Apps/StreamDL-sombre.exe"):
            self.start_ready_app()
        self.assertTrue(APP.themed_asset("social_github.png").endswith("social_github_dark.png"))
        # Icons without a dark variant are used as they are.
        self.assertTrue(APP.themed_asset("social_youtube.png").endswith("social_youtube.png"))

    def test_regular_icon_on_the_light_theme(self):
        self.start_ready_app()
        self.assertTrue(APP.themed_asset("social_github.png").endswith("social_github.png"))


class ConversionOptionsTests(ErgonomicsTestCase):
    def test_options_are_folded_by_default(self):
        self.start_ready_app()
        self.assertEqual(self.app.conversion_frame.winfo_manager(), "")
        self.app.toggle_conversion_options()
        self.assertEqual(self.app.conversion_frame.winfo_manager(), "pack")
        self.assertTrue(str(self.app.conversion_toggle_btn["text"]).startswith("▾"))
        self.app.toggle_conversion_options()
        self.assertEqual(self.app.conversion_frame.winfo_manager(), "")

    def test_advanced_format_unfolds_the_options(self):
        self.start_ready_app()
        self.app.url_var.set("https://www.youtube.com/watch?v=jNQXAC9IVRw")
        dialog = mock.Mock(selected_format="251")
        with mock.patch.object(APP.App, "run_command_json", return_value=(0, json.dumps(VIDEO_INFO), "")), \
                mock.patch.object(APP, "FormatSelector", return_value=dialog), \
                mock.patch.object(self.root, "wait_window"):
            self.app.choose_format_flow()
            self.pump_until(lambda: self.app.selected_download_format == "251")
        self.assertEqual(self.app.conversion_frame.winfo_manager(), "pack")
        self.assertEqual(str(self.app.audio_conversion_combo["state"]), "readonly")


class PreviewTests(ErgonomicsTestCase):
    def read_video(self, info, playlist=False):
        self.start_ready_app()
        self.app.url_var.set("https://www.youtube.com/watch?v=jNQXAC9IVRw")
        self.app.playlist_mode_var.set(playlist)
        with mock.patch.object(APP.App, "run_command_json", return_value=(0, json.dumps(info), "")), \
                mock.patch.object(APP.App, "download_worker") as worker:
            self.app.start_preset("video")
            self.pump_until(lambda: worker.called)
        return self.app.preview_var.get()

    def test_title_channel_and_duration_are_shown(self):
        preview = self.read_video(VIDEO_INFO)
        for part in ("Me at the zoo", "jawed", "0:19"):
            self.assertIn(part, preview)
        self.assertEqual(self.app.preview_label.winfo_manager(), "pack")

    def test_playlist_preview(self):
        info = {"_type": "playlist", "title": "Mes favoris", "entries": [VIDEO_INFO, VIDEO_INFO, VIDEO_INFO]}
        preview = self.read_video(info, playlist=True)
        self.assertIn("Mes favoris", preview)
        self.assertIn("3 vidéos", preview)

    def test_new_reading_clears_the_previous_preview(self):
        self.read_video(VIDEO_INFO)
        self.app.url_var.set("https://www.youtube.com/watch?v=other")
        with mock.patch.object(APP.App, "run_command_json", return_value=(1, "", "ERROR: x")):
            self.app.choose_format_flow()
            self.assertEqual(self.app.preview_var.get(), "")
            self.assertEqual(self.app.preview_label.winfo_manager(), "")
            self.pump_until(lambda: str(self.app.choose_format_btn["state"]) == "normal")

    def test_duration_format(self):
        self.assertEqual(APP.format_duration(19), "0:19")
        self.assertEqual(APP.format_duration(59.6), "1:00")
        self.assertEqual(APP.format_duration(3725), "1:02:05")
        self.assertEqual(APP.format_duration(None), "")
        self.assertEqual(APP.format_duration("?"), "")


class BuildThemeTests(unittest.TestCase):
    def test_theme_files_are_packaged(self):
        source = build_exe.find_latest_source()
        self.assertIn("--include-package-data=sv_ttk",
                      build_exe.nuitka_arguments(source, full=False, output_dir=build_exe.WORK_DIR))
        arguments = build_exe.pyinstaller_arguments(source, full=False)
        self.assertEqual(arguments[arguments.index("--collect-data") + 1], "sv_ttk")


if __name__ == "__main__":
    unittest.main()
