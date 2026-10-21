"""Bounded background work for rapidly changing waveform zoom/pan requests."""
import threading
import time
import unittest

from audiocoder.waveform_jobs import LatestOnlyWorker


class LatestWaveformWorkerTests(unittest.TestCase):
    def test_rapid_requests_only_decode_first_and_latest(self):
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()
        processed, published = [], []

        def work(request):
            processed.append(request)
            if request == 1:
                started.set()
                self.assertTrue(release.wait(5))
            return request * 10

        def publish(request, result):
            published.append((request, result))
            if request == 25:
                finished.set()

        worker = LatestOnlyWorker(work, publish)
        try:
            worker.submit(1)
            self.assertTrue(started.wait(3), "Initial decoder didn't start")
            for i in range(2, 26):
                worker.submit(i)
            self.assertEqual(processed, [1], "Overlapping FFmpeg jobs started")
            release.set()
            self.assertTrue(finished.wait(5), "Latest requested view was not decoded")
            self.assertEqual(processed, [1, 25])
            self.assertEqual(published, [(25, 250)])
        finally:
            release.set()
            worker.close()

    def test_clear_discards_pending_and_prevents_old_result_publication(self):
        started = threading.Event()
        release = threading.Event()
        processed, published = [], []

        def work(request):
            processed.append(request)
            started.set()
            release.wait(5)
            return request

        worker = LatestOnlyWorker(work, lambda req, result: published.append(result))
        try:
            worker.submit(1)
            self.assertTrue(started.wait(3))
            worker.submit(2)
            worker.clear()
            release.set()
            self.assertTrue(worker.wait_idle(5))
            self.assertEqual(processed, [1])
            self.assertEqual(published, [])
        finally:
            release.set()
            worker.close()

    def test_close_rejects_new_requests_and_suppresses_results(self):
        started = threading.Event()
        release = threading.Event()
        published = []
        def work(job):
            started.set()
            release.wait(5)
            return job
        worker = LatestOnlyWorker(work, lambda req, result: published.append(result))
        worker.submit(1)
        self.assertTrue(started.wait(3))
        worker.close()
        worker.submit(2)
        release.set()
        self.assertTrue(worker.wait_idle(5))
        self.assertEqual(published, [])

    def test_failure_is_reported_without_stopping_future_jobs(self):
        errors, results = [], []
        reported = threading.Event()

        def work(job):
            if job == 1:
                raise ValueError("bad FFmpeg audio")
            return job * 2

        def error(job, exc):
            errors.append((job, str(exc)))
            reported.set()

        worker = LatestOnlyWorker(
            work, lambda job, result: results.append((job, result)), error)
        try:
            worker.submit(1)
            self.assertTrue(reported.wait(5))
            self.assertTrue(worker.wait_idle(5))
            worker.submit(2)
            self.assertTrue(worker.wait_idle(5))
            self.assertEqual(errors, [(1, "bad FFmpeg audio")])
            self.assertEqual(results, [(2, 4)])
        finally:
            worker.close()


if __name__ == "__main__":
    unittest.main()
