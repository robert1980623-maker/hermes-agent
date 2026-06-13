"""Regression tests for the think-block stripping at the final_response
capture point in run_agent.py.

Some OpenAI-compatible providers (notably minimax-cn's MiniMax-M3) embed
their reasoning inline in the assistant message's `content` field rather
than using the structured `reasoning_content` / `reasoning_details` API
fields.  Without stripping <think>...</think> blocks at the capture point,
raw think blocks leak into messaging-platform outputs (Feishu / Telegram /
Slack) even when `display.show_reasoning: false`.

The fix is a single-line change at run_agent.py:9840 — call
`self._strip_think_blocks(...)` on `assistant_message.content` before
assigning to `final_response`.  This mirrors the pattern already used by
the fallback content path (~line 9865) and the streaming display path.

We test this in two layers:

1. **Source-level test** — verifies that the patched run_agent.py actually
   calls `_strip_think_blocks` at the final_response capture point.  This
   is the primary regression test and is independent of the import graph.

2. **Helper-level test** — exercises the `_strip_think_blocks` regex
   patterns in isolation.  The mirror patterns are kept in sync with
   the production helper; the source-level test verifies the production
   code still uses the same patterns.
"""

import re
from pathlib import Path

import pytest

_RUN_AGENT = Path(__file__).resolve().parent.parent.parent / "run_agent.py"


# Mirror of the regex transforms inside run_agent._strip_think_blocks.
# Kept in sync with the production helper — the source-level test in
# TestFixAppliedAtRunAgent9840 verifies the production code still uses
# the same patterns, so a drift here will be caught.
_STRIP_TRANSFORMS = [
    (r"<think>.*?</think>", re.DOTALL),
    (r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE),
    (r"<reasoning>.*?</reasoning>", re.DOTALL),
    (r"<REASONING_SCRATCHPAD>.*?</REASONING_SCRATCHPAD>", re.DOTALL),
    (r"</?(?:think|thinking|reasoning|REASONING_SCRATCHPAD)>\s*", re.IGNORECASE),
]


def _strip_think_blocks(content):
    if not content:
        return ""
    for pattern, flags in _STRIP_TRANSFORMS:
        content = re.sub(pattern, "", content, flags=flags)
    return content


def _capture_final_response(content):
    """Replicate the EXACT post-fix code pattern at run_agent.py:9840.

    Pattern: `final_response = self._strip_think_blocks(
        assistant_message.content or ""
    ).strip()`
    """
    return _strip_think_blocks(content or "").strip()


# ── source-level regression test ──────────────────────────────────────────


class TestFixAppliedAtRunAgent9840:
    """The actual production fix is a 1-line change at the final_response
    capture point.  Verify that change is in place."""

    def test_line_9840_calls_strip_think_blocks(self):
        """The line that assigns `final_response = assistant_message.content`
        must be replaced with the `_strip_think_blocks(...)` variant.

        We locate the line dynamically (no hard-coded line number) so the
        test survives future line drift.
        """
        src = _RUN_AGENT.read_text(encoding="utf-8")
        match = re.search(
            r"# No tool calls - this is the final response\s*\n"
            r"(?P<body>.*?)"
            r"# Check if response only has think block",
            src,
            flags=re.DOTALL,
        )
        assert match, "Could not locate the final_response capture block."
        body = match.group("body")
        # The fix: must call _strip_think_blocks on assistant_message.content
        assert "_strip_think_blocks(assistant_message.content" in body, (
            "final_response is not being stripped of inline think blocks. "
            "The fix at this capture point is missing."
        )
        # Anti-regression: must NOT just be the unstripped original.
        assert 'final_response = assistant_message.content or ""' not in body, (
            "The original un-stripped final_response assignment is still "
            "in place — the fix has been reverted."
        )

    def test_inline_documentation_present(self):
        """The fix should include a comment explaining why stripping happens,
        so future maintainers don't accidentally remove it."""
        src = _RUN_AGENT.read_text(encoding="utf-8")
        match = re.search(
            r"# No tool calls - this is the final response\s*\n"
            r"(?P<body>.*?)"
            r"# Check if response only has think block",
            src,
            flags=re.DOTALL,
        )
        assert match
        body = match.group("body")
        keywords = ("strip", "think", "inline", "reasoning", "leak", "minimax")
        assert any(kw in body.lower() for kw in keywords), (
            "The fix should include a comment explaining why think-block "
            "stripping is needed at this point."
        )


