"""Tests for recom.log -- the framing/ordering the host applies to a
device's raw log blob.

    cd host && pytest

The fixtures deliberately mirror Polaris util/log's rendered line format
(``#<ts>-<LEVEL>: [<task>] <msg>\\n``), including a ring buffer that has
wrapped, so this doubles as the conformance check for that contract.
"""

from recom import log
from recom.log import Record, parse, format_log, validate, LogFollower


def line(ts, msg, level="INFO", task="T"):
    return "#%d-%s: [%s] %s\n" % (ts, level, task, msg)


def blob(*lines):
    return "".join(lines).encode("utf-8")


def texts(records):
    return [r.text for r in records]


class TestParse:
    def test_clean_blob_yields_every_record_in_order(self):
        raw = blob(line(0, "a"), line(1, "b"), line(2, "c"))
        assert parse(raw) == [
            Record(0, "#0-INFO: [T] a"),
            Record(1, "#1-INFO: [T] b"),
            Record(2, "#2-INFO: [T] c"),
        ]

    def test_leading_rollover_fragment_is_dropped(self):
        # Exactly what util/log's own wrap test produces: entry 0 half eaten.
        raw = b"] A\n" + blob(line(1, "B"), line(2, "C"))
        assert parse(raw) == [Record(1, "#1-INFO: [T] B"), Record(2, "#2-INFO: [T] C")]

    def test_unterminated_trailing_line_is_dropped(self):
        raw = blob(line(1, "done")) + b"#2-INFO: [T] half"
        assert parse(raw) == [Record(1, "#1-INFO: [T] done")]

    def test_records_are_sorted_by_timestamp(self):
        # A mid-read buffer wrap can hand back a later chunk that predates
        # an earlier one; timestamp order is restored.
        raw = blob(line(5, "e"), line(2, "b"), line(9, "i"), line(3, "c"))
        assert [r.timestamp for r in parse(raw)] == [2, 3, 5, 9]

    def test_sort_is_stable_for_equal_timestamps(self):
        raw = blob(line(4, "first"), line(4, "second"))
        assert texts(parse(raw)) == ["#4-INFO: [T] first", "#4-INFO: [T] second"]

    def test_adjacent_duplicate_records_are_deduped(self):
        raw = blob(line(1, "a"), line(2, "dup"), line(2, "dup"), line(3, "c"))
        assert texts(parse(raw)) == [
            "#1-INFO: [T] a", "#2-INFO: [T] dup", "#3-INFO: [T] c",
        ]

    def test_dedupe_can_be_disabled(self):
        raw = blob(line(2, "dup"), line(2, "dup"))
        assert len(parse(raw, dedupe=False)) == 2

    def test_crlf_terminators_are_accepted(self):
        raw = b"#1-INFO: [T] a\r\n#2-INFO: [T] b\r\n"
        assert [r.timestamp for r in parse(raw)] == [1, 2]

    def test_hash_inside_message_body_is_not_a_header(self):
        raw = blob(line(1, "see #42 for context"))
        assert parse(raw) == [Record(1, "#1-INFO: [T] see #42 for context")]

    def test_bare_hash_without_digits_is_not_a_header(self):
        raw = blob(line(1, "count: # of retries"))
        assert parse(raw) == [Record(1, "#1-INFO: [T] count: # of retries")]

    def test_empty_blob_yields_nothing(self):
        assert parse(b"") == []

    def test_blob_with_no_framable_records_yields_nothing(self):
        assert parse(b"garbage with no header and no newline") == []


class TestFormatLog:
    def test_renders_ordered_newline_terminated_text(self):
        raw = blob(line(3, "c"), line(1, "a"), line(2, "b"))
        assert format_log(raw) == "#1-INFO: [T] a\n#2-INFO: [T] b\n#3-INFO: [T] c\n"

    def test_empty_when_nothing_parses(self):
        assert format_log(b"") == ""
        assert format_log(b"no records here") == ""


