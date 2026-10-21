import tempfile
import array
import math
import wave
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

    def test_seeked_detail_recalculates_visible_time_window(self):
        cmd = waveform_command(Path("Музыка.flac"), Path("ffmpeg"), 1600, 120,
                               start=48.5, duration=12.25)
        self.assertEqual(cmd[cmd.index("-ss") + 1], "48.500000")
        self.assertEqual(cmd[cmd.index("-t") + 1], "12.250000")
        self.assertLess(cmd.index("-ss"), cmd.index("-i"))
        self.assertLess(cmd.index("-t"), cmd.index("-filter_complex"))
        self.assertIn("showwavespic=s=1600x120", " ".join(cmd))

    def test_invalid_detail_window_fails_fast(self):
        for start, duration in ((-1, 1), (1, 0), (1, float("nan")),
                                (float("inf"), 3), (0, -2)):
            with self.subTest(start=start, duration=duration), self.assertRaises(ValueError):
                waveform_command(Path("x.flac"), Path("ffmpeg"), 800, 120,
                                 start=start, duration=duration)

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
    def test_zoomed_waveform_decodes_actual_selected_segment(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "тишина-и-звук.wav"
            rate = 44100
            audio = array.array("h", [0] * rate + [
                int(15000 * math.sin(2 * math.pi * 440 * i / rate))
                for i in range(rate)
            ])
            with wave.open(str(source), "wb") as dest:
                dest.setnchannels(1)
                dest.setsampwidth(2)
                dest.setframerate(rate)
                dest.writeframes(audio.tobytes())
            silence = extract_waveform(source, width=256, height=64,
                                       start=.1, duration=.7)
            tone = extract_waveform(source, width=256, height=64,
                                    start=1.2, duration=.6)
            self.assertLess(max(silence), .03)
            self.assertGreater(max(tone), .05)

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
