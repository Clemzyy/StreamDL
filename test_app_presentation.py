"""Presentation of the main window: theme, blocks, conversion options, preview.

Run: py -3.13 -m unittest -v test_app_presentation.py
"""
import json
import statistics
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

# Part of yt-dlp's real -J output for jNQXAC9IVRw: formats go from worst to best.
REAL_INFO = {
    "title": "Me at the zoo",
    "duration": 19,
    "filesize_approx": 635110,
    "formats": [
        {"format_id": "sb0", "ext": "mhtml", "vcodec": "none", "acodec": "none"},
        # HLS audio whose codec yt-dlp does not know.
        {"format_id": "233", "ext": "mp4", "vcodec": "none", "acodec": None, "format_note": "Default, low",
         "protocol": "m3u8_native"},
        {"format_id": "139", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.5", "abr": 49.14,
         "filesize": 117526},
        {"format_id": "140-drc", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2", "abr": 129.757,
         "filesize": 309197},
        {"format_id": "251", "ext": "webm", "vcodec": "none", "acodec": "opus", "abr": 106.064,
         "filesize": 252182},
        {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2", "abr": 129.796,
         "filesize": 309288},
        {"format_id": "160", "ext": "mp4", "vcodec": "avc1.4D400B", "acodec": "none", "height": 144,
         "fps": 15, "tbr": 82.513, "filesize": 195278, "protocol": "https"},
        {"format_id": "229", "ext": "mp4", "vcodec": "avc1.4D400C", "acodec": "none", "height": 240,
         "fps": 15.0, "tbr": 245.113, "protocol": "m3u8_native"},
        {"format_id": "134", "ext": "mp4", "vcodec": "avc1.4D400C", "acodec": "none", "height": 240,
         "fps": 15, "tbr": 136.218, "filesize": 322379, "protocol": "https"},
        {"format_id": "18", "ext": "mp4", "vcodec": "avc1.42001E", "acodec": "mp4a.40.2", "height": 240,
         "fps": 15, "tbr": 266.531, "filesize_approx": 635110, "protocol": "https"},
        # VP9 in mp4 over HLS: the same quality as 242, bigger and slower.
        {"format_id": "604", "ext": "mp4", "vcodec": "vp09.00.20.08", "acodec": "none", "height": 240,
         "fps": 15.0, "tbr": 198.586, "protocol": "m3u8_native"},
        {"format_id": "242", "ext": "webm", "vcodec": "vp9", "acodec": "none", "height": 240,
         "fps": 15, "tbr": 123.838, "filesize": 293080, "protocol": "https"},
    ],
}


