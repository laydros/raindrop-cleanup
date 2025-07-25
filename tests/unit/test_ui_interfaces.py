"""Tests for the user interface components."""

import os
from unittest.mock import Mock, patch, MagicMock
import pytest
from raindrop_cleanup.ui.interfaces import UserInterface


class TestUserInterface:
    """Test cases for UserInterface."""

    def test_init_text_mode(self):
        """Test initialization with text mode enabled."""
        ui = UserInterface(text_mode=True)
        assert ui.text_mode is True

    def test_init_default_mode(self):
        """Test initialization with default mode."""
        ui = UserInterface()
        assert ui.text_mode is False

    @patch("raindrop_cleanup.ui.interfaces.os.isatty")
    @patch("raindrop_cleanup.ui.interfaces.curses")
    def test_display_batch_decisions_keyboard_mode(
        self, mock_curses, mock_isatty, mock_bookmarks, mock_claude_decisions
    ):
        """Test using keyboard interface when available."""
        mock_isatty.return_value = True
        mock_curses.wrapper.return_value = [0, 2]  # User selected indices 0 and 2

        ui = UserInterface(text_mode=False)
        selected = ui.display_batch_decisions(mock_bookmarks, mock_claude_decisions)

        assert selected == [0, 2]
        mock_curses.wrapper.assert_called_once()

    @patch("raindrop_cleanup.ui.interfaces.os.isatty")
    def test_display_batch_decisions_no_tty_fallback(
        self, mock_isatty, mock_bookmarks, mock_claude_decisions
    ):
        """Test fallback to text mode when not in TTY."""
        mock_isatty.return_value = False

        with patch.object(
            UserInterface, "_display_text_interface", return_value=[1]
        ) as mock_text:
            ui = UserInterface(text_mode=False)
            selected = ui.display_batch_decisions(mock_bookmarks, mock_claude_decisions)

            assert selected == [1]
            mock_text.assert_called_once_with(
                mock_bookmarks, mock_claude_decisions, None
            )

    @patch(
        "raindrop_cleanup.ui.interfaces.curses", side_effect=ImportError("No curses")
    )
    def test_display_batch_decisions_no_curses_fallback(
        self, mock_curses, mock_bookmarks, mock_claude_decisions
    ):
        """Test fallback to text mode when curses is unavailable."""
        with patch.object(
            UserInterface, "_display_text_interface", return_value=[2]
        ) as mock_text:
            ui = UserInterface(text_mode=False)
            selected = ui.display_batch_decisions(mock_bookmarks, mock_claude_decisions)

            assert selected == [2]
            mock_text.assert_called_once_with(
                mock_bookmarks, mock_claude_decisions, None
            )

    def test_display_batch_decisions_force_text_mode(
        self, mock_bookmarks, mock_claude_decisions
    ):
        """Test forcing text mode regardless of terminal capabilities."""
        with patch.object(
            UserInterface, "_display_text_interface", return_value=[0, 1]
        ) as mock_text:
            ui = UserInterface(text_mode=True)
            selected = ui.display_batch_decisions(mock_bookmarks, mock_claude_decisions)

            assert selected == [0, 1]
            mock_text.assert_called_once_with(
                mock_bookmarks, mock_claude_decisions, None
            )

    def test_get_available_actions_basic(self):
        """Test getting available actions for basic decision."""
        ui = UserInterface()
        decision = {"action": "DELETE", "reasoning": "test"}

        available = ui._get_available_actions(decision)

        # Should always have KEEP and DELETE available
        assert 0 in available  # KEEP
        assert 2 in available  # DELETE
        assert 1 not in available  # MOVE not suggested
        assert 3 not in available  # ARCHIVE not suggested

    def test_get_available_actions_with_move(self):
        """Test getting available actions when MOVE is suggested."""
        ui = UserInterface()
        decision = {"action": "MOVE", "target": "Development", "reasoning": "test"}

        available = ui._get_available_actions(decision)

        assert 0 in available  # KEEP
        assert 1 in available  # MOVE (suggested)
        assert 2 in available  # DELETE
        assert 3 not in available  # ARCHIVE not suggested

    def test_get_available_actions_with_archive(self):
        """Test getting available actions when ARCHIVE is suggested."""
        ui = UserInterface()
        decision = {"action": "ARCHIVE", "reasoning": "test"}

        available = ui._get_available_actions(decision)

        assert 0 in available  # KEEP
        assert 1 not in available  # MOVE not suggested
        assert 2 in available  # DELETE
        assert 3 in available  # ARCHIVE (suggested)

    @patch("builtins.input")
    @patch("builtins.print")
    def test_display_text_interface_all_actions(
        self, mock_print, mock_input, mock_bookmarks, mock_claude_decisions
    ):
        """Test text interface with 'all' selection."""
        mock_input.return_value = "all"

        ui = UserInterface()
        selected = ui._display_text_interface(mock_bookmarks, mock_claude_decisions)

        assert selected == [0, 1, 2]  # All bookmark indices

    @patch("builtins.input")
    @patch("builtins.print")
    def test_display_text_interface_deletes_only(
        self, mock_print, mock_input, mock_bookmarks, mock_claude_decisions
    ):
        """Test text interface with 'deletes' selection."""
        mock_input.return_value = "deletes"

        ui = UserInterface()
        selected = ui._display_text_interface(mock_bookmarks, mock_claude_decisions)

        # Only bookmark at index 2 has DELETE action
        assert selected == [2]

    @patch("builtins.input")
    @patch("builtins.print")
    def test_display_text_interface_moves_only(
        self, mock_print, mock_input, mock_bookmarks, mock_claude_decisions
    ):
        """Test text interface with 'moves' selection."""
        mock_input.return_value = "moves"

        ui = UserInterface()
        selected = ui._display_text_interface(mock_bookmarks, mock_claude_decisions)

        # Bookmarks at indices 0 and 1 have MOVE actions
        assert selected == [0, 1]

    @patch("builtins.input")
    @patch("builtins.print")
    def test_display_text_interface_archives_only(
        self, mock_print, mock_input, mock_bookmarks
    ):
        """Test text interface with 'archives' selection."""
        mock_input.return_value = "archives"

        # Create decisions with an ARCHIVE action
        decisions = [
            {"action": "KEEP", "reasoning": "test"},
            {"action": "ARCHIVE", "reasoning": "historical"},
            {"action": "DELETE", "reasoning": "outdated"},
        ]

        ui = UserInterface()
        selected = ui._display_text_interface(mock_bookmarks, decisions)

        # Only bookmark at index 1 has ARCHIVE action
        assert selected == [1]

    @patch("builtins.input")
    @patch("builtins.print")
    def test_display_text_interface_none_selection(
        self, mock_print, mock_input, mock_bookmarks, mock_claude_decisions
    ):
        """Test text interface with 'none' selection."""
        mock_input.return_value = "none"

        ui = UserInterface()
        selected = ui._display_text_interface(mock_bookmarks, mock_claude_decisions)

        assert selected == []

    @patch("builtins.input")
    @patch("builtins.print")
    def test_display_text_interface_empty_selection(
        self, mock_print, mock_input, mock_bookmarks, mock_claude_decisions
    ):
        """Test text interface with empty input (equivalent to 'none')."""
        mock_input.return_value = ""

        ui = UserInterface()
        selected = ui._display_text_interface(mock_bookmarks, mock_claude_decisions)

        assert selected == []

    @patch("builtins.input")
    @patch("builtins.print")
    def test_display_text_interface_quit(
        self, mock_print, mock_input, mock_bookmarks, mock_claude_decisions
    ):
        """Test text interface with 'quit' selection."""
        mock_input.return_value = "quit"

        ui = UserInterface()

        with pytest.raises(KeyboardInterrupt):
            ui._display_text_interface(mock_bookmarks, mock_claude_decisions)

    @patch("builtins.input")
    @patch("builtins.print")
    def test_display_text_interface_invalid_then_valid(
        self, mock_print, mock_input, mock_bookmarks, mock_claude_decisions
    ):
        """Test text interface with invalid input followed by valid input."""
        mock_input.side_effect = ["invalid", "nonsense", "deletes"]

        ui = UserInterface()
        selected = ui._display_text_interface(mock_bookmarks, mock_claude_decisions)

        assert selected == [2]  # Should eventually process 'deletes'
        assert mock_input.call_count == 3

    @patch("builtins.print")
    def test_display_text_interface_shows_recommendations(
        self, mock_print, mock_bookmarks, mock_claude_decisions
    ):
        """Test that text interface displays AI recommendations properly."""
        with patch("builtins.input", return_value="none"):
            ui = UserInterface()
            ui._display_text_interface(mock_bookmarks, mock_claude_decisions)

        # Check that print was called with recommendation details
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        recommendation_text = " ".join(print_calls)

        assert "CLAUDE'S RECOMMENDATIONS" in recommendation_text
        assert "Python Tutorial" in recommendation_text
        assert "Metroid Prime" in recommendation_text
        assert "MOVE" in recommendation_text
        assert "DELETE" in recommendation_text

    @patch("builtins.print")
    def test_display_text_interface_shows_move_target(self, mock_print, mock_bookmarks):
        """Test that text interface shows move targets for MOVE actions."""
        decisions = [
            {
                "action": "MOVE",
                "target": "Development",
                "reasoning": "programming content",
            },
            {"action": "DELETE", "reasoning": "outdated"},
        ]

        with patch("builtins.input", return_value="none"):
            ui = UserInterface()
            ui._display_text_interface(mock_bookmarks[:2], decisions)

        print_calls = [call[0][0] for call in mock_print.call_args_list]
        recommendation_text = " ".join(print_calls)

        assert "Target: Development" in recommendation_text
