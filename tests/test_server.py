import tempfile
import time
import unittest
from pathlib import Path

from server import Index, mark_message


SAMPLE_CHAT = """<!doctype html>
<html><body>
<div class="message"><div class="received"><span class="sender">Alice</span><span class="timestamp">Sep 02, 2026 10:00:00 AM</span><span>Hello world</span></div></div>
</body></html>
"""


class IndexTests(unittest.TestCase):
    def test_selected_archive_is_indexed(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory)
            (archive / "Alice.html").write_text(SAMPLE_CHAT, encoding="utf-8")
            index = Index()

            index.select_archive(archive)
            deadline = time.monotonic() + 2
            while not index.ready and time.monotonic() < deadline:
                time.sleep(0.01)

            self.assertTrue(index.ready)
            self.assertEqual(index.archive_dir, archive)
            self.assertEqual(index.chats[0]["name"], "Alice")
            self.assertEqual(index.search("hello")[0]["sender"], "Alice")

    def test_mark_message_adds_selected_anchor(self):
        marked = mark_message(SAMPLE_CHAT, 0)
        self.assertIn('id="selected-message"', marked)


if __name__ == "__main__":
    unittest.main()
