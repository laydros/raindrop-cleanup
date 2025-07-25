"""Claude AI bookmark analysis for intelligent recommendations."""

import time
import anthropic
from typing import List, Dict, Optional


class ClaudeAnalyzer:
    """Analyzes bookmarks using Claude AI to provide intelligent recommendations."""

    def __init__(self, client: Optional[anthropic.Anthropic] = None):
        """Initialize the Claude analyzer.

        Args:
            client: Pre-configured Anthropic client. If not provided, creates new one.
        """
        self.client = client or anthropic.Anthropic()
        self.last_call_time = 0
        self.rate_limit_delay = 1  # seconds between Claude calls

    def _rate_limit(self):
        """Apply rate limiting for Claude API calls."""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_call_time = time.time()

    def analyze_batch(
        self,
        bookmarks: List[Dict],
        all_collections: Optional[List[Dict]] = None,
        current_collection_name: Optional[str] = None,
    ) -> List[Dict]:
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
                    model="claude-3-haiku-20240307",
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt_content}],
                )
                .content[0]
                .text
            )

            return self._parse_batch_response(message, len(bookmarks))

        except Exception as e:
            print(f"Batch Claude API error: {e}")
            return [{"action": "KEEP", "reasoning": "API error"}] * len(bookmarks)

    def _build_batch_info(self, bookmarks: List[Dict]) -> str:
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
        all_collections: Optional[List[Dict]],
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
You are helping someone with ADHD declutter bookmarks. Analyze these {bookmark_count} bookmarks and provide recommendations:
{current_collection_info}
{batch_info}

{collection_info}

For each bookmark, recommend the BEST action:

ACTIONS:
- DELETE: Can find via search, old news, "might read someday", outdated tutorials, duplicate content
- KEEP: Already in the right collection, frequently referenced, active project tools
- ARCHIVE: Historical reference (if Archive collection exists)
- MOVE:[CollectionName]: Should be in a different collection for better organization

CRITICAL RULES:
- NEVER suggest MOVE to the current collection ({current_collection_name}) - use KEEP instead
- Be ruthless with DELETE - they can find things again with search
- MOVE suggestions should improve organization
- When in doubt between KEEP and DELETE, lean toward DELETE
- Look for patterns: multiple similar links, outdated tutorials, dead projects

CATEGORIZATION HINTS (examine URL, title, and domain carefully):
- Gaming: game names (Metroid, Zelda, Pokemon), gaming sites (Steam, IGN, GameFAQs), ROM hacking, speedrunning, game guides
- Development: GitHub, Stack Overflow, documentation, coding tutorials, development tools, programming languages
- Reading: articles, blogs, Medium, news sites, opinion pieces
- Tools: apps, services, utilities, online tools
- Learning: courses, tutorials, educational content, how-to guides

URL PATTERN CLUES:
- github.com/user/repo = development
- steamcommunity.com, store.steampowered.com = gaming  
- medium.com/@author, blog.* = reading
- docs.* = development (usually)
- reddit.com/r/gamedev = development, reddit.com/r/gaming = gaming

BE VERY CAREFUL: 
- "Metroid ROM hacking tutorial" = GAMING (it's about a game)
- "JavaScript tutorial" = DEVELOPMENT (it's about programming)
- "How to speedrun Zelda" = GAMING (it's about playing a game)
- "How to code a game in Unity" = DEVELOPMENT (it's about programming)

Respond with ONLY the numbers and decisions:
1. DELETE - outdated tutorial
2. MOVE:development - coding tool  
3. KEEP - active reference
4. ARCHIVE - historical doc
etc.

Include brief reasoning after each decision.
"""

    def _parse_batch_response(self, message: str, bookmark_count: int) -> List[Dict]:
        """Parse Claude's batch response into decision dictionaries."""
        decisions = []
        lines = message.strip().split("\n")

        for line in lines:
            if ". " in line and line[0].isdigit():
                parts = line.split(". ", 1)[1].strip()

                # Parse different decision types
                if parts.upper().startswith("MOVE:"):
                    # Extract collection name and reasoning
                    try:
                        move_part = parts.split(" - ", 1)
                        collection_name = move_part[0].split(":", 1)[1].strip()
                        reasoning = (
                            move_part[1]
                            if len(move_part) > 1
                            else "better organization"
                        )
                        decisions.append(
                            {
                                "action": "MOVE",
                                "target": collection_name,
                                "reasoning": reasoning,
                            }
                        )
                    except:
                        decisions.append({"action": "KEEP", "reasoning": "parse error"})
                else:
                    # Handle DELETE, KEEP, ARCHIVE with reasoning
                    decision_parts = parts.split(" - ", 1)
                    action = decision_parts[0].strip().upper()
                    reasoning = (
                        decision_parts[1]
                        if len(decision_parts) > 1
                        else "no reason given"
                    )

                    if action in ["DELETE", "KEEP", "ARCHIVE"]:
                        decisions.append({"action": action, "reasoning": reasoning})
                    else:
                        decisions.append(
                            {"action": "KEEP", "reasoning": "unclear recommendation"}
                        )

        # Ensure we have decisions for all bookmarks
        while len(decisions) < bookmark_count:
            decisions.append(
                {"action": "KEEP", "reasoning": "no recommendation received"}
            )

        return decisions[:bookmark_count]
