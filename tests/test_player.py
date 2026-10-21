"""Unit tests of FFplay seek boundaries, CLI and asynchronous transport."""
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from audiocoder.player import AudioPlayer, PlaybackWindow, ffplay_command, listening_window


class PlaybackTests(unittest.TestCase):
    def test_selection_and_left_play_until_right(self):
        for mode in ("selection", "left"):
            with self.subTest(mode=mode):
                self.assertEqual(listening_window(mode, 80, 190), PlaybackWindow(80, 190))

    def test_right_previews_last_one_second(self):
        self.assertEqual(listening_window("right", 80, 190), PlaybackWindow(189, 190))

    def test_short_right_preview_clamped_to_left(self):
        self.assertEqual(listening_window("right", 85.7, 86), PlaybackWindow(85.7, 86))
        self.assertEqual(listening_window("right", 0, 2), PlaybackWindow(0, 2))

    def test_invalid(self):
        for args in (("right", 4, 4), ("left", 3, 2), ("selection", -1, 4),
                     ("right", float("nan"), 5), ("other", 0, 10)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                listening_window(*args)

    def test_ffplay_command(self):
        cmd = ffplay_command(Path("Музыка.flac"), PlaybackWindow(185, 190), Path("ffplay"))
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


if __name__ == "__main__":
    unittest.main()
