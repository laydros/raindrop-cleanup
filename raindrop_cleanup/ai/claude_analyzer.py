"""Claude AI bookmark analysis for intelligent recommendations."""

import os
import time
from datetime import datetime
from typing import Optional

import anthropic


class ClaudeAnalyzer:
    """Analyzes bookmarks using Claude AI to provide intelligent recommendations."""

    def __init__(
        self, client: Optional[anthropic.Anthropic] = None, debug: bool = False
    ):
        """Initialize the Claude analyzer.

        Args:
            client: Pre-configured Anthropic client. If not provided, creates new one.
            debug: Enable debug logging to files
        """
        self.client = client or anthropic.Anthropic()
        self.last_call_time = 0
        self.rate_limit_delay = 1  # seconds between Claude calls

        # Setup debug logging
        self.debug_enabled = debug
        self.debug_dir = ".raindrop_debug"
        if self.debug_enabled:
            os.makedirs(self.debug_dir, exist_ok=True)

    def _debug_log(self, message: str):
        """Log debug message to file."""
        if not self.debug_enabled:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file = os.path.join(self.debug_dir, "claude_parser.log")

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")

    def _rate_limit(self):
        """Apply rate limiting for Claude API calls."""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_call_time = time.time()

    def analyze_batch(
        self,
        bookmarks: list[dict],
        all_collections: Optional[list[dict]] = None,
        current_collection_name: Optional[str] = None,
    ) -> list[dict]:
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
            message = (
                self.client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1500,
                    messages=[{"role": "user", "content": prompt_content}],
                )
                .content[0]
                .text
            )

            return self._parse_batch_response(message, len(bookmarks))

        except Exception as e:
            print(f"Batch Claude API error: {e}")
            return [{"action": "KEEP", "reasoning": "API error"}] * len(bookmarks)

    def _build_batch_info(self, bookmarks: list[dict]) -> str:
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
        all_collections: Optional[list[dict]],
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

        return f"""
You are helping someone with ADHD declutter bookmarks. This person tends to bookmark too much and rarely revisits items. They prefer to re-search rather than keep everything. Be aggressive with DELETE suggestions.

Analyze these {bookmark_count} bookmarks and provide recommendations:
{current_collection_info}
{batch_info}

{collection_info}

ACTIONS:
- DELETE: Topical blog posts >2 years old, tutorials >5 years old, "someday reading" items, duplicate content
- KEEP: Already in correct collection, timeless references, active work tools
- ARCHIVE: Historical reference (if Archive collection exists)
- MOVE:[CollectionName]: Should be in different collection for better organization

CRITICAL RULES:
- NEVER suggest MOVE to current collection ({current_collection_name}) - use KEEP instead
- DEFAULT to MOVE for better organization over KEEP
- Be ruthless with DELETE - user can find things via search
- When uncertain between KEEP/DELETE, lean toward DELETE
- User rarely revisits bookmarks, so DELETE liberally

AGE-BASED DELETE RULES:
- News articles, topical blog posts: DELETE if >2 years old
- Tutorials, how-tos: DELETE if >5 years old (unless timeless)
- Medium articles: DELETE if >3 years old
- GitHub repos: DELETE if archived/abandoned

SPECIFIC COLLECTION MAPPING:
- reddit.com/r/programming → development
- docs.microsoft.com → development (and KEEP)
- news.ycombinator.com → reading-and-blogs
- medium.com articles → reading-and-blogs (or DELETE if old)
- GitHub repos → development
- Gaming content → gaming
- Apple-specific → apple
- Security topics → privacy-security
- Linux/Unix → linux-unix
- Text editors → text-editors
- Infrastructure/DevOps → infrastructure
- OpenBSD → openbsd
- Health topics → health-wellness
- Music → music
- Making/DIY → making
- AI/ML → ai-ml
- Tools/utilities → tools
- RSS/bookmarking → bookmarking-and-rss
- Emacs → emacs
- Work items → work-specific

EXAMPLE DECISIONS:
1. "React Hooks Tutorial" (2019) + react.dev → DELETE - 5+ year old tutorial, React has changed significantly
2. "Microsoft Azure Documentation" + docs.microsoft.com → KEEP - timeless reference in correct collection
3. "Interesting AI article" + medium.com (2021) → DELETE - 3+ year old Medium article, likely outdated
4. "Vim Configuration Guide" + reddit.com/r/vim → MOVE:text-editors - better organization
5. "Apple M1 Review" (2020) + arstechnica.com → DELETE - 4+ year old tech review, outdated
6. "Python requests library docs" + docs.python.org → MOVE:development - reference documentation
7. "Weekend project ideas" + personal blog (2019) → DELETE - 5+ year old someday reading

Respond with ONLY the numbers and decisions:
1. DELETE - outdated tutorial from 2019
2. MOVE:development - coding reference
3. KEEP - timeless documentation
4. DELETE - old topical article
etc.

Include specific reasoning focusing on age, relevance, and collection fit.
"""

    def _parse_batch_response(self, message: str, bookmark_count: int) -> list[dict]:
        """Parse Claude's batch response into decision dictionaries."""
        decisions = []
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
