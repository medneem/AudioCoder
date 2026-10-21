import json
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from audiocoder.media import probe_audio


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "Тестовый альбом.flac"
        self.path.write_bytes(b"audio placeholder")

    def test_unicode_source_and_metadata(self):
        sample = {"format": {"duration": "123.456"}, "streams": [
            {"codec_name": "flac", "sample_rate": "44100", "channels": 2}]}
        with patch("audiocoder.media.subprocess.run", return_value=Mock(returncode=0, stdout=json.dumps(sample)) ) as run:
            info = probe_audio(self.path, Path("ffprobe"))
        self.assertEqual(info.duration, 123.456)
        self.assertEqual(info.codec, "flac")
        self.assertEqual(info.sample_rate, 44100)
        self.assertEqual(info.channels, 2)
        self.assertEqual(run.call_args.args[0][-1], str(self.path.resolve()))
        self.assertEqual(run.call_args.kwargs["creationflags"],
                         getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def test_no_audio_stream(self):
        with patch("audiocoder.media.subprocess.run", return_value=Mock(returncode=0, stdout='{"streams":[]}')):
            with self.assertRaises(ValueError):
                probe_audio(self.path, Path("ffprobe"))

    def test_ffprobe_failed(self):
        with patch("audiocoder.media.subprocess.run", return_value=Mock(returncode=1, stderr="broken")):
            with self.assertRaisesRegex(ValueError, "broken"):
                probe_audio(self.path, Path("ffprobe"))

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            probe_audio(self.path.with_name("not-here.flac"), Path("ffprobe"))


if __name__ == "__main__":
    unittest.main()
