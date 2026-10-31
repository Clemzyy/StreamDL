"""Ergonomics of the main window, driven in a hidden Tk window.

Run: py -3.13 -m unittest -v test_app_ergonomics.py
"""
import io
import json
import re
import sys
import tokenize
import unittest
from pathlib import Path
from unittest import mock

from test_app_tools_ui import APP, AppToolsTestCase, add_managed_copy
from tools_manager import DENO, FFMPEG, YTDLP, record_check


PROJECT_DIR = Path(__file__).resolve().parent
UNACCENTED_RE = re.compile(
    r"\b(telechargement|Telechargement|terminee|supprime|renomme|Echec|ignoree|necessaire|"
    r"detecte|supporte|Conversion video|conversion video|Format video)\b"
)
FORMAL_RE = re.compile(r"\b(vous|Vous|votre|Votre|vos|Vos|Voulez)\b|\b[A-Za-zéè]+ez\b")
NOT_FORMAL = {"chez", "assez", "nez"}

FAKE_YTDLP = '''
import os, sys, time
folder = os.path.dirname(sys.argv[sys.argv.index("-o") + 1])
partial = os.path.join(folder, "Fake video.f137.mp4")
with open(partial, "wb") as output:
    output.write(b"partial data")
print("[download] Destination: " + partial, flush=True)
print("[download]   1.0% of 10.00MiB at 1.00MiB/s ETA 00:09", flush=True)
time.sleep(60)
'''


def ui_strings(path):
    source = Path(path).read_text(encoding="utf-8")
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type in (tokenize.STRING, tokenize.FSTRING_MIDDLE):
            yield token.start[0], token.string


class ErgonomicsTestCase(AppToolsTestCase):
    def setUp(self):
        super().setUp()
        self.downloads = Path(self.temp.name) / "Downloads"
        self.downloads.mkdir()
        patcher = mock.patch.object(APP, "find_windows_downloads_folder", return_value=str(self.downloads))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.opened = []
        patcher = mock.patch.object(APP, "open_path", side_effect=self.opened.append)
        patcher.start()
        self.addCleanup(patcher.stop)

    def start_ready_app(self):
        for spec, version in ((YTDLP, "2026.10.26"), (DENO, "2.9.8"), (FFMPEG, "2026.10.30.1913")):
            add_managed_copy(self.storage, spec, version)
            record_check(spec, self.storage)
        self.start_app()
        self.wait_for_worker()


def latest_source():
    return max(PROJECT_DIR.glob("telechargeur_youtube_v*.pyw"),
               key=lambda p: tuple(int(n) for n in re.findall(r"_v(\d+)\.(\d+)", p.name)[0]))


class TextTests(unittest.TestCase):
    def test_title_shows_the_source_version(self):
        self.assertEqual(APP.APP_VERSION, re.search(r"_v(\d+\.\d+)", latest_source().name).group(1))
        self.assertEqual(APP.APP_TITLE, f"StreamDL v{APP.APP_VERSION}")

    def test_interface_texts_are_accented_and_informal(self):
        problems = []
        for path in (latest_source(), PROJECT_DIR / "auth_support.py"):
            for line, text in ui_strings(path):
                bad = {match.group(0) for match in UNACCENTED_RE.finditer(text)}
                bad |= {match.group(0) for match in FORMAL_RE.finditer(text)
                        if match.group(0).lower() not in NOT_FORMAL}
                if bad:
                    problems.append(f"{path.name}:{line} {sorted(bad)}")
        self.assertEqual(problems, [])


class LayoutTests(ErgonomicsTestCase):
    def test_authentication_help_button_fits_in_the_window(self):
        self.start_ready_app()
        self.root.update_idletasks()
        width = int(APP.WINDOW_SIZE.split("x")[0])
        self.assertLessEqual(self.app.cookies_frame.winfo_reqwidth(), width - 24)

    def test_actions_row_fits_in_the_window(self):
        self.start_ready_app()
        self.root.update_idletasks()
        width = int(APP.WINDOW_SIZE.split("x")[0])
        self.assertLessEqual(self.app.actions_frame.winfo_reqwidth(), width - 24)


