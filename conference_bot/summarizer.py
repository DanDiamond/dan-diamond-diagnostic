"""Summarization module using the Anthropic Claude API.

Takes the full session transcript and produces a structured summary
containing:
  - Session title / topic
  - Key points (bullet list)
  - Action items
  - Decisions made
  - Q&A highlights
  - One-paragraph executive summary
"""

import logging
from dataclasses import dataclass

import anthropic

from .config import config
from .transcriber import Transcript

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------


@dataclass
class Summary:
    """Structured summary produced from a conference transcript."""
    title: str
    executive_summary: str
    key_points: list[str]
    action_items: list[str]
    decisions: list[str]
    qa_highlights: list[str]
    raw_response: str          # full markdown as returned by Claude

    def to_markdown(self) -> str:
        """Render the summary as a nicely formatted Markdown document."""
        lines = [
            f"# {self.title}",
            "",
            "## Executive Summary",
            "",
            self.executive_summary,
            "",
        ]

        def _section(heading: str, items: list[str]):
            if items:
                lines.append(f"## {heading}")
                lines.append("")
                for item in items:
                    lines.append(f"- {item}")
                lines.append("")

        _section("Key Points", self.key_points)
        _section("Action Items", self.action_items)
        _section("Decisions Made", self.decisions)
        _section("Q&A Highlights", self.qa_highlights)

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Summarizer
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert note-taker for online conferences, lectures, and webinars.
You receive a verbatim transcript and produce a concise, well-structured summary
in clean Markdown using exactly the sections below.  Be accurate and specific —
do not invent information not present in the transcript.

Output format (Markdown, use these exact section headings):
# <Session Title>

## Executive Summary
<One or two paragraph overview of the session>

## Key Points
- <bullet>
- <bullet>

## Action Items
- <bullet>  (or "None identified" if there are none)

## Decisions Made
- <bullet>  (or "None identified")

## Q&A Highlights
- <bullet>  (or "None")
"""


class Summarizer:
    """Calls Claude to summarise a Transcript.

    Usage::

        s = Summarizer()
        summary = s.summarize(transcript, context="Python conference talk on async IO")
        print(summary.to_markdown())
    """

    def __init__(self, model: str = None):
        self.model = model or config.claude_model
        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def summarize(
        self,
        transcript: Transcript,
        context: str = "",
        max_tokens: int = 2048,
    ) -> Summary:
        """Summarize *transcript* and return a Summary object.

        Args:
            transcript: The Transcript produced by the Transcriber.
            context:    Optional free-text context (e.g. event name, topic)
                        to help Claude produce better output.
            max_tokens: Maximum tokens for the Claude response.
        """
        if not transcript.full_text.strip():
            logger.warning("Transcript is empty — returning placeholder summary")
            return Summary(
                title="Session Summary",
                executive_summary="No audio was transcribed for this session.",
                key_points=[],
                action_items=[],
                decisions=[],
                qa_highlights=[],
                raw_response="",
            )

        user_message = self._build_user_message(transcript, context)

        logger.info(
            "Sending %d words to Claude (%s) for summarization",
            transcript.word_count(),
            self.model,
        )

        response = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = response.content[0].text
        logger.info("Summary received (%d chars)", len(raw))

        return self._parse_summary(raw)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_user_message(self, transcript: Transcript, context: str) -> str:
        parts = []
        if context:
            parts.append(f"**Session context:** {context}\n")
        parts.append("**Transcript:**\n")
        parts.append(transcript.timestamped_text)
        return "\n".join(parts)

    def _parse_summary(self, raw: str) -> Summary:
        """Parse the Markdown response from Claude into a Summary object."""
        title = "Session Summary"
        executive_summary = ""
        key_points: list[str] = []
        action_items: list[str] = []
        decisions: list[str] = []
        qa_highlights: list[str] = []

        current_section = None
        exec_lines: list[str] = []

        for line in raw.splitlines():
            stripped = line.strip()

            if stripped.startswith("# ") and not stripped.startswith("## "):
                title = stripped.lstrip("# ").strip()
                current_section = None
            elif stripped == "## Executive Summary":
                current_section = "exec"
            elif stripped == "## Key Points":
                current_section = "kp"
            elif stripped == "## Action Items":
                current_section = "ai"
            elif stripped == "## Decisions Made":
                current_section = "dec"
            elif stripped == "## Q&A Highlights":
                current_section = "qa"
            elif stripped.startswith("## "):
                current_section = "other"
            else:
                # Accumulate content for the current section
                if current_section == "exec":
                    if stripped:
                        exec_lines.append(stripped)
                elif current_section in ("kp", "ai", "dec", "qa"):
                    if stripped.startswith("- "):
                        item = stripped[2:].strip()
                        if item and item.lower() not in ("none identified", "none"):
                            target = {
                                "kp": key_points,
                                "ai": action_items,
                                "dec": decisions,
                                "qa": qa_highlights,
                            }[current_section]
                            target.append(item)

        executive_summary = " ".join(exec_lines)

        return Summary(
            title=title,
            executive_summary=executive_summary,
            key_points=key_points,
            action_items=action_items,
            decisions=decisions,
            qa_highlights=qa_highlights,
            raw_response=raw,
        )
