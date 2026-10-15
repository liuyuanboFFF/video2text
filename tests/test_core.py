import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from video2text import fetch, output
from video2text.models import Segment, VideoMeta

SAMPLE_VTT = """WEBVTT

00:00:00.000 --> 00:00:02.000
大家好

00:00:02.000 --> 00:00:04.000
大家好今天我们来聊聊

00:00:04.000 --> 00:00:06.000
<c>今天天气</c>不错

NOTE 这行应当被忽略
"""


def meta():
    return VideoMeta(
        id="BV1test",
        title="测试 视频/标题",
        uploader="某人",
        duration=1465,
        webpage_url="https://example.com/v",
        extractor="Bilibili",
    )


def segs():
    return [Segment(0.0, 2.0, "第一句"), Segment(2.0, 65.5, "第二句")]


class TestVttParsing(unittest.TestCase):
    def _parse(self):
        fd, path = tempfile.mkstemp(suffix=".vtt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(SAMPLE_VTT)
        try:
            return fetch.parse_vtt(path)
        finally:
            os.unlink(path)

    def test_rolling_captions_merged(self):
        got = self._parse()
        self.assertEqual(len(got), 2, "滚动字幕应被合并为 2 段")
        self.assertEqual(got[0].text, "大家好今天我们来聊聊")
        self.assertEqual(got[0].start, 0.0)
        self.assertEqual(got[0].end, 4.0)

    def test_tags_stripped(self):
        got = self._parse()
        self.assertEqual(got[1].text, "今天天气不错")

    def test_note_block_ignored(self):
        got = self._parse()
        self.assertFalse(any("NOTE" in s.text for s in got))


class TestTimeParsing(unittest.TestCase):
    def test_hms_and_ms(self):
        self.assertAlmostEqual(fetch._parse_ts("00:01:02.500"), 62.5)
        self.assertAlmostEqual(fetch._parse_ts("01:02.250"), 62.25)
        self.assertAlmostEqual(fetch._parse_ts("00:00:00,000"), 0.0)


class TestFilename(unittest.TestCase):
    def test_unsafe_chars_replaced(self):
        self.assertNotIn("/", output.safe_filename("a/b"))
        self.assertTrue(output.safe_filename(""))
        self.assertTrue(len(output.safe_filename("啊" * 200)) <= 60)


class TestWriters(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def _read(self, name):
        with open(os.path.join(self.dir, name), encoding="utf-8") as f:
            return f.read()

    def test_markdown_frontmatter_and_body(self):
        p = os.path.join(self.dir, "a.md")
        output.write_markdown(meta(), segs(), p, source="whisper:medium", model="medium")
        body = self._read("a.md")
        self.assertIn("title: ", body)
        self.assertIn("transcript_source: \"whisper:medium\"", body)
        self.assertIn("[00:00] 第一句", body)
        self.assertIn("[00:02] 第二句", body)
        self.assertIn("可能存在识别误差", body)

    def test_markdown_no_frontmatter(self):
        p = os.path.join(self.dir, "b.md")
        output.write_markdown(meta(), segs(), p, frontmatter=False, source="subtitle:x")
        self.assertTrue(self._read("b.md").startswith("# "))

    def test_srt_format(self):
        p = os.path.join(self.dir, "c.srt")
        output.write_srt(segs(), p)
        body = self._read("c.srt")
        self.assertIn("1\n00:00:00,000 --> 00:00:02,000\n第一句", body)
        self.assertIn("00:01:05,500", body)

    def test_json_roundtrip(self):
        p = os.path.join(self.dir, "d.json")
        output.write_json(meta(), segs(), p, source="subtitle:x")
        data = json.loads(self._read("d.json"))
        self.assertEqual(data["title"], "测试 视频/标题")
        self.assertEqual(len(data["segments"]), 2)
        self.assertEqual(data["segments"][1]["text"], "第二句")

    def test_text_plain(self):
        p = os.path.join(self.dir, "e.txt")
        output.write_text(segs(), p, with_timestamps=False)
        self.assertEqual(self._read("e.txt").strip(), "第一句\n第二句")


if __name__ == "__main__":
    unittest.main(verbosity=2)