class FolderTests(ErgonomicsTestCase):
    def test_download_folder_defaults_to_downloads(self):
        self.start_ready_app()
        self.assertEqual(self.app.folder_var.get(), str(self.downloads))

    def test_chosen_folder_is_remembered(self):
        chosen = Path(self.temp.name) / "Vidéos"
        chosen.mkdir()
        self.start_ready_app()
        with mock.patch.object(APP.filedialog, "askdirectory", return_value=str(chosen)):
            self.app.choose_folder()
        self.app.on_application_close()
        self.start_app()
        self.assertEqual(self.app.folder_var.get(), str(chosen))

    def test_missing_remembered_folder_falls_back_to_downloads(self):
        settings = self.storage.parent / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps({"download_folder": str(Path(self.temp.name) / "gone")}))
        self.start_ready_app()
        self.assertEqual(self.app.folder_var.get(), str(self.downloads))


class PresetTests(ErgonomicsTestCase):
    def run_preset(self, kind):
        self.start_ready_app()
        self.app.url_var.set("https://www.youtube.com/watch?v=jNQXAC9IVRw")
        info = json.dumps({"title": "Me at the zoo", "formats": [
            {"format_id": "251", "acodec": "opus", "vcodec": "none", "ext": "webm"},
        ]})
        with mock.patch.object(APP.App, "run_command_json", return_value=(0, info, "")), \
                mock.patch.object(APP.App, "download_worker") as worker, \
                mock.patch.object(APP, "FormatSelector", side_effect=AssertionError("dialogue affiché")):
            self.app.start_preset(kind)
            self.pump_until(lambda: worker.called)
        self.assertEqual(self.tk_errors, [])
        self.worker_kwargs = worker.call_args.kwargs
        return worker.call_args.args

    def test_video_preset_downloads_best_mp4_without_format_dialog(self):
        url, folder, selected, playlist, title, _ = self.run_preset("video")
        self.assertEqual((selected, title, folder), ("BEST_AUTO", "Me at the zoo", str(self.downloads)))
        self.assertEqual(self.app.video_conversion_var.get(), "Aucune conversion")

    def test_audio_preset_downloads_best_audio_as_mp3(self):
        url, folder, selected, playlist, title, _ = self.run_preset("audio")
        self.assertEqual(selected, "BEST_AUDIO")
        self.assertEqual(self.app.audio_conversion_var.get(), "MP3")
        self.assertTrue(self.app.is_audio_only_format("BEST_AUDIO", []))
        self.assertEqual(self.app.get_selected_format_kind("BEST_AUDIO"), "audio")

    def test_best_audio_asks_ytdlp_for_the_audio_track(self):
        self.start_ready_app()
        with mock.patch.object(APP.App, "run_command_live", return_value=(1, "ERROR: test")) as live, \
                mock.patch.object(APP.App, "on_download_error"):
            self.app.download_worker("https://youtu.be/x", str(self.downloads), "BEST_AUDIO",
                                     False, "x", APP.CookieSource.none())
        command = live.call_args.args[0]
        self.assertEqual(command[command.index("-f") + 1], "ba/b")

    def test_preview_tells_ytdlp_where_ffmpeg_is(self):
        # Without ffmpeg, yt-dlp sizes a single lower-quality file instead of
        # the merged best quality that "Automatique" downloads.
        self.start_ready_app()
        self.app.url_var.set("https://www.youtube.com/watch?v=jNQXAC9IVRw")
        info = json.dumps({"title": "Me at the zoo", "formats": []})
        with mock.patch.object(APP.App, "run_command_json", return_value=(0, info, "")) as fetch, \
                mock.patch.object(APP.App, "download_worker") as worker:
            self.app.start_preset("video")
            self.pump_until(lambda: worker.called)
        command = fetch.call_args.args[0]
        self.assertEqual(command[command.index("--ffmpeg-location") + 1],
                         APP.find_ffmpeg(self.app.tool_path("ffmpeg")))
        self.assertLess(command.index("--ffmpeg-location"), command.index("--"))

    def test_preview_json_is_handed_to_the_download(self):
        self.run_preset("video")
        self.assertEqual(json.loads(self.worker_kwargs["info_json"])["title"], "Me at the zoo")

    def test_playlist_json_is_not_reused(self):
        self.start_ready_app()
        self.app.url_var.set("https://www.youtube.com/playlist?list=PL1")
        self.app.playlist_mode_var.set(True)
        info = json.dumps({"_type": "playlist", "title": "Liste", "entries": [
            {"title": "Une", "formats": [{"format_id": "18", "acodec": "aac", "vcodec": "avc1", "ext": "mp4"}]},
        ]})
        with mock.patch.object(APP.App, "run_command_json", return_value=(0, info, "")), \
                mock.patch.object(APP.App, "download_worker") as worker:
            self.app.start_preset("video")
            self.pump_until(lambda: worker.called)
        self.assertIsNone(worker.call_args.kwargs["info_json"])

    def test_preset_needs_an_existing_folder(self):
        self.start_ready_app()
        self.app.url_var.set("https://www.youtube.com/watch?v=jNQXAC9IVRw")
        self.app.folder_var.set(str(Path(self.temp.name) / "absent"))
        with mock.patch.object(APP.App, "run_command_json") as fetch:
            self.app.start_preset("video")
        fetch.assert_not_called()
        self.assertEqual(len(self.dialogs), 1)

    def test_enter_in_the_url_field_starts_the_video_preset(self):
        self.start_ready_app()
        with mock.patch.object(self.app, "start_preset") as preset:
            self.app.on_url_return(None)
        preset.assert_called_once_with("video")


