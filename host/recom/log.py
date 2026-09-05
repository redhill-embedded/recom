"""Turning a Recom device's raw log blob into whole, ordered records.

A device's log (see ``RecomDevice.getLogBytes``) is a byte blob carved out
of a ring buffer on the device. Because that buffer overwrites its oldest
bytes once it fills, the blob almost always begins partway through a line;
and if the device keeps logging while the host reads it back in chunks, the
blob can also end with a torn line or contain a few lines that are briefly
out of order. This module drops the partial lines and puts the rest back in
order.

Framing contract
----------------
Recom does not define the log *format* -- the consuming project's logger
does (for Polaris that is ``util/log``). Recom only relies on three framing
properties, and a logger that pulls Recom in as a dependency must honour
them:

* A record **starts** with ``RECORD_PREFIX`` (``#``) immediately followed by
  one or more ASCII decimal digits: the timestamp. Its integer value is the
  only thing Recom interprets, and only to order records against each other.
* A record **ends** with CR, LF, or CRLF.
* Everything between is opaque payload (level, task name, message, ...).
  Recom never looks at it -- but it must not contain a bare CR or LF, or the
  record cannot be framed.

:func:`validate` checks a blob against these rules. A project can feed its
logger's output -- including a deliberately wrapped ring buffer -- through
it as a conformance test, without Recom needing to know anything else about
the format.
"""

from __future__ import annotations

import re
from collections import namedtuple

# A record header: the prefix byte followed by the decimal timestamp,
# matched only at the very start of a line (parse() splits into lines
# first, then applies this to each).
RECORD_PREFIX = b"#"
HEADER_RE = re.compile(rb"#(\d+)")

# Record terminators, longest first so CRLF is consumed as one unit.
_TERMINATOR_RE = re.compile(rb"\r\n|\r|\n")


# timestamp: int, the parsed value of the header's digits.
# text:      str, the whole record line, prefix included, terminator excluded.
Record = namedtuple("Record", ["timestamp", "text"])

# kind:   str, a short stable identifier (see validate() for the set).
# detail: str, a human-readable explanation.
Problem = namedtuple("Problem", ["kind", "detail"])


def _iter_lines(raw):
    """Yield ``(line_bytes, terminated)`` for each physical line in ``raw``.

    Only the final line can ever come back with ``terminated`` False: it
    is the point the blob was cut off, the one place a partial line is
    expected rather than a bug. Every earlier line is, by construction,
    the text that preceded a CR/LF.
    """
    start = 0
    for m in _TERMINATOR_RE.finditer(raw):
        yield raw[start:m.start()], True
        start = m.end()
    if start < len(raw):
        yield raw[start:], False


def parse(raw, dedupe=True):
    """Whole, timestamp-ordered :class:`Record` list from a raw log blob.

    Lines that do not begin with a valid header are dropped: the leading
    one is the fragment left by ring-buffer rollover, and any later one is
    a message that embedded a newline (a framing-contract violation --
    :func:`validate` reports it) or blob corruption. An unterminated
    trailing line is dropped too; the device will hand it back whole on
    the next read.

    The surviving records are sorted by timestamp (stably, so records
    sharing a timestamp keep their original order). With ``dedupe`` set
    (the default), a record identical to the one before it after sorting
    is removed -- this absorbs the duplicate line a mid-read buffer wrap
    can produce.
    """
    records = []
    for line, terminated in _iter_lines(raw):
        if not terminated:
            continue
        m = HEADER_RE.match(line)
        if not m:
            continue
        records.append(Record(int(m.group(1)),
                              line.decode("utf-8", errors="replace")))

    records.sort(key=lambda r: r.timestamp)

    if dedupe:
        deduped = []
        for r in records:
            if not deduped or deduped[-1] != r:
                deduped.append(r)
        records = deduped

    return records


def format_log(raw, dedupe=True):
    """:func:`parse` output rendered back to text, ready to print.

    One record per line, newline-terminated. Returns the empty string
    when nothing parses (including when ``raw`` itself is empty) -- a
    caller that wants to tell "device has no log" apart from "device's
    log did not parse" should check ``raw`` itself.
    """
    return "".join(r.text + "\n" for r in parse(raw, dedupe=dedupe))


def validate(raw, allow_leading_fragment=True):
    """Check ``raw`` against the framing contract; return a list of
    :class:`Problem` (empty means it conforms).

    Problem kinds:

    * ``"embedded-newline"`` -- a line past the first has no header, which
      means an earlier record's payload contained a bare CR/LF (or the
      blob is corrupt). This is the check a logger's conformance test
      most wants: its rendered lines must never contain a newline except
      the terminator.
    * ``"no-records"`` -- ``raw`` is non-empty but not one whole record
      could be framed out of it. Not necessarily a contract violation (a
      snapshot can catch a single not-yet-terminated line), but worth
      surfacing.
    * ``"missing-leading-header"`` -- the first line has no header, only
      reported when ``allow_leading_fragment`` is False. Rollover makes
      this the normal case, so it is permitted by default.

    A bare ``#`` not followed by digits is treated as payload, not a
    header, so a message containing one is fine.
    """
    problems = []
    framed_any = False

    for i, (line, terminated) in enumerate(_iter_lines(raw)):
        has_header = HEADER_RE.match(line) is not None

        if has_header:
            framed_any = terminated or framed_any
        elif i == 0:
            if not allow_leading_fragment:
                problems.append(Problem(
                    "missing-leading-header",
                    "first line does not start with '#<timestamp>': {!r}".format(
                        line[:40])))
        else:
            problems.append(Problem(
                "embedded-newline",
                "line {} has no header -- a preceding record's payload "
                "contains a bare CR/LF, or the blob is corrupt: {!r}".format(
                    i, line[:40])))

    if raw and not framed_any and not any(p.kind == "embedded-newline" for p in problems):
        problems.append(Problem(
            "no-records",
            "{} bytes of data but no complete record could be framed".format(len(raw))))

    return problems
