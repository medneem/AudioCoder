import tempfile
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import Mock, patch

from audiocoder.waveform import extract_waveform, peak_columns, waveform_command


class WaveformTests(unittest.TestCase):
    def test_command_is_bounded_to_one_gray_frame(self):
        args = waveform_command(Path("Музыка.flac"), Path("ffmpeg"), 960, 120)
        self.assertIn("showwavespic=s=960x120", " ".join(args))
        self.assertIn("rawvideo", args)
        self.assertIn("gray", args)
        self.assertEqual(args[-1], "pipe:1")

    def test_peaks_silence_and_signal(self):
        # image 2 x 4: full-height first column, empty second
        raw = bytes([255, 0, 0, 0, 0, 0, 255, 0])
        peaks = peak_columns(raw, 2, 4)
        self.assertAlmostEqual(peaks[0], 0.75)
        self.assertEqual(peaks[1], 0.0)

    def test_incomplete_frame(self):
        with self.assertRaises(ValueError):
            peak_columns(b"\x00", 960, 120)

    def test_ffmpeg_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "song.flac"
            source.touch()
            broken = Mock(returncode=1, stdout=b"", stderr=b"bad file")
            with patch("audiocoder.waveform.subprocess.run", return_value=broken):
                with self.assertRaisesRegex(ValueError, "bad file"):
                    extract_waveform(source, Path("ffmpeg"))

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg unavailable")
    def test_real_waveform_for_tone(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "Тон.wav"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                "-c:a", "pcm_s16le", "-n", str(source),
            ], check=True, capture_output=True)
            peaks = extract_waveform(source, width=128, height=64)
            self.assertEqual(len(peaks), 128)
            self.assertGreater(max(peaks), 0.05)
            self.assertTrue(all(0 <= peak <= 1 for peak in peaks))


if __name__ == "__main__":
    unittest.main()