class PreviewReuseTests(ErgonomicsTestCase):
    URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    INFO = json.dumps({"_type": "video", "title": "Me at the zoo", "formats": []})

    def download(self, results):
        """Run download_worker with run_command_live returning `results` in turn."""
        self.start_ready_app()
        self.commands = []
        self.json_seen = []

        def live(cmd):
            self.commands.append(cmd)
            if "--load-info-json" in cmd:
                info_path = Path(cmd[cmd.index("--load-info-json") + 1])
                self.json_seen.append((info_path, info_path.read_text(encoding="utf-8")))
            result = results[len(self.commands) - 1]
            return result() if callable(result) else result

        with mock.patch.object(APP.App, "run_command_live", side_effect=live), \
                mock.patch.object(APP.App, "on_download_error"), \
                mock.patch.object(APP.App, "finish_cancelled_download"):
            self.app.download_worker(self.URL, str(self.downloads), "BEST_AUTO", False,
                                     "Me at the zoo", APP.CookieSource.none(), info_json=self.INFO)

    def test_download_reads_the_preview_json_instead_of_the_page(self):
        self.download([(1, "ERROR: test"), (1, "ERROR: test")])
        first = self.commands[0]
        self.assertNotIn(self.URL, first)
        self.assertEqual(self.json_seen[0][1], self.INFO)
        self.assertEqual(first[first.index("-f") + 1], "bv*+ba/b")
        # The JSON may hold the cookies of the request: it is never left behind.
        self.assertFalse(self.json_seen[0][0].exists())

    def test_failed_download_from_the_json_reads_the_page_again(self):
        self.download([(1, "ERROR: HTTP Error 403: Forbidden"), (0, "")])
        self.assertEqual(len(self.commands), 2)
        second = self.commands[1]
        self.assertNotIn("--load-info-json", second)
        self.assertEqual(second[-2:], ["--", self.URL])
        self.assertEqual(second[:second.index("--")], self.commands[0][:self.commands[0].index("--load-info-json")])

    def test_cancelled_download_is_not_retried(self):
        def cancel():
            self.app.cancel_requested = True
            return (1, "")

        self.download([cancel])
        self.assertEqual(len(self.commands), 1)


