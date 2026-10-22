"""Unit tests of FFplay seek boundaries, CLI and asynchronous transport."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from audiocoder.player import AudioPlayer, PlaybackWindow, PlaybackEffects, ffplay_command, listening_window


class PlaybackTests(unittest.TestCase):
    def test_button_plays_entire_selection(self):
        for mode in ("selection",):
            with self.subTest(mode=mode):
                self.assertEqual(listening_window(mode, 80, 190), PlaybackWindow(80, 190))

    def test_left_previews_entire_selection_from_left_marker(self):
        self.assertEqual(listening_window("left", 80, 190), PlaybackWindow(80, 190))
        self.assertEqual(listening_window("left", 80, 83), PlaybackWindow(80, 83))
        self.assertEqual(listening_window("selection", 80, 190), PlaybackWindow(80, 190))

    def test_right_previews_last_one_second(self):
        self.assertEqual(listening_window("right", 80, 190), PlaybackWindow(189, 190))

    def test_short_right_preview_clamped_to_left(self):
        self.assertEqual(listening_window("right", 85.7, 86), PlaybackWindow(85.7, 86))
        self.assertEqual(listening_window("right", 0, 2), PlaybackWindow(1, 2))

    def test_invalid(self):
        for args in (("right", 4, 4), ("left", 3, 2), ("selection", -1, 4),
                     ("right", float("nan"), 5), ("other", 0, 10)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                listening_window(*args)

    def test_selected_preview_uses_same_fade_filter_as_export(self):
        from audiocoder.fade import fade_filtergraph
        effects = PlaybackEffects(
            enabled=True, seconds=1.0, in_curve="qsin", out_curve="cub")
        window = PlaybackWindow(12, 22)
        cmd = ffplay_command(Path("Музыка.flac"), window, Path("ffplay"), effects)
        self.assertIn("-af", cmd)
        self.assertEqual(
            cmd[cmd.index("-af") + 1],
            "asetpts=PTS-STARTPTS," + fade_filtergraph(10, 1, "qsin", "cub"))
        self.assertIn("afade=t=in:st=0:d=1.000000:curve=qsin",
                      cmd[cmd.index("-af") + 1])
        self.assertIn("afade=t=out:st=9.000000:d=1.000000:curve=cub",
                      cmd[cmd.index("-af") + 1])

    def test_left_preview_applies_both_fades_and_right_preview_only_fades_out(self):
        for mode, window, has_in in (
            ("left", PlaybackWindow(20, 25), True),
            ("right", PlaybackWindow(24, 25), False),
        ):
            with self.subTest(mode=mode):
                effects = PlaybackEffects(
                    enabled=True, seconds=1, in_curve="tri",
                    out_curve="log", mode=mode)
                cmd = ffplay_command(Path("song.flac"), window, Path("ffplay"), effects)
                fade = cmd[cmd.index("-af") + 1]
                self.assertIn("t=out", fade)
                self.assertEqual("t=in" in fade, has_in)

    def test_disabled_or_none_fades_are_absent_in_preview(self):
        win = PlaybackWindow(0, 5)
        source, exe = Path("source.flac"), Path("ffplay")
        for effects in (
            PlaybackEffects(enabled=False),
            PlaybackEffects(enabled=True, in_curve="none", out_curve="none"),
        ):
            with self.subTest(effects=effects):
                self.assertNotIn("-af", ffplay_command(source, win, exe, effects))
        for curve in ("in_curve", "out_curve"):
            settings = dict(enabled=True, in_curve="log", out_curve="cub")
            settings[curve] = "none"
            cmd = ffplay_command(source, win, exe, PlaybackEffects(**settings))
            filters = cmd[cmd.index("-af") + 1]
            self.assertEqual(filters.count("afade="), 1)

    def test_seeking_requires_zero_based_audio_timestamps_for_fades(self):
        """FFplay retains source PTS after -ss; without asetpts right preview is mute."""
        for mode, window in (
            ("selection", PlaybackWindow(80, 100)),
            ("left", PlaybackWindow(80, 85)),
            ("right", PlaybackWindow(99, 100)),
        ):
            with self.subTest(mode=mode):
                effects = PlaybackEffects(
                    enabled=True, seconds=1, in_curve="log",
                    out_curve="log", mode=mode)
                command = ffplay_command(Path("song.flac"), window,
                                         Path("ffplay"), effects)
                self.assertIn("-af", command)
                graph = command[command.index("-af") + 1]
                self.assertTrue(
                    graph.startswith("asetpts=PTS-STARTPTS,"),
                    f"Seeked {mode} preview keeps nonzero timestamps: {graph}")
                self.assertEqual(command[command.index("-ss") + 1],
                                 f"{window.start:.6f}")
                self.assertEqual(command[command.index("-t") + 1],
                                 f"{window.duration:.6f}")

    @unittest.skipUnless(shutil.which("ffplay") and shutil.which("ffmpeg"),
                         "FFplay and FFmpeg required for live audio regression")
    def test_real_ffplay_right_preview_is_audible_after_nonzero_seek(self):
        """Output after a seek must not be -inf dB (all samples silenced)."""
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "Проверка-затухания.wav"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=7",
                "-c:a", "pcm_s16le", "-y", str(source),
            ], capture_output=True, check=True, timeout=15)
            cmd = ffplay_command(
                source, PlaybackWindow(5, 6), Path(shutil.which("ffplay")),
                PlaybackEffects(enabled=True, seconds=1,
                                in_curve="log", out_curve="log", mode="right"))
            cmd[cmd.index("-loglevel") + 1] = "info"
            cmd[cmd.index("-af") + 1] += ",ashowinfo,astats=metadata=1:reset=0"
            env = {**os.environ, "SDL_AUDIODRIVER": "dummy",
                   "SDL_VIDEODRIVER": "dummy"}
            result = subprocess.run(
                cmd, env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.assertEqual(result.returncode, 0, result.stderr[-1200:])
            self.assertRegex(result.stderr, r"n:0 pts:0 pts_time:0\b")
            rms = re.search(r"RMS level dB:\s*([-\d.]+)", result.stderr)
            self.assertIsNotNone(rms, result.stderr[-1600:])
            self.assertGreater(float(rms.group(1)), -55,
                               "Seeked right preview was silent")

    def test_ffplay_command(self):
        cmd = ffplay_command(Path("Музыка.flac"), PlaybackWindow(189, 190), Path("ffplay"))
        self.assertEqual(cmd[cmd.index("-ss") + 1], "189.000000")
        self.assertEqual(cmd[cmd.index("-t") + 1], "1.000000")
        self.assertIn("-nodisp", cmd)
        self.assertIn("-autoexit", cmd)
        self.assertIn("-vn", cmd)
        self.assertEqual(cmd[-1], str(Path("Музыка.flac")))


class DummyProcess:
    def __init__(self):
        self.killed = False
        self.returncode = None

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


class PlayerTransportTests(unittest.TestCase):
    def test_play_and_stop(self):
        player = AudioPlayer()
        spawned = []
        event = threading.Event()
        def popen(*args, **kwargs):
            p = DummyProcess()
            spawned.append(p)
            event.set()
            return p
        with patch("audiocoder.player.find_binary", return_value=Path("ffplay")), patch(
            "audiocoder.player.subprocess.Popen", side_effect=popen
        ):
            token = player.play(Path("song.flac"), PlaybackWindow(10, 20))
            self.assertTrue(event.wait(2))
            self.assertEqual(player.generation, token)
            self.assertIsNotNone(player.position())
            player.stop()
        self.assertTrue(spawned[0].killed)
        self.assertIsNone(player.position())

    def test_transport_launches_ffplay_with_the_selected_fade_filters(self):
        player = AudioPlayer()
        launched = threading.Event()
        commands = []

        def spawn(command, **kwargs):
            commands.append(command)
            launched.set()
            return DummyProcess()

        effects = PlaybackEffects(enabled=True, seconds=.5,
                                  in_curve="none", out_curve="hsin")
        with patch("audiocoder.player.find_binary", return_value=Path("ffplay")), \
             patch("audiocoder.player.subprocess.Popen", side_effect=spawn):
            player.play(Path("song.flac"), PlaybackWindow(4, 8),
                        effects=effects)
            self.assertTrue(launched.wait(3), "FFplay did not launch")
            player.stop()
        self.assertEqual(len(commands), 1)
        self.assertEqual(
            commands[0][commands[0].index("-af") + 1],
            "asetpts=PTS-STARTPTS,afade=t=out:st=3.500000:d=0.500000:curve=hsin")
        self.assertNotIn("t=in", commands[0][commands[0].index("-af") + 1])

    def test_stale_launch_is_cancelled(self):
        player = AudioPlayer()
        entered = threading.Event()
        resume = threading.Event()
        exited = threading.Event()
        def find(name):
            entered.set()
            resume.wait(2)
            exited.set()
            return Path(name)
        with patch("audiocoder.player.find_binary", side_effect=find), patch(
            "audiocoder.player.subprocess.Popen"
        ) as popen:
            player.play(Path("song.flac"), PlaybackWindow(1, 5))
            self.assertTrue(entered.wait(2))
            player.stop()
            resume.set()
            self.assertTrue(exited.wait(2))
            # Let the worker finish its post-search generation check.
            with player._lock:
                pass
            popen.assert_not_called()

    def test_missing_ffplay_reports_error(self):
        player = AudioPlayer()
        completed = threading.Event()
        errors = []
        def on_error(generation, message):
            errors.append((generation, message))
            completed.set()
        with patch("audiocoder.player.find_binary", side_effect=FileNotFoundError("ffplay missing")):
            token = player.play(Path("song.flac"), PlaybackWindow(0, 10), on_error)
            self.assertTrue(completed.wait(2))
        self.assertEqual(errors, [(token, "ffplay missing")])
        self.assertIsNone(player.position())

    def test_new_play_kills_old(self):
        player = AudioPlayer()
        procs = []
        event = threading.Event()
        def popen(*args, **kwargs):
            p = DummyProcess()
            procs.append(p)
            event.set()
            return p
        with patch("audiocoder.player.find_binary", return_value=Path("ffplay")), patch(
            "audiocoder.player.subprocess.Popen", side_effect=popen
        ):
            player.play(Path("one.flac"), PlaybackWindow(0, 10))
            self.assertTrue(event.wait(2))
            event.clear()
            player.play(Path("two.flac"), PlaybackWindow(1, 10))
            self.assertTrue(event.wait(2))
            player.stop()
        self.assertTrue(procs[0].killed)
        self.assertTrue(procs[1].killed)


    def test_player_exposes_success_or_failure_on_natural_exit(self):
        player = AudioPlayer()
        processes = [DummyProcess(), DummyProcess()]
        launched = threading.Event()
        def popen(*args, **kwargs):
            result = processes.pop(0)
            launched.set()
            return result
        first = processes[0]
        second = processes[1]
        with patch("audiocoder.player.find_binary", return_value=Path("ffplay")), \
             patch("audiocoder.player.subprocess.Popen", side_effect=popen):
            player.play(Path("song.flac"), PlaybackWindow(0, 2))
            self.assertTrue(launched.wait(2))
            first.returncode = 1
            self.assertIsNone(player.position())
            self.assertEqual(player.last_returncode, 1)
            launched.clear()
            player.play(Path("song.flac"), PlaybackWindow(0, 2))
            self.assertTrue(launched.wait(2))
            self.assertIsNone(player.last_returncode)
            second.returncode = 0
            self.assertIsNone(player.position())
            self.assertEqual(player.last_returncode, 0)
            player.stop()
            self.assertIsNone(player.last_returncode)


if __name__ == "__main__":
    unittest.main()
