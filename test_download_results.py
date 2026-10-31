"""Regression tests for final download paths and playlist conversions."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from test_app_tools_ui import APP
from test_app_ergonomics import ErgonomicsTestCase


def variable(value):
    return SimpleNamespace(get=lambda: value)


class DownloadResultsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.app = APP.App.__new__(APP.App)
        self.app.closing = False
        self.app.cancel_requested = False
        self.app.current_formats_list = []
        self.app.current_download_outputs = []
        self.app.tool_path = lambda name: "fake.exe"
        self.app.root = SimpleNamespace(after=lambda delay, callback: callback())
        self.app.audio_conversion_var = variable("MP3")
        self.app.video_conversion_var = variable("Aucune conversion")
        self.app.delete_audio_source_var = variable(True)
        self.app.delete_video_source_var = variable(True)
        self.app.set_status_threadsafe = mock.Mock()
        self.app.append_log_threadsafe = mock.Mock()
        self.app.mark_progress_done_threadsafe = mock.Mock()
        self.app.add_history_entry = mock.Mock()
        self.app.on_success = mock.Mock()
        self.app.on_download_error = mock.Mock()
        self.app.finish_cancelled_download = mock.Mock()
        for name, result in (("find_downloader", ["fake.exe"]), ("find_ffmpeg", "fake.exe")):
            patcher = mock.patch.object(APP, name, return_value=result)
            patcher.start()
            self.addCleanup(patcher.stop)

    def reported(self, paths):
        return "\n".join(APP.DOWNLOADED_FILE_PREFIX + json.dumps(str(path)) for path in paths)

    def run_download(self, paths, playlist=False, audio=True, returncode=0):
        self.app.run_download = mock.Mock(return_value=(returncode, self.reported(paths)))
        self.app.download_worker(
            "https://example.com/video", str(self.folder),
            "BEST_AUDIO" if audio else "BEST_AUTO", playlist, "Vidéo",
            APP.CookieSource.none()
        )

    def media(self, name):
        path = self.folder / name
        path.write_bytes(b"original media")
        return path

    def converter(self, path, conversion, ffmpeg):
        output = Path(path).with_suffix("." + conversion.lower())
        output.write_bytes(b"converted media")
        return str(output)

    def history(self):
        return [(Path(call.args[0]).name, call.args[1])
                for call in self.app.add_history_entry.call_args_list]

    def test_every_audio_in_a_playlist_is_converted_and_recorded(self):
        paths = [self.media("a.webm"), self.media("b.webm")]
        self.app.convert_audio_file = mock.Mock(side_effect=self.converter)
        self.run_download(paths, playlist=True)
        self.assertEqual(self.app.convert_audio_file.call_count, 2)
        self.assertEqual(self.history(), [("a.mp3", "MP3"), ("b.mp3", "MP3")])
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["a.mp3", "b.mp3"])
        self.assertEqual(self.app.on_success.call_args.kwargs["conversion_errors"], [])
        self.app.on_download_error.assert_not_called()

    def test_every_video_in_a_playlist_is_converted_and_recorded(self):
        paths = [self.media("a.webm"), self.media("b.webm")]
        self.app.video_conversion_var = variable("MP4")
        self.app.convert_video_file = mock.Mock(side_effect=self.converter)
        self.run_download(paths, playlist=True, audio=False)
        self.assertEqual(self.history(), [("a.mp4", "MP4"), ("b.mp4", "MP4")])

    def test_partial_conversion_failure_preserves_the_original_and_actual_history(self):
        paths = [self.media("a.webm"), self.media("b.webm"), self.media("c.webm")]

        def convert(path, conversion, ffmpeg):
            if Path(path).name == "b.webm":
                raise RuntimeError("conversion impossible")
            return self.converter(path, conversion, ffmpeg)

        self.app.convert_audio_file = mock.Mock(side_effect=convert)
        self.run_download(paths, playlist=True)
        self.assertEqual(self.history(), [("a.mp3", "MP3"), ("b.webm", "Aucune"), ("c.mp3", "MP3")])
        self.assertEqual(paths[1].read_bytes(), b"original media")
        warnings = self.app.on_success.call_args.kwargs["conversion_errors"]
        self.assertEqual(warnings, ["b.webm : conversion impossible"])

    def test_existing_file_is_found_without_a_new_file_or_folder_scan(self):
        path = self.media("Vidéo.mp4")
        unrelated = self.media("autre.mp4")
        self.run_download([path], audio=False)
        self.assertEqual(self.history(), [("Vidéo.mp4", "Aucune")])
        self.assertEqual(self.app.on_success.call_args.args, (str(self.folder), str(path)))
        self.assertEqual(unrelated.read_bytes(), b"original media")
        command = self.app.run_download.call_args.args[0]
        self.assertIn("after_move:STREAMDL_FILE:%(filepath)j", command)
        self.assertIn("--no-simulate", command)
        # --print implies quiet mode; destination lines are still needed
        # to remove the partial files when a real download is cancelled.
        self.assertIn("--no-quiet", command)

    def test_existing_audio_can_be_converted(self):
        path = self.media("Vidéo.webm")
        self.app.convert_audio_file = mock.Mock(side_effect=self.converter)
        self.run_download([path])
        self.assertEqual(self.history(), [("Vidéo.mp3", "MP3")])
        self.assertFalse(path.exists())

    def test_conversion_can_keep_the_original(self):
        path = self.media("Vidéo.webm")
        self.app.delete_audio_source_var = variable(False)
        self.app.convert_audio_file = mock.Mock(side_effect=self.converter)
        self.run_download([path])
        self.assertTrue(path.is_file())
        self.assertTrue(path.with_suffix(".mp3").is_file())

    def test_failed_conversion_is_reported_without_a_false_mp3_entry(self):
        path = self.media("Vidéo.webm")
        self.app.convert_audio_file = mock.Mock(side_effect=RuntimeError("échec ffmpeg"))
        self.run_download([path])
        self.assertEqual(self.history(), [("Vidéo.webm", "Aucune")])
        self.assertTrue(self.app.on_success.call_args.kwargs["conversion_errors"])
        self.assertEqual(path.read_bytes(), b"original media")

    def test_missing_final_path_is_an_error(self):
        self.media("autre.mp4")
        self.run_download([], audio=False)
        self.app.on_success.assert_not_called()
        self.app.add_history_entry.assert_not_called()
        self.app.on_download_error.assert_called_once()

    def test_failed_download_does_not_convert_completed_items(self):
        path = self.media("a.webm")
        self.app.convert_audio_file = mock.Mock()
        self.run_download([path], returncode=1)
        self.app.convert_audio_file.assert_not_called()
        self.app.on_success.assert_not_called()
        self.app.on_download_error.assert_called_once()

    def test_cancel_during_conversion_keeps_the_source_and_stops_the_playlist(self):
        paths = [self.media("a.webm"), self.media("b.webm")]

        def cancel(path, conversion, ffmpeg):
            self.app.cancel_requested = True
            return self.converter(path, conversion, ffmpeg)

        self.app.convert_audio_file = mock.Mock(side_effect=cancel)
        self.run_download(paths, playlist=True)
        self.app.finish_cancelled_download.assert_called_once()
        self.app.on_success.assert_not_called()
        self.app.add_history_entry.assert_not_called()
        self.assertEqual(self.app.convert_audio_file.call_count, 1)
        self.assertTrue(paths[0].is_file())

    def test_failed_ffmpeg_removes_its_incomplete_output_only(self):
        source = self.media("Vidéo.webm")

        def fail(cmd, output):
            Path(output).write_bytes(b"incomplete conversion")
            return 1

        self.app.run_ffmpeg = mock.Mock(side_effect=fail)
        for converter, fmt, extension in (
            (self.app.convert_audio_file, "MP3", ".mp3"),
            (self.app.convert_video_file, "MP4", ".mp4"),
        ):
            with self.assertRaises(RuntimeError):
                converter(str(source), fmt, "fake.exe")
            self.assertFalse(source.with_suffix(extension).exists())
            self.assertEqual(source.read_bytes(), b"original media")

    def test_report_parser_handles_accents_quotes_duplicates_and_ignores_foreign_files(self):
        valid = self.media("été 'concert'.mp4")
        with tempfile.TemporaryDirectory() as outside:
            foreign = Path(outside) / "étranger.mp4"
            foreign.write_bytes(b"do not touch")
            output = self.reported([valid, valid, foreign, self.folder / "absent.mp4"])
            output += "\nSTREAMDL_FILE:invalid json\nSTREAMDL_FILE:null\nSTREAMDL_FILE:123"
            self.assertEqual(APP.reported_download_files(output, self.folder), [str(valid)])
            self.assertEqual(foreign.read_bytes(), b"do not touch")


class ConversionWarningTests(ErgonomicsTestCase):
    def test_conversion_failure_shows_a_warning_and_keeps_the_file_accessible(self):
        self.start_ready_app()
        source = self.downloads / "Vidéo.webm"
        source.write_bytes(b"original")
        self.app.on_success(str(self.downloads), str(source), ["Vidéo.webm : échec"])
        self.assertIn("Conversion incomplète", self.app.status_label["text"])
        self.assertEqual(str(self.app.status_label["foreground"]), APP.palette["warning"])
        self.assertEqual(str(self.app.open_result_file_btn["state"]), "normal")
        self.assertTrue(self.dialogs)

    def test_hash_of_existing_file_preserves_the_conversion_warning(self):
        self.start_ready_app()
        source = self.downloads / "Vidéo.webm"
        source.write_bytes(b"original")
        self.app.create_sha256_var.set(True)
        self.app.on_success(str(self.downloads), str(source), ["Vidéo.webm : échec"])
        self.pump_until(lambda: "SHA-256 enregistré" in self.app.status_label["text"])
        self.assertTrue(Path(str(source) + ".sha256.txt").is_file())
        self.assertIn("Conversion incomplète", self.app.status_label["text"])
        self.assertEqual(str(self.app.status_label["foreground"]), APP.palette["warning"])

    def test_closing_cancels_pending_ui_updates(self):
        self.start_ready_app()
        late_update = mock.Mock()
        self.app.after_ui(1000, late_update)
        self.app.on_application_close()
        self.assertIsNone(self.app.after_ui(0, late_update))
        late_update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