# Part of yt-dlp's real -J output for _MK4k-KfWq8 (33 min): "Automatique"
# gets the Premium 1080p over HLS, whose size yt-dlp does not give.
PREMIUM_FORMATS = [
    {"format_id": "251-3", "ext": "webm", "vcodec": "none", "acodec": "opus", "abr": 128.519,
     "filesize": 32239408, "protocol": "https"},
    {"format_id": "270", "ext": "mp4", "vcodec": "avc1.640028", "acodec": "none", "height": 1080,
     "fps": 25.0, "tbr": 4876.675, "protocol": "m3u8_native"},
    {"format_id": "137", "ext": "mp4", "vcodec": "avc1.640028", "acodec": "none", "height": 1080,
     "fps": 25, "tbr": 2424.165, "filesize": 608_100_000, "protocol": "https"},
    {"format_id": "614", "ext": "mp4", "vcodec": "vp09.00.40.08", "acodec": "none", "height": 1080,
     "fps": 25.0, "tbr": 3188.041, "protocol": "m3u8_native"},
    {"format_id": "248", "ext": "webm", "vcodec": "vp9", "acodec": "none", "height": 1080,
     "fps": 25, "tbr": 1465.248, "filesize": 367_500_000, "protocol": "https"},
    {"format_id": "616", "ext": "mp4", "vcodec": "vp09.00.40.08", "acodec": "none", "height": 1080,
     "fps": 25.0, "tbr": 5098.958, "protocol": "m3u8_native", "format_note": "Premium"},
]
PREMIUM_INFO = {
    "title": "J'ai corrigé les défauts de ma GT40",
    "duration": 2007,
    "format_id": "616+251-3",
    # yt-dlp's own estimate: the audio only (30,7 Mo).
    "filesize_approx": 32239408,
    "formats": PREMIUM_FORMATS,
    "requested_formats": [PREMIUM_FORMATS[5], PREMIUM_FORMATS[0]],
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

    def history_files(self):
        return [self.app.history_tree.item(item, "values")[1] for item in self.app.history_tree.get_children()]

    def test_history_is_kept_after_closing(self):
        self.start_ready_app()
        self.app.add_history_entry(str(self.downloads / "a.mp4"), "Aucune")
        self.app.add_history_entry(str(self.downloads / "b.mp3"), "MP3")
        self.app.on_application_close()
        self.start_app()
        self.assertEqual(self.history_files(), ["b.mp3", "a.mp4"])
        self.assertEqual(self.app.download_history[0]["file"], str(self.downloads / "b.mp3"))
        self.assertEqual(str(self.app.bottom_tabs.tab(self.app.history_tab, "text")), "Historique (2)")

    def test_history_keeps_the_latest_downloads(self):
        with mock.patch.object(APP, "HISTORY_LIMIT", 3):
            self.start_ready_app()
            for index in range(5):
                self.app.add_history_entry(str(self.downloads / f"{index}.mp4"), "Aucune")
            self.app.on_application_close()
            self.start_app()
        self.assertEqual(self.history_files(), ["4.mp4", "3.mp4", "2.mp4"])

    def test_damaged_history_file_is_ignored(self):
        history = self.storage.parent / "history.json"
        history.parent.mkdir(parents=True, exist_ok=True)
        history.write_text("{pas du json", encoding="utf-8")
        self.start_ready_app()
        self.assertEqual(self.history_files(), [])
        self.app.on_application_close()
        entries = [{"file": 3}, "texte", {"time": "31/10 12:00", "file": "C:/Vidéos/ok.mp4",
                                         "conversion": "Aucune", "folder": "C:/Vidéos"}]
        history.write_text(json.dumps(entries), encoding="utf-8")
        self.start_app()
        self.assertEqual(self.history_files(), ["ok.mp4"])
        self.assertEqual(self.tk_errors, [])

    def test_history_can_be_cleared(self):
        self.start_ready_app()
        self.app.add_history_entry(str(self.downloads / "a.mp4"), "Aucune")
        with mock.patch.object(APP.messagebox, "askyesno", return_value=True):
            self.app.clear_history()
        self.assertEqual(self.history_files(), [])
        self.assertEqual(str(self.app.bottom_tabs.tab(self.app.history_tab, "text")), "Historique")
        self.app.on_application_close()
        self.start_app()
        self.assertEqual(self.history_files(), [])


class ThemedIconTests(ErgonomicsTestCase):
    def test_github_icon_is_light_on_the_dark_theme(self):
        with mock.patch.object(APP, "get_launcher_path", return_value="C:/Apps/StreamDL-sombre.exe"):
            self.start_ready_app()
        # Every icon has a dark version, without the light disc behind it.
        for _, icon, _ in APP.SOCIAL_LINKS:
            self.assertTrue(APP.themed_asset(icon).endswith(icon.replace(".png", "_dark.png")), icon)

    def test_regular_icon_on_the_light_theme(self):
        self.start_ready_app()
        self.assertTrue(APP.themed_asset("social_github.png").endswith("social_github.png"))

    def image_of(self, icon_name):
        button = dict(self.app.social_buttons)[icon_name]
        return str(button.cget("image")[0])

    def assert_icons_match(self, mode):
        for _, icon_name, _ in APP.SOCIAL_LINKS:
            self.assertEqual(
                self.image_of(icon_name),
                str(self.app.social_icon_cache[mode, icon_name])
            )
        github = self.image_of("social_github.png")
        color = (255, 255, 255) if mode == "dark" else (0, 0, 0)
        self.assertEqual(tuple(self.root.tk.call(github, "get", 16, 16)), color)

    def test_displayed_icons_follow_light_dark_light_without_reading_files_again(self):
        self.start_ready_app()
        self.assert_icons_match("light")
        count = len(self.app.social_icon_images)
        # A packaged app must still switch after its startup resources are
        # unavailable; checking themed_asset() alone did not test the widget.
        with mock.patch.object(APP.tk, "PhotoImage", side_effect=AssertionError("image reloaded")), \
                mock.patch.object(APP, "find_asset", return_value=None):
            for mode in ("dark", "light", "dark", "light"):
                self.app.switch_theme(mode)
                self.root.update_idletasks()
                self.assert_icons_match(mode)
        self.assertEqual(len(self.app.social_icon_images), count)

    def test_displayed_icons_follow_dark_light_dark(self):
        with mock.patch.object(APP, "get_launcher_path", return_value="C:/Apps/StreamDL-sombre.exe"):
            self.start_ready_app()
        for mode in ("dark", "light", "dark"):
            self.app.switch_theme(mode)
            self.root.update_idletasks()
            self.assert_icons_match(mode)

    def test_displayed_logos_have_no_translucent_disc_in_either_theme(self):
        from PIL import Image

        self.start_ready_app()
        for mode in ("light", "dark"):
            self.app.switch_theme(mode)
            for _, icon_name, _ in APP.SOCIAL_LINKS[:-1]:
                with Image.open(build_exe.PROJECT_DIR / icon_name) as original:
                    rgba = original.convert("RGBA")
                    disc = [(x, y) for y in range(rgba.height) for x in range(rgba.width)
                            if rgba.getpixel((x, y)) == (255, 255, 255, 51)]
                if icon_name == "social_paypal.png":
                    # Regenerated from the vector mark, with no disc even
                    # in the original/light asset.
                    self.assertEqual(disc, [])
                else:
                    self.assertTrue(disc)
                image = self.image_of(icon_name)
                self.assertTrue(all(
                    self.root.tk.getboolean(self.root.tk.call(image, "transparency", "get", x, y))
                    for x, y in disc
                ), (mode, icon_name))


def all_widgets(widget):
    found = [widget]
    for child in widget.winfo_children():
        found += all_widgets(child)
    return found


class ThemeSwitchTests(ErgonomicsTestCase):
    def labels(self):
        return [label for label, _ in self.app.theme_menu_items()]

    def test_light_theme_offers_dark_mode(self):
        self.start_ready_app()
        self.assertEqual(self.labels(), ["Passer en mode sombre"])

    def test_switch_to_dark_mode_is_remembered(self):
        self.start_ready_app()
        dict(self.app.theme_menu_items())["Passer en mode sombre"]()
        self.assertEqual(APP.palette["mode"], "dark")
        self.assertEqual(self.labels(), ["Passer en mode clair"])
        self.app.on_application_close()
        self.start_app()
        self.assertEqual(APP.palette["mode"], "dark")
        self.assertEqual(self.labels(), ["Passer en mode clair"])

    def test_colors_and_icons_follow_the_switch(self):
        self.start_ready_app()
        light, dark = APP.PALETTES["light"], APP.PALETTES["dark"]
        muted = [widget for widget in all_widgets(self.root)
                 if isinstance(widget, ttk.Label) and str(widget.cget("foreground")).lower() == light["muted"]]
        self.assertTrue(muted)
        self.app.switch_theme("dark")
        self.assertEqual({str(widget.cget("foreground")).lower() for widget in muted}, {dark["muted"]})
        self.assertEqual(str(self.app.log_box.cget("background")).lower(), dark["text_bg"])
        self.assertEqual(str(self.app.log_box.tag_cget("detail", "foreground")).lower(), dark["detail"])
        self.assertTrue(APP.themed_asset("social_github.png").endswith("social_github_dark.png"))
        self.app.switch_theme("light")
        self.assertEqual({str(widget.cget("foreground")).lower() for widget in muted}, {light["muted"]})
        self.assertEqual(self.tk_errors, [])

    def test_switched_window_matches_a_window_opened_dark(self):
        with mock.patch.object(APP, "get_launcher_path", return_value="C:/Apps/StreamDL-sombre.exe"):
            self.start_ready_app()
        opened_dark = {str(widget): str(widget.cget("background")) for widget in all_widgets(self.root)
                       if not isinstance(widget, ttk.Widget)}
        self.app.on_application_close()
        self.start_app()
        self.app.switch_theme("dark")
        switched = {str(widget): str(widget.cget("background")) for widget in all_widgets(self.root)
                    if not isinstance(widget, ttk.Widget)}
        self.assertEqual(switched, opened_dark)

    def test_exe_name_still_wins(self):
        self.start_ready_app()
        self.app.switch_theme("dark")
        self.app.on_application_close()
        with mock.patch.object(APP, "get_launcher_path", return_value="C:/Apps/StreamDL-clair.exe"):
            self.start_app()
        self.assertEqual(APP.palette["mode"], "light")

    def test_classic_windows_look_has_no_switch(self):
        with mock.patch.object(APP, "get_launcher_path", return_value="C:/Apps/StreamDL-natif.exe"):
            self.start_ready_app()
        self.assertEqual(self.app.theme_menu_items(), [])

    def test_right_click_menus_offer_the_switch(self):
        self.start_ready_app()
        menu = APP.build_edit_menu(self.app.url_entry, self.app.theme_menu_items())
        self.assertEqual(menu.entrycget(menu.index("end"), "label"), "Passer en mode sombre")
        event = mock.Mock(widget=self.app.history_tree, x_root=3, y_root=4)
        with mock.patch.object(APP.tk.Menu, "tk_popup") as popup:
            self.app.show_window_menu(event)
        popup.assert_called_once_with(3, 4)
        self.assertTrue(self.root.bind("<Button-3>"))


class ContextMenuColorsTests(ErgonomicsTestCase):
    def test_edit_menu_uses_light_text_on_the_dark_theme(self):
        self.start_ready_app()
        self.app.switch_theme("dark")
        menu = APP.build_edit_menu(self.app.url_entry, self.app.theme_menu_items())
        self.addCleanup(menu.destroy)
        self.assertEqual(str(menu.cget("foreground")), "#ffffff")
        self.assertEqual(str(menu.cget("activeforeground")), "#ffffff")
        self.assertEqual(str(menu.cget("background")), "#2b2b2b")
        self.assertNotEqual(str(menu.cget("disabledforeground")), str(menu.cget("foreground")))
        from tkinter import font

        self.assertEqual(font.Font(root=self.root, font=menu.cget("font")).actual("weight"), "bold")

    def test_window_menu_and_edit_menu_share_the_theme_colors(self):
        self.start_ready_app()
        self.app.switch_theme("dark")
        menus = []
        make_menu = APP.make_context_menu

        def capture(parent):
            menu = make_menu(parent)
            menus.append(menu)
            return menu

        with mock.patch.object(APP, "make_context_menu", side_effect=capture), \
                mock.patch.object(APP.tk.Menu, "tk_popup"):
            self.app.show_window_menu(mock.Mock(widget=self.app.history_tree, x_root=3, y_root=4))
        self.addCleanup(menus[0].destroy)
        self.assertEqual(str(menus[0].cget("foreground")), "#ffffff")

    def test_new_menu_returns_to_dark_text_on_the_light_theme(self):
        self.start_ready_app()
        self.app.switch_theme("dark")
        self.app.switch_theme("light")
        menu = APP.make_context_menu(self.root)
        self.addCleanup(menu.destroy)
        self.assertEqual(str(menu.cget("foreground")), "#1c1c1c")
        self.assertEqual(str(menu.cget("activeforeground")), "#1c1c1c")
        self.assertEqual(str(menu.cget("background")), "#ffffff")
        from tkinter import font

        self.assertEqual(font.Font(root=self.root, font=menu.cget("font")).actual("weight"), "normal")


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


class FormatChoicesTests(unittest.TestCase):
    def setUp(self):
        self.choices = APP.format_choices(REAL_INFO)

    def formats(self, kind):
        return [choice["format"] for choice in self.choices[kind]]

    def test_three_kinds_best_first(self):
        # Storyboards (mhtml), DRC audio copies and the unknown codec (233)
        # are left out; the HLS copies of 134 (229) and 242 (604) are duplicates.
        self.assertEqual(self.formats("video"), ["134+ba/134", "242+ba/242", "160+ba/160"])
        self.assertEqual(self.formats("video_only"), ["134", "242", "160"])
        self.assertEqual(self.formats("audio"), ["140", "251", "139"])

    def test_video_with_sound_adds_the_best_audio_size(self):
        best = self.choices["video"][0]
        self.assertEqual(best["size"], 322379 + 309288)
        self.assertEqual(best["label"], "240p · 15 i/s · H.264 · ~616,9 Ko")
        self.assertEqual(best["kind"], "video")

    def test_labels_of_video_only_and_audio(self):
        self.assertEqual(self.choices["video_only"][1]["label"], "240p · 15 i/s · VP9 · webm · ~286,2 Ko")
        self.assertEqual(self.choices["audio"][0]["label"], "130 kb/s · AAC · m4a · ~302,0 Ko")
        self.assertEqual(self.choices["audio"][0]["kind"], "audio")

    def test_automatic_size(self):
        self.assertEqual(self.choices["auto_size"], 635110)

    def test_size_estimated_from_bitrate_and_duration(self):
        self.assertEqual(APP.estimated_size({"tbr": 245.113}, 19), int(245.113 * 125 * 19))
        self.assertIsNone(APP.estimated_size({}, 19))

    def test_site_with_a_single_unknown_format(self):
        choices = APP.format_choices({"formats": [{"format_id": "0", "ext": "mp4", "url": "x"}]})
        self.assertEqual(self.formats_of(choices, "video"), ["0"])

    def formats_of(self, choices, kind):
        return [choice["format"] for choice in choices[kind]]

    def test_sizes_in_french_units(self):
        self.assertEqual(APP.human_size(635110), "620,2 Ko")
        self.assertEqual(APP.human_size(3 * 1024 ** 3), "3,0 Go")
        self.assertEqual(APP.human_size(None), "?")


class SizeEstimateTests(unittest.TestCase):
    def test_automatic_size_counts_the_hls_video(self):
        size = APP.automatic_size(PREMIUM_INFO)
        # Downloaded for real: a little over 600 Mo.
        self.assertGreater(size, 550 * 1024 ** 2)
        self.assertLess(size, 700 * 1024 ** 2)
        self.assertEqual(APP.format_choices(PREMIUM_INFO)["auto_size"], size)
        self.assertTrue(APP.build_preview_text(PREMIUM_INFO, False).endswith("~" + APP.human_size(size)))

    def test_hls_bitrate_is_scaled_by_the_direct_downloads_of_the_same_height(self):
        expected = statistics.median([
            608_100_000 / (4876.675 * 125 * 2007),  # 270 (HLS) / 137 (direct)
            367_500_000 / (3188.041 * 125 * 2007),  # 614 (HLS) / 248 (direct)
        ])
        factors = APP.hls_size_factors(PREMIUM_FORMATS, 2007)
        self.assertAlmostEqual(factors[1080], expected)
        # Other heights use every measure.
        self.assertAlmostEqual(factors[None], expected)
        self.assertEqual(APP.hls_size_factors([], 2007), {None: APP.HLS_DEFAULT_FACTOR})

    def test_premium_is_offered_apart(self):
        video = APP.format_choices(PREMIUM_INFO)["video"]
        self.assertEqual(video[0]["format"], "616+ba/616")
        self.assertIn("Premium", video[0]["label"])
        self.assertEqual([choice["format"] for choice in video], ["616+ba/616", "137+ba/137", "248+ba/248"])


class DarkIconTests(unittest.TestCase):
    def pixels(self, name):
        from PIL import Image

        with Image.open(build_exe.PROJECT_DIR / name) as image:
            rgba = image.convert("RGBA")
            return [rgba.getpixel((x, y)) for y in range(rgba.height)
                    for x in range(rgba.width)]

    def test_every_icon_has_a_dark_version_without_its_light_disc(self):
        # GitHub's dark version is white on purpose: test_github_is_white...
        for link_label, icon, url in APP.SOCIAL_LINKS[:-1]:
            dark = icon.replace(".png", "_dark.png")
            with self.subTest(icon=dark):
                self.assertTrue((build_exe.PROJECT_DIR / dark).is_file())
                # The light version sits on a 20 % white disc: grey on a dark
                # background. Where only that disc shows, the dark one is clear.
                disc = [index for index, pixel in enumerate(self.pixels(icon))
                        if pixel == (255, 255, 255, 51)]
                if icon == "social_paypal.png":
                    self.assertEqual(disc, [])
                    continue
                self.assertGreater(len(disc), 50)
                dark_pixels = self.pixels(dark)
                self.assertEqual({dark_pixels[index][3] for index in disc}, {0})

    def test_github_is_white_on_the_dark_theme(self):
        colors = {p[:3] for p in self.pixels("social_github_dark.png") if p[3] > 0}
        self.assertEqual(colors, {(255, 255, 255)})

    def test_paypal_has_clean_blue_edges_on_a_transparent_background(self):
        light = self.pixels("social_paypal.png")
        self.assertEqual(light, self.pixels("social_paypal_dark.png"))
        self.assertEqual(light[0][3], 0)
        edge = [pixel for pixel in light if 0 < pixel[3] < 255]
        self.assertTrue(edge)
        self.assertTrue(all(b >= g and b > r for r, g, b, a in edge))
        self.assertFalse(any(min(pixel[:3]) > 180 for pixel in edge))


class FormatDialogTests(ErgonomicsTestCase):
    def open_dialog(self):
        self.start_ready_app()
        self.choices = APP.format_choices(REAL_INFO)
        dialog = APP.FormatSelector(self.root, self.choices, "Vidéo : Me at the zoo")
        self.addCleanup(lambda: dialog.winfo_exists() and dialog.destroy())
        return dialog

    def test_automatic_is_the_default(self):
        dialog = self.open_dialog()
        self.assertEqual(dialog.mode_var.get(), "auto")
        self.assertIn("~620,2 Ko", str(dialog.auto_button["text"]))
        self.assertEqual(str(dialog.format_combo["state"]), "disabled")
        dialog.choose_selected()
        self.assertEqual(dialog.selected_format, "BEST_AUTO")

    def test_custom_video_with_sound(self):
        dialog = self.open_dialog()
        dialog.mode_var.set("custom")
        dialog.update_state()
        self.assertEqual(str(dialog.format_combo["state"]), "readonly")
        self.assertEqual(list(dialog.type_combo["values"]),
                         ["Vidéo avec son", "Vidéo uniquement (sans son)", "Audio uniquement"])
        self.assertEqual(dialog.type_var.get(), "Vidéo avec son")
        dialog.choose_selected()
        self.assertEqual(dialog.selected_format, "134+ba/134")

    def test_custom_audio(self):
        dialog = self.open_dialog()
        dialog.mode_var.set("custom")
        dialog.update_state()
        dialog.type_var.set("Audio uniquement")
        dialog.fill_formats()
        self.assertEqual(list(dialog.format_combo["values"]), [c["label"] for c in self.choices["audio"]])
        dialog.format_combo.current(1)
        dialog.choose_selected()
        self.assertEqual(dialog.selected_format, "251")

    def test_cancel(self):
        dialog = self.open_dialog()
        dialog.cancel()
        self.assertIsNone(dialog.selected_format)


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

    def test_estimated_size_is_shown(self):
        preview = self.read_video(dict(VIDEO_INFO, filesize_approx=635110))
        self.assertTrue(preview.endswith("· ~620,2 Ko"), preview)
        self.assertNotIn("~", APP.build_preview_text(VIDEO_INFO, False))

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
