"""User interface components for interactive bookmark management."""

import curses
import os
from typing import Optional


class UserInterface:
    """Handles user interaction for bookmark decision making."""

    def __init__(self, text_mode: bool = False):
        """Initialize the user interface.

        Args:
            text_mode: If True, force text-only interface instead of keyboard navigation
        """
        self.text_mode = text_mode

    def display_batch_decisions(
        self,
        bookmarks: list[dict],
        decisions: list[dict],
        collection_name: Optional[str] = None,
        batch_info: Optional[str] = None,
    ) -> list[int]:
        """Display recommendations and get user choices.

        Args:
            bookmarks: List of bookmark dictionaries
            decisions: List of AI decision dictionaries
            collection_name: Name of the current collection being processed
            batch_info: Optional batch progress info (e.g., "Batch 2 of 5")

        Returns:
            List of indices of bookmarks to process (non-KEEP actions)
        """
        # Check if we can use curses (keyboard interface)
        can_use_curses = not self.text_mode

        # Try to use curses interface if not explicitly disabled
        if can_use_curses:
            try:
                # Test if curses is available and terminal supports it
                import curses

                if hasattr(curses, "wrapper") and os.isatty(
                    0
                ):  # Check if stdin is a terminal
                    return self._display_keyboard_interface(
                        bookmarks, decisions, collection_name, batch_info
                    )
                else:
                    print(
                        "⚠️  Terminal doesn't support interactive mode, falling back to text interface"
                    )
                    return self._display_text_interface(
                        bookmarks, decisions, collection_name, batch_info
                    )
            except (ImportError, curses.error):
                print("⚠️  Curses not available, using text interface")
                return self._display_text_interface(
                    bookmarks, decisions, collection_name, batch_info
                )
        else:
            return self._display_text_interface(
                bookmarks, decisions, collection_name, batch_info
            )

    def _display_keyboard_interface(
        self,
        bookmarks: list[dict],
        decisions: list[dict],
        collection_name: Optional[str] = None,
        batch_info: Optional[str] = None,
    ) -> list[int]:
        """Keyboard-driven interface for selecting bookmark actions."""

        # Prepare selections - start with Claude's recommendations
        selections = []
        action_options = ["KEEP", "MOVE", "DELETE", "ARCHIVE"]

        for decision in decisions:
            action = decision.get("action", "KEEP")
            if action in action_options:
                selections.append(action_options.index(action))
            else:
                selections.append(0)  # Default to KEEP

        def draw_interface(stdscr):
            current_bookmark = 0

            while True:
                stdscr.clear()
                height, width = stdscr.getmaxyx()

                # Header
                collection_info = f" in '{collection_name}'" if collection_name else ""
                batch_progress = f" - {batch_info}" if batch_info else ""
                header = f"📋 Batch Review ({len(bookmarks)} bookmarks{collection_info}{batch_progress}) - Navigate: ↑↓/jk, Select: ←→/hl, Accept: Enter, Quit: q"
                stdscr.addstr(0, 0, header[: width - 1], curses.A_BOLD)
                stdscr.addstr(1, 0, "─" * min(width - 1, 80))

                # Show bookmarks
                start_row = 3
                for i, (bookmark, decision) in enumerate(zip(bookmarks, decisions)):
                    if start_row + i * 5 >= height - 2:  # Don't overflow screen
                        break

                    # Dynamic truncation based on terminal width - more generous limits
                    max_title = min(100, width - 5)
                    max_domain = min(60, width - 5)
                    max_reasoning = min(200, width - 5)

                    title = bookmark.get("title", "Untitled")[:max_title]
                    domain = bookmark.get("domain", "")[:max_domain]
                    reasoning = decision.get("reasoning", "")[:max_reasoning]
                    action_options[selections[i]]

                    # Show target collection for MOVE actions
                    move_target = ""
                    if decision.get("action") == "MOVE":
                        target = decision.get("target", "Unknown")
                        move_target = f" → {target}"

                    # Highlight current bookmark
                    title_attr = (
                        curses.A_REVERSE if i == current_bookmark else curses.A_NORMAL
                    )

                    # Bookmark info
                    row = start_row + i * 5
                    stdscr.addstr(
                        row,
                        0,
                        f"{'►' if i == current_bookmark else ' '} {title}",
                        title_attr,
                    )
                    stdscr.addstr(row + 1, 2, f"🌐 {domain}")

                    # Handle long reasoning with better formatting
                    reasoning_line = f"💭 {reasoning}"
                    if len(reasoning_line) > width - 6:
                        # Try to break at word boundaries
                        available_width = width - 6
                        if len(reasoning_line) > available_width:
                            # Find last space before the cutoff
                            cutoff = available_width - 3
                            space_pos = reasoning_line.rfind(" ", 0, cutoff)
                            if (
                                space_pos > len("💭 ") + 10
                            ):  # Make sure we don't cut too early
                                reasoning_line = reasoning_line[:space_pos] + "..."
                            else:
                                reasoning_line = reasoning_line[:cutoff] + "..."
                    stdscr.addstr(row + 2, 2, reasoning_line)

                    if move_target:
                        stdscr.addstr(row + 3, 2, f"📂 {move_target}")

                    # Action selection with highlighting
                    actions_row = row + 4
                    stdscr.addstr(actions_row, 4, "Actions: ")
                    x_pos = 13

                    for j, action in enumerate(action_options):
                        if action == "MOVE" and decision.get("action") != "MOVE":
                            continue  # Skip MOVE if not suggested by Claude
                        if action == "ARCHIVE" and decision.get("action") != "ARCHIVE":
                            continue  # Skip ARCHIVE if not suggested by Claude

                        # Highlight selected action for current bookmark
                        if i == current_bookmark and j == selections[i]:
                            attr = curses.A_REVERSE | curses.A_BOLD
                        elif j == selections[i]:
                            attr = curses.A_BOLD
                        else:
                            attr = curses.A_NORMAL

                        action_text = f"[{action}]"
                        stdscr.addstr(actions_row, x_pos, action_text, attr)
                        x_pos += len(action_text) + 1

                # Instructions at bottom
                if height > 10:
                    stdscr.addstr(
                        height - 2,
                        0,
                        "Press Enter to execute selections, 'q' to quit with save",
                    )

                stdscr.refresh()

                # Handle input
                try:
                    key = stdscr.getch()
                except KeyboardInterrupt:
                    raise

                # Navigation
                if key in [ord("j"), curses.KEY_DOWN]:
                    current_bookmark = min(current_bookmark + 1, len(bookmarks) - 1)
                elif key in [ord("k"), curses.KEY_UP]:
                    current_bookmark = max(current_bookmark - 1, 0)
                elif key in [ord("h"), curses.KEY_LEFT]:
                    # Move to previous action (skip unavailable ones)
                    available_actions = self._get_available_actions(
                        decisions[current_bookmark]
                    )
                    current_idx = (
                        available_actions.index(selections[current_bookmark])
                        if selections[current_bookmark] in available_actions
                        else 0
                    )
                    new_idx = (current_idx - 1) % len(available_actions)
                    selections[current_bookmark] = available_actions[new_idx]

                elif key in [ord("l"), curses.KEY_RIGHT]:
                    # Move to next action (skip unavailable ones)
                    available_actions = self._get_available_actions(
                        decisions[current_bookmark]
                    )
                    current_idx = (
                        available_actions.index(selections[current_bookmark])
                        if selections[current_bookmark] in available_actions
                        else 0
                    )
                    new_idx = (current_idx + 1) % len(available_actions)
                    selections[current_bookmark] = available_actions[new_idx]

                elif key in [ord("\n"), ord("\r"), 10]:  # Enter
                    # Return selected indices based on actions
                    selected_indices = []
                    for i, selection in enumerate(selections):
                        action = action_options[selection]
                        if (
                            action != "KEEP"
                        ):  # Only return indices for actions to execute
                            selected_indices.append(i)
                    return selected_indices

                elif key in [ord("q"), ord("Q")]:
                    raise KeyboardInterrupt()  # Quit with save

        try:
            return curses.wrapper(draw_interface)
        except KeyboardInterrupt:
            print("💾 Saving progress and exiting...")
            raise

    def _get_available_actions(self, decision: dict) -> list[int]:
        """Get list of available action indices for a decision."""
        action_options = ["KEEP", "MOVE", "DELETE", "ARCHIVE"]
        available_actions = []

        for j, action in enumerate(action_options):
            if action in ["KEEP", "DELETE"]:
                available_actions.append(j)
            elif action == "MOVE" and decision.get("action") == "MOVE":
                available_actions.append(j)
            elif action == "ARCHIVE" and decision.get("action") == "ARCHIVE":
                available_actions.append(j)

        return available_actions

    def _display_text_interface(
        self,
        bookmarks: list[dict],
        decisions: list[dict],
        collection_name: Optional[str] = None,
        batch_info: Optional[str] = None,
    ) -> list[int]:
        """Fallback text-based interface for selecting bookmark actions."""
        print(f"\n{'='*80}")
        collection_info = f" FROM '{collection_name}'" if collection_name else ""
        batch_progress = f" - {batch_info}" if batch_info else ""
        print(
            f"🤖 CLAUDE'S RECOMMENDATIONS FOR {len(bookmarks)} BOOKMARKS{collection_info}{batch_progress}"
        )
        print(f"{'='*80}")

        for i, (bookmark, decision) in enumerate(zip(bookmarks, decisions)):
            title = bookmark.get("title", "Untitled")[:60]
            domain = bookmark.get("domain", "")
            action = decision.get("action", "KEEP")
            reasoning = decision.get("reasoning", "")

            action_color = {"DELETE": "❌", "KEEP": "✅", "ARCHIVE": "📦", "MOVE": "🔄"}

            print(f"\n{i+1:2d}. {action_color.get(action, '?')} {action}")
            print(f"    📰 {title}")
            print(f"    🌐 {domain}")
            print(f"    💭 {reasoning}")

            if action == "MOVE":
                target = decision.get("target", "Unknown")
                print(f"    📂 Target: {target}")

        print(f"\n{'='*80}")
        print("💡 Enter your choice:")
        print("  'deletes' - Execute all DELETE recommendations")
        print("  'moves' - Execute all MOVE recommendations")
        print("  'all' - Execute ALL Claude's recommendations")
        print("  'none' - Skip this batch (keep everything)")
        print("  'quit' - Save progress and exit")

        while True:
            try:
                user_input = input("\n📝 Your choice: ").strip().lower()

                if user_input in ["quit", "q", "exit"]:
                    raise KeyboardInterrupt()
                elif user_input in ["none", "skip", ""]:
                    return []
                elif user_input == "all":
                    return list(range(len(bookmarks)))
                elif user_input == "deletes":
                    return [
                        i
                        for i, d in enumerate(decisions)
                        if d.get("action") == "DELETE"
                    ]
                elif user_input == "moves":
                    return [
                        i for i, d in enumerate(decisions) if d.get("action") == "MOVE"
                    ]
                elif user_input == "archives":
                    return [
                        i
                        for i, d in enumerate(decisions)
                        if d.get("action") == "ARCHIVE"
                    ]
                else:
                    print("❌ Try: 'deletes', 'moves', 'all', 'none', or 'quit'")
                    continue
            except (ValueError, IndexError):
                print("❌ Try: 'deletes', 'moves', 'all', 'none', or 'quit'")
                continue
