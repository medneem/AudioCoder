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

    def test_mp3_vbr_and_cbr_use_distinct_controls(self):
        for enabled in (True, False):
            job = ConversionJob(self.info, self.destination, "MP3",
                                ClipRange(0, 10, 10), "192k",
                                vbr_enabled=enabled, vbr_quality=1)
            cmd = ffmpeg_command(job, self.destination, Path("ffmpeg"))
            if enabled:
                self.assertEqual(cmd[cmd.index("-q:a") + 1], "1")
                self.assertNotIn("-b:a", cmd)
            else:
                self.assertEqual(cmd[cmd.index("-b:a") + 1], "192k")
                self.assertNotIn("-q:a", cmd)

    def test_opus_vbr_option_and_bitrate(self):
        target = output_path(self.source, self.root, "Opus")
        for enabled in (True, False):
            job = ConversionJob(self.info, target, "Opus", ClipRange(0, 10, 10),
                                bitrate="256k", vbr_enabled=enabled)
            cmd = ffmpeg_command(job, target, Path("ffmpeg"))
            self.assertEqual(cmd[cmd.index("-vbr") + 1],
                             "on" if enabled else "off")
            self.assertEqual(cmd[cmd.index("-b:a") + 1], "256k")

    def test_none_fade_selection_creates_only_requested_filters(self):
        for fade_in, fade_out, count, wanted in (
            ("none", "cub", 1, "t=out"),
            ("qsin", "none", 1, "t=in"),
            ("none", "none", 0, ""),
        ):
            with self.subTest(curves=(fade_in, fade_out)):
                job = ConversionJob(
                    self.info, self.destination, "MP3", ClipRange(0, 10, 10),
                    fade_enabled=True, fade_in_curve=fade_in,
                    fade_out_curve=fade_out)
                command = ffmpeg_command(job, self.destination, Path("ffmpeg"))
                if count:
                    self.assertIn("-af", command)
                    self.assertEqual(command[command.index("-af") + 1].count("afade="), count)
                    self.assertIn(wanted, command[command.index("-af") + 1])
                else:
                    self.assertNotIn("-af", command)

    def test_different_fade_in_and_fade_out_curves(self):
        job = ConversionJob(
            self.info, self.destination, "MP3", ClipRange(0, 10, 10),
            fade_enabled=True, fade_in_curve="qsin", fade_out_curve="cub")
        cmd = ffmpeg_command(job, self.destination, Path("ffmpeg"))
        filters = cmd[cmd.index("-af") + 1]
        self.assertIn("curve=qsin", filters)
        self.assertIn("curve=cub", filters)

    def test_invalid_options_are_rejected(self):
        params = (
            {"fade_in_curve": "not-a-filter"},
            {"fade_out_curve": "not-a-filter"},
            {"vbr_enabled": "on"},
            {"vbr_quality": 10},
        )
        for overrides in params:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                ConversionJob(self.info, self.destination, "MP3",
                              ClipRange(0, 10, 10), **overrides)

    def test_maximum_quality_parameters(self):
        for format_name, codec, quality in (
            ("FLAC", "flac", "12"),
            ("MP3", "libmp3lame", "0"),
            ("Opus", "libopus", "10"),
        ):
            with self.subTest(format=format_name):
                path = output_path(self.source, self.root, format_name)
                job = ConversionJob(self.info, path, format_name, ClipRange(0, 10, 10))
                cmd = ffmpeg_command(job, path, Path("ffmpeg"))
                self.assertIn(codec, cmd)
                self.assertEqual(cmd[cmd.index("-compression_level") + 1], quality)

    def test_logarithmic_fades_follow_trimmed_timeline(self):
        job = ConversionJob(self.info, self.destination, "MP3", ClipRange(2, 6, 10),
                            fade_enabled=True, fade_seconds=1)
        cmd = ffmpeg_command(job, self.destination, Path("ffmpeg"))
        self.assertIn("-af", cmd)
        self.assertEqual(cmd[cmd.index("-af") + 1],
                         "afade=t=in:st=0:d=1.000000:curve=log,"
                         "afade=t=out:st=3.000000:d=1.000000:curve=log")
        self.assertLess(cmd.index("-ss"), cmd.index("-i"))

    def test_fades_are_clamped_for_short_clips(self):
        job = ConversionJob(self.info, self.destination, "MP3", ClipRange(0, .6, 10),
                            fade_enabled=True, fade_seconds=3)
        cmd = ffmpeg_command(job, self.destination, Path("ffmpeg"))
        self.assertIn("st=0.300000:d=0.300000", cmd[cmd.index("-af") + 1])

    def test_invalid_fade_settings(self):
        for duration in (float("nan"), float("inf"), True, 0, -1, 21):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                ConversionJob(self.info, self.destination, "MP3", ClipRange(0, 4, 10),
                              fade_enabled=True, fade_seconds=duration)

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

    def test_existing_result_replaced_on_success(self):
        self.destination.write_bytes(b"previous conversion")
        with patch("audiocoder.converter.subprocess.Popen", side_effect=lambda cmd, **kw: FakeProcess(cmd)):
            ConversionRunner().run(self.job, ffmpeg=Path("ffmpeg"))
        self.assertEqual(self.destination.read_bytes(), b"encoded")
        self.assertEqual(self.source.read_bytes(), b"original")
        self.assertFalse(list(self.root.glob(".audiocoder-*")))

    def test_failed_conversion_preserves_existing_result(self):
        self.destination.write_bytes(b"previous conversion")
        with patch("audiocoder.converter.subprocess.Popen", side_effect=lambda cmd, **kw: FakeProcess(cmd, 1)):
            with self.assertRaises(ConversionError):
                ConversionRunner().run(self.job, ffmpeg=Path("ffmpeg"))
        self.assertEqual(self.destination.read_bytes(), b"previous conversion")
        self.assertFalse(list(self.root.glob(".audiocoder-*")))

    def test_failure_cleans_temp(self):
        with patch("audiocoder.converter.subprocess.Popen", side_effect=lambda cmd, **kw: FakeProcess(cmd, 1)):
            with self.assertRaises(ConversionError):
                ConversionRunner().run(self.job, ffmpeg=Path("ffmpeg"))
        self.assertFalse(self.destination.exists())
        self.assertFalse(list(self.root.glob(".audiocoder-*")))

    def test_cancel_before_start_keeps_existing_result(self):
        self.destination.write_bytes(b"existing")
        runner = ConversionRunner()
        runner.cancel()
        with self.assertRaises(ConversionCancelled):
            runner.run(self.job, ffmpeg=Path("ffmpeg"))
        self.assertEqual(self.destination.read_bytes(), b"existing")

    def test_reject_source_overwrite(self):
        with self.assertRaises(ValueError):
            ConversionJob(self.info, self.source, "FLAC", ClipRange(0, 10, 10))


if __name__ == "__main__":
    unittest.main()
