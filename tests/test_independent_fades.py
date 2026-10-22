"""Independent fade timings must match in preview, export and settings."""
import json
from pathlib import Path
import tempfile
import unittest

from audiocoder.converter import ConversionJob, ffmpeg_command
from audiocoder.fade import fade_filtergraph
from audiocoder.media import AudioInfo
from audiocoder.player import PlaybackEffects, PlaybackWindow, ffplay_command
from audiocoder.selection import ClipRange
from audiocoder.settings import DEFAULTS, load_settings, save_settings


class IndependentFadesTests(unittest.TestCase):
    def test_left_preview_still_fades_out_at_the_right_marker(self):
        graph = fade_filtergraph(
            10, 1, "qsin", "cub", mode="left", out_seconds=3)
        self.assertEqual(
            graph, "afade=t=in:st=0:d=1.000000:curve=qsin,"
                   "afade=t=out:st=7.000000:d=3.000000:curve=cub")

    def test_preview_and_export_use_same_independent_fade_lengths(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "original.wav"
            src.touch()
            info = AudioInfo(src, 20, "pcm_s16le", 44100, 2)
            job = ConversionJob(
                info, Path(temp) / "out.wav", "WAV", ClipRange(2, 12, 20),
                fade_enabled=True, fade_in_seconds=1,
                fade_out_seconds=3, fade_in_curve="qsin", fade_out_curve="cub")
            export = ffmpeg_command(job, job.destination, Path("ffmpeg"))
            effects = PlaybackEffects(enabled=True, seconds=1, out_seconds=3,
                                      in_curve="qsin", out_curve="cub",
                                      mode="left")
            preview = ffplay_command(src, PlaybackWindow(2, 12), Path("ffplay"), effects)
            export_filters = export[export.index("-af") + 1]
            preview_filters = preview[preview.index("-af") + 1]
            self.assertEqual(preview_filters, "asetpts=PTS-STARTPTS," + export_filters)

    def test_asymmetric_fades_shrink_proportionally_for_short_clip(self):
        graph = fade_filtergraph(2, 1, "tri", "cub", out_seconds=3)
        self.assertEqual(
            graph, "afade=t=in:st=0:d=0.500000:curve=tri,"
                   "afade=t=out:st=0.500000:d=1.500000:curve=cub")

    def test_none_fade_leaves_full_duration_to_other_effect(self):
        self.assertEqual(
            fade_filtergraph(2, 1, "none", "cub", out_seconds=3),
            "afade=t=out:st=0.000000:d=2.000000:curve=cub")
        self.assertEqual(
            fade_filtergraph(2, 4, "tri", "none", out_seconds=1),
            "afade=t=in:st=0:d=2.000000:curve=tri")

    def test_old_single_fade_setting_initializes_both_independent_values(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "config.json"
            config.write_text(json.dumps({"fade_seconds": 3.0}), encoding="utf-8")
            restored = load_settings(Path(temp))
            self.assertEqual(restored["fade_in_seconds"], 3)
            self.assertEqual(restored["fade_out_seconds"], 3)
            save_settings(restored, Path(temp))
            data = json.loads(config.read_text(encoding="utf-8"))
            self.assertNotIn("fade_seconds", data)
            self.assertEqual(data["fade_in_seconds"], 3)
            self.assertEqual(data["fade_out_seconds"], 3)

    def test_independent_timing_roundtrips_and_rejects_invalid_values(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            values = {**DEFAULTS, "fade_in_seconds": 0.5, "fade_out_seconds": 5.0}
            save_settings(values, p)
            self.assertEqual(load_settings(p), values)
            for name in ("fade_in_seconds", "fade_out_seconds"):
                for bad in (True, None, 0, 21, float("inf"), float("nan")):
                    with self.subTest(name=name, bad=bad), self.assertRaises(ValueError):
                        save_settings({**values, name: bad}, p)


if __name__ == "__main__":
    unittest.main()