class TestValidate:
    def test_passes_a_clean_blob(self):
        assert validate(blob(line(0, "a"), line(1, "b"))) == []

    def test_allows_a_leading_rollover_fragment_by_default(self):
        raw = b"NFO: [T] half\n" + blob(line(1, "b"))
        assert validate(raw) == []

    def test_flags_leading_fragment_when_asked(self):
        raw = b"NFO: [T] half\n" + blob(line(1, "b"))
        kinds = [p.kind for p in validate(raw, allow_leading_fragment=False)]
        assert kinds == ["missing-leading-header"]

    def test_flags_a_newline_embedded_in_a_message(self):
        # util/log must never let a rendered line contain a bare newline;
        # if it did, the tail would look like a headerless record.
        raw = b"#1-INFO: [T] line one\nline two\n#2-INFO: [T] ok\n"
        assert "embedded-newline" in [p.kind for p in validate(raw)]

    def test_allows_a_torn_trailing_line(self):
        # A live snapshot legitimately ends mid-line; that alone is fine.
        raw = blob(line(1, "a")) + b"#2-INFO: [T] tor"
        assert validate(raw) == []

    def test_reports_no_records_for_nonempty_unparsable_blob(self):
        assert [p.kind for p in validate(b"just some noise")] == ["no-records"]


class TestLogFollower:
    def test_first_feed_returns_the_whole_buffer(self):
        f = LogFollower()
        assert texts(f.feed(blob(line(1, "a"), line(2, "b")))) == [
            "#1-INFO: [T] a", "#2-INFO: [T] b",
        ]

    def test_overlapping_feed_returns_only_the_new_records(self):
        f = LogFollower()
        f.feed(blob(line(1, "a"), line(2, "b")))
        out = f.feed(blob(line(1, "a"), line(2, "b"), line(3, "c"), line(4, "d")))
        assert texts(out) == ["#3-INFO: [T] c", "#4-INFO: [T] d"]

    def test_feed_with_nothing_new_returns_empty(self):
        f = LogFollower()
        f.feed(blob(line(1, "a"), line(2, "b")))
        assert f.feed(blob(line(1, "a"), line(2, "b"))) == []

    def test_watermark_advances_across_successive_feeds(self):
        f = LogFollower()
        f.feed(blob(line(1, "a")))
        f.feed(blob(line(1, "a"), line(2, "b")))
        out = f.feed(blob(line(1, "a"), line(2, "b"), line(3, "c")))
        assert texts(out) == ["#3-INFO: [T] c"]

    def test_feed_tolerates_the_front_of_the_buffer_dropping_off(self):
        f = LogFollower()
        f.feed(blob(line(1, "a"), line(2, "b"), line(3, "c")))
        # Ring buffer wrapped: entry 1 half-eaten, entry 4 appended.
        out = f.feed(b"NFO: [T] a\n" + blob(line(2, "b"), line(3, "c"), line(4, "d")))
        assert texts(out) == ["#4-INFO: [T] d"]

    def test_feed_resumes_when_the_watermark_has_scrolled_out(self):
        f = LogFollower()
        f.feed(blob(line(1, "a"), line(2, "b")))
        # Polled too slowly; ts=2 is gone, only newer entries remain.
        out = f.feed(blob(line(5, "e"), line(6, "f")))
        assert texts(out) == ["#5-INFO: [T] e", "#6-INFO: [T] f"]

    def test_feed_replays_the_buffer_after_a_device_reboot(self):
        f = LogFollower()
        f.feed(blob(line(40, "old"), line(41, "older")))
        out = f.feed(blob(line(0, "boot"), line(1, "up")))
        assert texts(out) == ["#0-INFO: [T] boot", "#1-INFO: [T] up"]

    def test_feed_ignores_a_torn_trailing_line_until_it_completes(self):
        f = LogFollower()
        first = f.feed(blob(line(1, "a")) + b"#2-INFO: [T] hal")
        assert texts(first) == ["#1-INFO: [T] a"]
        out = f.feed(blob(line(1, "a"), line(2, "half")))
        assert texts(out) == ["#2-INFO: [T] half"]


def test_module_is_reachable_as_recom_log():
    assert log.RECORD_PREFIX == b"#"
