from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from audiocoder.converter import (ConversionRunner, ConversionJob, ConversionCancelled,
                                  ConversionError, ffmpeg_command, output_path)
from audiocoder.media import AudioInfo
from audiocoder.selection import ClipRange


class FakeProcess:
    def __init__(self, cmd, returncode=0, write_data=True):
        self.returncode = returncode
        self.stdout = iter(["out_time_us=1000000\n", "out_time_ms=1500000\n", "progress=end\n"])
        if write_data:
            Path(cmd[-1]).write_bytes(b"encoded")
        self.killed = False

    def wait(self):
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True


class ConverterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "Моя музыка.flac"
        self.source.write_bytes(b"original")
        self.info = AudioInfo(self.source, 10.0, "flac", 44100, 2)
        self.destination = output_path(self.source, self.root, "MP3")
        self.job = ConversionJob(self.info, self.destination, "MP3", ClipRange(2, 6, 10), "320k")

    def test_command_uses_precise_trim_and_codec(self):
        cmd = ffmpeg_command(self.job, self.destination, Path("ffmpeg"))
        self.assertEqual(cmd[cmd.index("-ss") + 1], "2.000000")
        self.assertEqual(cmd[cmd.index("-t") + 1], "4.000000")
        self.assertEqual(cmd[cmd.index("-b:a") + 1], "320k")
        self.assertIn("libmp3lame", cmd)
        self.assertIn("-n", cmd)
        self.assertNotIn("-y", cmd)

    def test_formats(self):
        for fmt, codec in (("FLAC", "flac"), ("WAV", "pcm_s24le"),
                           ("Opus", "libopus"), ("MP3", "libmp3lame")):
            with self.subTest(fmt=fmt):
                destination = output_path(self.source, self.root, fmt)
                job = ConversionJob(self.info, destination, fmt, ClipRange(0, 10, 10))
                self.assertIn(codec, ffmpeg_command(job, destination, Path("ffmpeg")))

    def test_runner_finishes_and_never_touches_source(self):
        values = []
        with patch("audiocoder.converter.subprocess.Popen", side_effect=lambda cmd, **kw: FakeProcess(cmd)):
            result = ConversionRunner().run(self.job, values.append, Path("ffmpeg"))
        self.assertEqual(result, self.destination)
        self.assertEqual(result.read_bytes(), b"encoded")
        self.assertEqual(self.source.read_bytes(), b"original")
        self.assertEqual(values[-1], 1.0)
        self.assertFalse(list(self.root.glob(".audiocoder-*")))

    def test_existing_result_not_overwritten(self):
        self.destination.write_bytes(b"preserve")
        with self.assertRaises(FileExistsError):
            ConversionRunner().run(self.job, ffmpeg=Path("ffmpeg"))
        self.assertEqual(self.destination.read_bytes(), b"preserve")

    def test_failure_cleans_temp(self):
        with patch("audiocoder.converter.subprocess.Popen", side_effect=lambda cmd, **kw: FakeProcess(cmd, 1)):
            with self.assertRaises(ConversionError):
                ConversionRunner().run(self.job, ffmpeg=Path("ffmpeg"))
        self.assertFalse(self.destination.exists())
        self.assertFalse(list(self.root.glob(".audiocoder-*")))

    def test_cancel_before_start(self):
        runner = ConversionRunner()
        runner.cancel()
        with self.assertRaises(ConversionCancelled):
            runner.run(self.job, ffmpeg=Path("ffmpeg"))
        self.assertFalse(self.destination.exists())

    def test_reject_source_overwrite(self):
        with self.assertRaises(ValueError):
            ConversionJob(self.info, self.source, "FLAC", ClipRange(0, 10, 10))


if __name__ == "__main__":
    unittest.main()