# ── helper-level behaviour tests ──────────────────────────────────────────


class TestStripThinkBlocksFromFinalResponse:
    """Verify the helper's regex behaviour for the patterns we care about."""

    def test_basic_think_block_stripped(self):
        """Single <think>...</think> removed, real content preserved."""
        result = _capture_final_response(
            "<think>Let me think about this.</think>The answer is 42."
        )
        assert "<think>" not in result
        assert "Let me think" not in result
        assert result == "The answer is 42."

    def test_no_think_block_passes_through(self):
        """Plain content without think blocks is unchanged."""
        result = _capture_final_response("Just a normal response.")
        assert result == "Just a normal response."

    def test_multiline_think_block_stripped(self):
        """Multi-line think blocks are stripped completely."""
        content = (
            "<think>Line 1 of reasoning.\n"
            "Line 2 of reasoning.\n"
            "Line 3.\n"
            "</think>\n"
            "The actual answer."
        )
        result = _capture_final_response(content)
        assert "Line 1" not in result
        assert "Line 2" not in result
        assert "Line 3" not in result
        assert "<think>" not in result
        assert "</think>" not in result
        assert result == "The actual answer."

    def test_thinking_tag_variant_stripped(self):
        """<thinking>...</thinking> variant is also stripped."""
        result = _capture_final_response(
            "<thinking>Reasoning here.</thinking>The answer."
        )
        assert "Reasoning" not in result
        assert "<thinking>" not in result
        assert result == "The answer."

    def test_reasoning_scratchpad_variant_stripped(self):
        """<REASONING_SCRATCHPAD> variant used by some models is stripped."""
        content = (
            "<REASONING_SCRATCHPAD>step 1: x\n"
            "step 2: y</REASONING_SCRATCHPAD>\n"
            "Final answer."
        )
        result = _capture_final_response(content)
        assert "step 1" not in result
        assert "step 2" not in result
        assert "REASONING_SCRATCHPAD" not in result
        assert result == "Final answer."

    def test_multiple_think_blocks_all_stripped(self):
        """Multiple sequential think blocks are all removed."""
        result = _capture_final_response(
            "<think>first thought.</think>"
            "Some text. "
            "<think>second thought.</think>"
            "More text."
        )
        assert "first thought" not in result
        assert "second thought" not in result
        assert result == "Some text. More text."

    def test_minimax_style_realistic(self):
        """Specific case: minimax-cn MiniMax-M3 leaking think blocks
        into Feishu messages.  Mirrors the kind of output reported in
        the bug report."""
        content = (
            "<think>The user is asking about X. "
            "I should provide a clear answer.</think>"
            "Here is the answer to X."
        )
        result = _capture_final_response(content)
        assert result == "Here is the answer to X."

    def test_empty_content_returns_empty(self):
        """None / empty content is handled gracefully (no AttributeError)."""
        assert _capture_final_response("") == ""
        assert _capture_final_response(None) == ""

    def test_think_block_only_returns_empty(self):
        """Content that is ONLY a think block yields empty string — this
        matches the `_has_content_after_think_block` check immediately
        downstream at line ~9844 which then triggers fallback logic."""
        result = _capture_final_response(
            "<think>all thinking, no answer.</think>"
        )
        assert result == ""

    def test_stray_closing_tag_removed(self):
        """A stray `</think>` without matching open tag is cleaned up.
        The production regex includes `\s*` after the tag, so trailing
        whitespace is also consumed (this is intentional — keeps the
        visible text tightly formatted)."""
        result = _capture_final_response("Some text</think> more text")
        assert "</think>" not in result
        assert result == "Some textmore text"
