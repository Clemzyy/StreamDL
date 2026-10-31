import tempfile
import unittest
from pathlib import Path

import build_exe


class BuildArgumentsTests(unittest.TestCase):
    def data_names(self, full):
        return {path.name for path in build_exe.data_files(full)}

    def test_light_build_ships_no_tool(self):
        names = self.data_names(full=False)
        self.assertIn("download.ico", names)
        self.assertIn("social_github.png", names)
        self.assertFalse({"yt-dlp.exe", "ffmpeg.exe", "deno.exe", "download.png"} & names)

    def test_full_build_embeds_the_tools(self):
        names = self.data_names(full=True)
        self.assertTrue({"yt-dlp.exe", "ffmpeg.exe", "deno.exe", "DENO_LICENSE.md"} <= names)
        self.assertNotIn("download.png", names)

    def test_nuitka_unpacks_once_into_a_per_build_cache(self):
        source = build_exe.find_latest_source()
        arguments = build_exe.nuitka_arguments(source, full=False, output_dir=Path("out"))
        self.assertIn("--onefile", arguments)
        self.assertIn("--onefile-cache-mode=cached", arguments)
        spec = next(a for a in arguments if a.startswith("--onefile-tempdir-spec="))
        self.assertRegex(spec, r"\{CACHE_DIR\}/StreamDL/app/[0-9a-f]{12}$")
        self.assertIn("--windows-console-mode=disable", arguments)
        self.assertIn(f"--file-version={build_exe.source_version_number(source)}", arguments)
        self.assertRegex(build_exe.source_version_number(source), r"^\d+\.\d+\.0\.0$")
        self.assertFalse(any("yt-dlp.exe" in a for a in arguments))

    def test_build_id_follows_content_and_toolchain(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder) / "data.txt"
            data.write_text("a")
            first = build_exe.build_id([data], "nuitka 4.3.3")
            self.assertEqual(first, build_exe.build_id([data], "nuitka 4.3.3"))
            self.assertNotEqual(first, build_exe.build_id([data], "nuitka 4.4.0"))
            data.write_text("b")
            self.assertNotEqual(first, build_exe.build_id([data], "nuitka 4.3.3"))


if __name__ == "__main__":
    unittest.main()
