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
    def test_fade_in_out_is_applied_to_exported_audio(self):
        import array
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "сигнал.wav"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                "-i", "sine=frequency=440:duration=3", "-c:a", "pcm_s16le",
                "-y", str(source)
            ], check=True, capture_output=True)
            info = probe_audio(source)
            result = ConversionRunner().run(ConversionJob(
                info, output_path(source, root, "WAV"),
                "WAV", ClipRange(1, 2, info.duration),
                fade_enabled=True, fade_seconds=0.3))
            # Decode 16-bit mono for a platform-independent RMS comparison.
            raw = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(result),
                "-ac", "1", "-ar", "44100", "-f", "s16le", "pipe:1"
            ], capture_output=True, check=True).stdout
            samples = array.array("h")
            samples.frombytes(raw)
            def rms(start, end):
                section = samples[int(start * 44100):int(end * 44100)]
                return (sum(int(v) ** 2 for v in section) / len(section)) ** .5
            center = rms(.4, .6)
            self.assertGreater(center, 1000)
            self.assertLess(rms(0, .025), center * .4)
            self.assertLess(rms(.975, 1), center * .4)

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
