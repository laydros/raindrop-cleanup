"""Claude AI bookmark analysis for intelligent recommendations."""

import os
import time
from datetime import datetime
from typing import Any, Optional

import anthropic
from anthropic.types import TextBlock

from .prompt_config import load_prompt_template


class ClaudeAnalyzer:
    """Analyzes bookmarks using Claude AI to provide intelligent recommendations."""

    def __init__(
        self, client: Optional[anthropic.Anthropic] = None, debug: bool = False
    ) -> None:
        """Initialize the Claude analyzer.

        Args:
            client: Pre-configured Anthropic client. If not provided, creates new one.
            debug: Enable debug logging to files
        """
        self.client = client or anthropic.Anthropic()
        self.last_call_time: float = 0.0
        self.rate_limit_delay = 1  # seconds between Claude calls

        # Setup debug logging
        self.debug_enabled = debug
        self.debug_dir = ".raindrop_debug"
        if self.debug_enabled:
            os.makedirs(self.debug_dir, exist_ok=True)

    def _debug_log(self, message: str) -> None:
        """Log debug message to file."""
        if not self.debug_enabled:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file = os.path.join(self.debug_dir, "claude_parser.log")

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")

    def _rate_limit(self) -> None:
        """Apply rate limiting for Claude API calls."""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_call_time = time.time()

    def analyze_batch(
        self,
        bookmarks: list[dict[str, Any]],
        all_collections: Optional[list[dict[str, Any]]] = None,
        current_collection_name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Analyze a batch of bookmarks with Claude for efficiency.

        Args:
            bookmarks: List of bookmark dictionaries to analyze
            all_collections: Optional list of all available collections
            current_collection_name: Name of the current collection being processed

        Returns:
            List of decision dictionaries with action and reasoning
        """
        self._rate_limit()

        # Build batch information for the prompt
        batch_info = self._build_batch_info(bookmarks)
        collection_info = self._build_collection_info(
            all_collections, current_collection_name
        )

        prompt_content = self._build_analysis_prompt(
            batch_info, collection_info, len(bookmarks), current_collection_name
        )

        try:
            response_content = self.client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt_content}],
            ).content

            message = ""
            for block in response_content:
                if isinstance(block, TextBlock):
                    message += block.text

            return self._parse_batch_response(message, len(bookmarks))

        except Exception as e:
            print(f"Batch Claude API error: {e}")
            return [{"action": "KEEP", "reasoning": "API error"}] * len(bookmarks)

    def _build_batch_info(self, bookmarks: list[dict[str, Any]]) -> str:
        """Build bookmark information string for the prompt."""
        batch_info = ""
        for i, bookmark in enumerate(bookmarks):
            title = bookmark.get("title", "Untitled")
            url = bookmark.get("link", "")
            domain = bookmark.get("domain", "")
            excerpt = (
                bookmark.get("excerpt", "")[:150] if bookmark.get("excerpt") else ""
            )
            created = (
                bookmark.get("created", "")[:10] if bookmark.get("created") else ""
            )

            batch_info += f"\n{i+1}. [{title}] - {domain} - {created}\n   URL: {url}\n"
            if excerpt:
                batch_info += f"   Content: {excerpt}\n"
            batch_info += "\n"

        return batch_info

    def _build_collection_info(
        self,
        all_collections: Optional[list[dict[str, Any]]],
        current_collection_name: Optional[str],
    ) -> str:
        """Build collection information string for the prompt."""
        if not all_collections:
            return ""

        collection_info = "\nAVAILABLE COLLECTIONS:\n"
        for col in all_collections:
            is_current = (
                " ← CURRENT"
                if current_collection_name and col["title"] == current_collection_name
                else ""
            )
            collection_info += (
                f"- {col['title']} ({col.get('count', 0)} items){is_current}\n"
            )

        return collection_info

    def _build_analysis_prompt(
        self,
        batch_info: str,
        collection_info: str,
        bookmark_count: int,
        current_collection_name: Optional[str],
    ) -> str:
        """Build the complete analysis prompt."""
        current_collection_info = (
            f"\nCURRENT COLLECTION: {current_collection_name}\n"
            if current_collection_name
            else ""
        )

        template = load_prompt_template()

        return template.format(
            bookmark_count=bookmark_count,
            current_collection_name=current_collection_name or "",
            batch_info=batch_info,
            collection_info=collection_info,
            current_collection_info=current_collection_info,
        )

    def _parse_batch_response(
        self, message: str, bookmark_count: int
    ) -> list[dict[str, Any]]:
        """Parse Claude's batch response into decision dictionaries."""
        decisions: list[dict[str, Any]] = []
        lines = message.strip().split("\n")

        self._debug_log("=" * 60)
        self._debug_log(f"PARSING BATCH RESPONSE ({bookmark_count} bookmarks)")
        self._debug_log("=" * 60)
        self._debug_log(f"Raw response: {repr(message)}")
        self._debug_log("=" * 60)

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            self._debug_log(f"Line {i}: '{line}'")

            if ". " in line and line and line[0].isdigit():
                parts = line.split(". ", 1)[1].strip()
                self._debug_log(f"  Found decision: '{parts}'")

                action_part = parts
                reasoning = "no reason given"

                # Format 1: "ACTION - reasoning text"
                if " - " in parts:
                    parts_split = parts.split(" - ", 1)
                    action_part = parts_split[0].strip()
                    reasoning = parts_split[1].strip()
                    self._debug_log(
                        f"  Format 1: action='{action_part}', reasoning='{reasoning}'"
                    )
                else:
                    # NEW LOGIC: Handle reasoning on subsequent lines (prefixed, bulleted, or plain)
                    reasoning_lines = []
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j].strip()

                        # Stop if we hit the next numbered item or a summary section
                        if (
                            next_line
                            and (next_line[0].isdigit() and ". " in next_line)
                            or next_line.lower().startswith("summary:")
                            or next_line.lower().startswith("reasoning summary:")
                        ):
                            self._debug_log(
                                f"    Hit next decision or summary, stopping scan at line {j}"
                            )
                            break

                        # Clean the line by removing common prefixes and add to reasoning
                        clean_line = next_line
                        for prefix in ["Reasoning:", "Reason:", "-"]:
                            if clean_line.lower().startswith(prefix.lower()):
                                clean_line = clean_line[len(prefix) :].strip()
                                break  # Only remove one prefix per line

                        if clean_line:
                            reasoning_lines.append(clean_line)

                        j += 1

                    if reasoning_lines:
                        reasoning = " ".join(reasoning_lines)
                        self._debug_log(
                            f"  Combined reasoning from lines {i+1}-{j-1}: '{reasoning}'"
                        )

                    # Advance the main loop counter past the lines we just processed
                    i = j - 1

                self._debug_log(f"  Final reasoning: '{reasoning}'")
                action_part = action_part.strip()

                # Parse different decision types
                if action_part.upper().startswith("MOVE:"):
                    try:
                        collection_name = action_part.split(":", 1)[1].strip()
                        self._debug_log(f"  MOVE to '{collection_name}' - {reasoning}")
                        decisions.append(
                            {
                                "action": "MOVE",
                                "target": collection_name,
                                "reasoning": reasoning,
                            }
                        )
                    except IndexError:
                        self._debug_log(f"  MOVE parse error: {action_part}")
                        decisions.append({"action": "KEEP", "reasoning": "parse error"})
                else:
                    # Handle DELETE, KEEP, ARCHIVE
                    action = action_part.upper()
                    self._debug_log(f"  {action} - {reasoning}")

                    if action in ["DELETE", "KEEP", "ARCHIVE"]:
                        decisions.append({"action": action, "reasoning": reasoning})
                    else:
                        self._debug_log(
                            f"  Unknown action '{action}', defaulting to KEEP"
                        )
                        decisions.append(
                            {
                                "action": "KEEP",
                                "reasoning": f"unclear recommendation: {action}",
                            }
                        )

            i += 1

        # Ensure we have decisions for all bookmarks
        while len(decisions) < bookmark_count:
            decisions.append(
                {"action": "KEEP", "reasoning": "no recommendation received"}
            )

        self._debug_log(
            f"FINAL DECISIONS: {len(decisions)} decisions for {bookmark_count} bookmarks"
        )
        for i, decision in enumerate(decisions[:bookmark_count]):
            self._debug_log(
                f"  {i+1}. {decision['action']} -> {decision.get('target', '')} - {decision['reasoning']}"
            )
        self._debug_log("=" * 60)

        return decisions[:bookmark_count]