class EditMenuTests(ErgonomicsTestCase):
    def setUp(self):
        super().setUp()
        # A fake clipboard: the tests never touch the real one.
        self.clipboard = ["https://youtu.be/collé"]

        def clipboard_get(widget, **kwargs):
            return self.clipboard[0]

        def clipboard_clear(widget, **kwargs):
            self.clipboard[0] = ""

        def clipboard_append(widget, text, **kwargs):
            self.clipboard[0] += text

        for name, value in (("clipboard_get", clipboard_get), ("clipboard_clear", clipboard_clear),
                            ("clipboard_append", clipboard_append)):
            patcher = mock.patch.object(APP.tk.Misc, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def items(self, widget):
        menu = APP.build_edit_menu(widget)
        return {
            menu.entrycget(index, "label"): (menu, index)
            for index in range(menu.index("end") + 1)
            if menu.type(index) == "command"
        }

    def state(self, item):
        menu, index = item
        return str(menu.entrycget(index, "state"))

    def invoke(self, widget, label):
        menu, index = self.items(widget)[label]
        menu.invoke(index)

    def test_menu_has_the_usual_edit_commands(self):
        self.start_ready_app()
        self.assertEqual(list(self.items(self.app.url_entry)),
                         ["Couper", "Copier", "Coller", "Tout sélectionner"])

    def test_right_click_opens_it_in_every_text_field(self):
        self.start_ready_app()
        for widget_class in ("TEntry", "Text"):
            self.assertTrue(self.root.bind_class(widget_class, "<Button-3>"), widget_class)
        event = mock.Mock(widget=self.app.url_entry, x_root=10, y_root=20)
        with mock.patch.object(APP.tk.Menu, "tk_popup") as popup:
            APP.show_edit_menu(event)
        popup.assert_called_once_with(10, 20)

    def test_paste_replaces_the_selection(self):
        self.start_ready_app()
        self.app.url_var.set("ancien lien")
        self.app.url_entry.select_range(0, "end")
        self.invoke(self.app.url_entry, "Coller")
        self.assertEqual(self.app.url_var.get(), "https://youtu.be/collé")

    def test_cut_and_copy_need_a_selection(self):
        self.start_ready_app()
        self.app.folder_var.set(r"C:\Vidéos")
        self.app.folder_entry.selection_clear()
        items = self.items(self.app.folder_entry)
        self.assertEqual((self.state(items["Couper"]), self.state(items["Copier"])), ("disabled", "disabled"))
        self.app.folder_entry.select_range(0, "end")
        self.invoke(self.app.folder_entry, "Couper")
        self.assertEqual((self.clipboard[0], self.app.folder_var.get()), (r"C:\Vidéos", ""))

    def test_select_all(self):
        self.start_ready_app()
        self.app.url_var.set("https://youtu.be/x")
        self.invoke(self.app.url_entry, "Tout sélectionner")
        self.assertEqual(APP.text_widget_selection(self.app.url_entry), "https://youtu.be/x")

    def test_journal_can_only_be_copied(self):
        self.start_ready_app()
        self.app.log_box.tag_add("sel", "1.0", "1.9")
        items = self.items(self.app.log_box)
        self.assertEqual((self.state(items["Couper"]), self.state(items["Coller"])), ("disabled", "disabled"))
        self.invoke(self.app.log_box, "Copier")
        self.assertEqual(self.clipboard[0], self.app.log_box.get("1.0", "1.9"))


class OperaGXTests(ErgonomicsTestCase):
    def runtime_cookie_argument(self, browser):
        self.start_ready_app()
        self.app.cookies_browser_var.set(browser)
        with mock.patch.dict(APP.os.environ, {"APPDATA": r"C:\Users\x\AppData\Roaming"}):
            options = self.app.build_ytdlp_runtime_options(self.app.cookie_source_from_main_ui())
        return options[options.index("--cookies-from-browser") + 1]

    def test_opera_gx_cookies_come_from_its_own_profile(self):
        self.assertIn("Opera GX", APP.COOKIE_BROWSER_OPTIONS)
        self.assertEqual(self.runtime_cookie_argument("Opera GX"),
                         r"opera:C:\Users\x\AppData\Roaming\Opera Software\Opera GX Stable")

    def test_classic_opera_is_unchanged(self):
        self.assertEqual(self.runtime_cookie_argument("Opera"), "opera")


class CustomFormatDownloadTests(ErgonomicsTestCase):
    def test_video_merged_with_the_best_audio_is_saved_as_mp4(self):
        self.start_ready_app()
        with mock.patch.object(APP.App, "run_command_live", return_value=(1, "ERROR: test")) as live, \
                mock.patch.object(APP.App, "on_download_error"):
            self.app.download_worker("https://youtu.be/x", str(self.downloads), "134+ba/134",
                                     False, "x", APP.CookieSource.none())
        command = live.call_args.args[0]
        self.assertEqual(command[command.index("-f") + 1], "134+ba/134")
        self.assertEqual(command[command.index("--merge-output-format") + 1], "mp4")
        self.assertEqual(self.app.get_selected_format_ext("134+ba/134"), ".mp4")
        self.assertEqual(self.app.get_selected_format_kind("134+ba/134"), "video")


class Sha256Tests(ErgonomicsTestCase):
    def test_sha256_file_is_written_next_to_the_video(self):
        self.start_ready_app()
        video = self.downloads / "Sous-dossier" / "Me at the zoo.mp4"
        video.parent.mkdir()
        video.write_bytes(b"video")
        with mock.patch.object(self.app, "on_hash_success") as done:
            self.app.hash_worker(str(video), str(self.downloads))
            self.pump_until(lambda: done.called)
        self.assertTrue((video.parent / "Me at the zoo.mp4.sha256.txt").is_file())


class CancelTests(ErgonomicsTestCase):
    def test_cancel_stops_ytdlp_and_removes_its_partial_file(self):
        script = Path(self.temp.name) / "fake_ytdlp.py"
        script.write_text(FAKE_YTDLP, encoding="utf-8")
        partial = self.downloads / "Fake video.f137.mp4"
        self.start_ready_app()
        self.assertEqual(str(self.app.cancel_btn["state"]), "disabled")
        self.app.selected_download_format = "BEST_AUTO"
        self.app.selected_download_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
        self.app.selected_download_title = "Fake video"
        with mock.patch.object(APP, "find_downloader", return_value=[sys.executable, str(script)]):
            self.app.start_download_flow()
            self.pump_until(lambda: partial.exists() and self.app.current_process is not None)
            self.assertEqual(str(self.app.cancel_btn["state"]), "normal")
            self.app.cancel_download()
            self.pump_until(lambda: "annulé" in self.app.status_label["text"], timeout=20)
        self.assertFalse(partial.exists())
        self.assertEqual(self.dialogs, [])
        self.assertEqual(str(self.app.cancel_btn["state"]), "disabled")
        self.assertEqual(str(self.app.video_preset_btn["state"]), "normal")
        self.assertEqual(self.tk_errors, [])


class EndOfDownloadTests(ErgonomicsTestCase):
    def test_success_shows_open_buttons_without_popup(self):
        self.start_ready_app()
        video = self.downloads / "Me at the zoo.mp4"
        video.write_bytes(b"video")
        with mock.patch.object(APP, "open_folder") as open_folder:
            self.app.on_success(str(self.downloads), str(video))
        open_folder.assert_not_called()
        self.assertEqual(self.dialogs, [])
        self.assertIn("Me at the zoo.mp4", self.app.status_label["text"])
        self.assertEqual(self.app.result_frame.winfo_manager(), "pack")
        self.app.open_result_file_btn.invoke()
        self.assertEqual(self.opened, [str(video)])

    def test_new_step_hides_previous_result(self):
        self.start_ready_app()
        video = self.downloads / "a.mp4"
        video.write_bytes(b"video")
        self.app.on_success(str(self.downloads), str(video))
        self.app.disable_action_buttons()
        self.assertEqual(self.app.result_frame.winfo_manager(), "")


class JournalTests(ErgonomicsTestCase):
    def test_technical_lines_are_hidden_until_requested(self):
        self.start_ready_app()
        self.app.append_log("[ffmpeg] [libx264 @ 0x1] ref P L0: 56.0%", detail=True)
        self.app.append_log("Conversion terminée.")
        self.assertTrue(int(self.app.log_box.tag_cget("detail", "elide")))
        self.app.show_details_var.set(True)
        self.app.toggle_details_visibility()
        self.assertFalse(int(self.app.log_box.tag_cget("detail", "elide")))
        text = self.app.log_box.get("1.0", "end")
        self.assertIn("libx264", text)
        self.assertIn("Conversion terminée.", text)


class ClipboardTests(ErgonomicsTestCase):
    def test_link_in_clipboard_is_pasted_once(self):
        self.start_ready_app()
        with mock.patch.object(self.root, "clipboard_get", return_value="https://youtu.be/jNQXAC9IVRw\n"):
            self.app.auto_paste_clipboard()
            self.assertEqual(self.app.url_var.get(), "https://youtu.be/jNQXAC9IVRw")
            self.app.url_var.set("")
            self.app.auto_paste_clipboard()
            self.assertEqual(self.app.url_var.get(), "")

    def test_other_clipboard_text_is_ignored(self):
        self.start_ready_app()
        for text in ("bonjour", "--exec=calc.exe", "https://a b"):
            with mock.patch.object(self.root, "clipboard_get", return_value=text):
                self.app.auto_paste_clipboard()
            self.assertEqual(self.app.url_var.get(), "")


if __name__ == "__main__":
    unittest.main()
