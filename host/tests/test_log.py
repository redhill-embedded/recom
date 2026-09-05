"""Tests for recom.log -- the framing/ordering the host applies to a
device's raw log blob.

Stdlib unittest, no third-party test runner needed:

    cd host && python -m unittest discover -s tests

The fixtures deliberately mirror Polaris util/log's rendered line format
(``#<ts>-<LEVEL>: [<task>] <msg>\\n``), including a ring buffer that has
wrapped, so this doubles as the conformance check for that contract.
"""

import unittest

from recom import log
from recom.log import Record, parse, format_log, validate


def line(ts, msg, level="INFO", task="T"):
    return "#%d-%s: [%s] %s\n" % (ts, level, task, msg)


def blob(*lines):
    return "".join(lines).encode("utf-8")


class ParseTests(unittest.TestCase):
    def test_clean_blob_yields_every_record_in_order(self):
        raw = blob(line(0, "a"), line(1, "b"), line(2, "c"))
        self.assertEqual(parse(raw), [
            Record(0, "#0-INFO: [T] a"),
            Record(1, "#1-INFO: [T] b"),
            Record(2, "#2-INFO: [T] c"),
        ])

    def test_leading_rollover_fragment_is_dropped(self):
        # Exactly what util/log's own wrap test produces: entry 0 half eaten.
        raw = b"] A\n" + blob(line(1, "B"), line(2, "C"))
        self.assertEqual(parse(raw),
                         [Record(1, "#1-INFO: [T] B"), Record(2, "#2-INFO: [T] C")])

    def test_unterminated_trailing_line_is_dropped(self):
        raw = blob(line(1, "done")) + b"#2-INFO: [T] half"
        self.assertEqual(parse(raw), [Record(1, "#1-INFO: [T] done")])

    def test_records_are_sorted_by_timestamp(self):
        # A mid-read buffer wrap can hand back a later chunk that predates
        # an earlier one; timestamp order is restored.
        raw = blob(line(5, "e"), line(2, "b"), line(9, "i"), line(3, "c"))
        self.assertEqual([r.timestamp for r in parse(raw)], [2, 3, 5, 9])

    def test_sort_is_stable_for_equal_timestamps(self):
        raw = blob(line(4, "first"), line(4, "second"))
        self.assertEqual([r.text for r in parse(raw)],
                         ["#4-INFO: [T] first", "#4-INFO: [T] second"])

    def test_adjacent_duplicate_records_are_deduped(self):
        raw = blob(line(1, "a"), line(2, "dup"), line(2, "dup"), line(3, "c"))
        self.assertEqual([r.text for r in parse(raw)],
                         ["#1-INFO: [T] a", "#2-INFO: [T] dup", "#3-INFO: [T] c"])

    def test_dedupe_can_be_disabled(self):
        raw = blob(line(2, "dup"), line(2, "dup"))
        self.assertEqual(len(parse(raw, dedupe=False)), 2)

    def test_crlf_terminators_are_accepted(self):
        raw = b"#1-INFO: [T] a\r\n#2-INFO: [T] b\r\n"
        self.assertEqual([r.timestamp for r in parse(raw)], [1, 2])

    def test_hash_inside_message_body_is_not_a_header(self):
        raw = blob(line(1, "see #42 for context"))
        self.assertEqual(parse(raw), [Record(1, "#1-INFO: [T] see #42 for context")])

    def test_bare_hash_without_digits_is_not_a_header(self):
        raw = blob(line(1, "count: # of retries"))
        self.assertEqual(parse(raw), [Record(1, "#1-INFO: [T] count: # of retries")])

    def test_empty_blob_yields_nothing(self):
        self.assertEqual(parse(b""), [])

    def test_blob_with_no_framable_records_yields_nothing(self):
        self.assertEqual(parse(b"garbage with no header and no newline"), [])


class FormatLogTests(unittest.TestCase):
    def test_renders_ordered_newline_terminated_text(self):
        raw = blob(line(3, "c"), line(1, "a"), line(2, "b"))
        self.assertEqual(format_log(raw),
                         "#1-INFO: [T] a\n#2-INFO: [T] b\n#3-INFO: [T] c\n")

    def test_empty_when_nothing_parses(self):
        self.assertEqual(format_log(b""), "")
        self.assertEqual(format_log(b"no records here"), "")


class ValidateTests(unittest.TestCase):
    def test_passes_a_clean_blob(self):
        self.assertEqual(validate(blob(line(0, "a"), line(1, "b"))), [])

    def test_allows_a_leading_rollover_fragment_by_default(self):
        raw = b"NFO: [T] half\n" + blob(line(1, "b"))
        self.assertEqual(validate(raw), [])

    def test_flags_leading_fragment_when_asked(self):
        raw = b"NFO: [T] half\n" + blob(line(1, "b"))
        kinds = [p.kind for p in validate(raw, allow_leading_fragment=False)]
        self.assertEqual(kinds, ["missing-leading-header"])

    def test_flags_a_newline_embedded_in_a_message(self):
        # util/log must never let a rendered line contain a bare newline;
        # if it did, the tail would look like a headerless record.
        raw = b"#1-INFO: [T] line one\nline two\n#2-INFO: [T] ok\n"
        self.assertIn("embedded-newline", [p.kind for p in validate(raw)])

    def test_allows_a_torn_trailing_line(self):
        # A live snapshot legitimately ends mid-line; that alone is fine.
        raw = blob(line(1, "a")) + b"#2-INFO: [T] tor"
        self.assertEqual(validate(raw), [])

    def test_reports_no_records_for_nonempty_unparsable_blob(self):
        self.assertEqual([p.kind for p in validate(b"just some noise")], ["no-records"])


class ModuleSurfaceTests(unittest.TestCase):
    def test_reachable_as_recom_log(self):
        self.assertEqual(log.RECORD_PREFIX, b"#")


if __name__ == "__main__":
    unittest.main()
