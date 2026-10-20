"""Run with real FFmpeg when available. No external media fixtures."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from audiocoder.media import probe_audio
from audiocoder.converter import ConversionJob, ConversionRunner, output_path
from audiocoder.selection import ClipRange


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/FFprobe unavailable")
class ConversionIntegrationTests(unittest.TestCase):
    def test_trim_lossless_flac_to_mp3(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "Тест.flac"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                "-i", "sine=frequency=440:duration=3", "-c:a", "flac", "-n", str(source)
            ], check=True, capture_output=True)
            info = probe_audio(source)
            result = ConversionRunner().run(ConversionJob(
                info, output_path(source, root, "MP3"),
                "MP3", ClipRange(1.0, 2.0, info.duration)))
            result_info = probe_audio(result)
            self.assertGreater(result_info.duration, 0.9)
            self.assertLess(result_info.duration, 1.1)
            self.assertEqual(source.read_bytes()[:4], b"fLaC")


if __name__ == "__main__":
    unittest.main()
