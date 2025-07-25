"""Tests for the state manager."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest
from raindrop_cleanup.state.manager import StateManager


class TestStateManager:
    """Test cases for StateManager."""

    def test_init_creates_state_dir(self, temp_state_dir):
        """Test that initialization creates state directory."""
        state_manager = StateManager(state_dir=temp_state_dir)

        assert state_manager.state_dir == Path(temp_state_dir)
        assert state_manager.state_dir.exists()
        assert len(state_manager.processed_bookmark_ids) == 0
        assert state_manager.stats["processed"] == 0

    def test_get_state_filename(self, temp_state_dir):
        """Test state filename generation."""
        state_manager = StateManager(state_dir=temp_state_dir)
        filename = state_manager.get_state_filename(123, "Test Collection")

        expected = Path(temp_state_dir) / "collection_123_Test_Collection.json"
        assert filename == expected

    def test_get_state_filename_special_chars(self, temp_state_dir):
        """Test state filename with special characters."""
        state_manager = StateManager(state_dir=temp_state_dir)
        filename = state_manager.get_state_filename(456, "Test/Collection@#$%")

        expected = Path(temp_state_dir) / "collection_456_TestCollection.json"
        assert filename == expected

    def test_save_state(self, temp_state_dir):
        """Test saving state to file."""
        state_manager = StateManager(state_dir=temp_state_dir)
        state_manager.processed_bookmark_ids.add(101)
        state_manager.processed_bookmark_ids.add(102)
        state_manager.stats["processed"] = 2
        state_manager.stats["deleted"] = 1

        state_manager.save_state(123, "Test Collection", current_page=3)

        # Verify file was created
        expected_file = Path(temp_state_dir) / "collection_123_Test_Collection.json"
        assert expected_file.exists()

        # Verify file contents
        with open(expected_file, "r") as f:
            saved_state = json.load(f)

        assert saved_state["collection_id"] == 123
        assert saved_state["collection_name"] == "Test Collection"
        assert saved_state["current_page"] == 3
        assert set(saved_state["processed_bookmark_ids"]) == {101, 102}
        assert saved_state["stats"]["processed"] == 2
        assert saved_state["stats"]["deleted"] == 1
        assert "last_updated" in saved_state

    def test_load_state_success(self, temp_state_dir, sample_state_data):
        """Test successful state loading."""
        state_manager = StateManager(state_dir=temp_state_dir)

        # Create a state file
        state_file = Path(temp_state_dir) / "collection_1_Unsorted.json"
        with open(state_file, "w") as f:
            json.dump(sample_state_data, f, default=str)

        loaded_state = state_manager.load_state(1, "Unsorted")

        assert loaded_state is not None
        assert loaded_state["collection_id"] == 1
        assert loaded_state["collection_name"] == "Unsorted"
        assert state_manager.processed_bookmark_ids == {101, 102, 103}
        assert state_manager.stats["processed"] == 3

    def test_load_state_file_not_found(self, temp_state_dir):
        """Test loading state when file doesn't exist."""
        state_manager = StateManager(state_dir=temp_state_dir)
        loaded_state = state_manager.load_state(999, "NonExistent")

        assert loaded_state is None

    def test_load_state_invalid_collection(self, temp_state_dir, sample_state_data):
        """Test loading state with mismatched collection."""
        state_manager = StateManager(state_dir=temp_state_dir)

        # Create state file with different collection ID
        state_file = Path(temp_state_dir) / "collection_999_Wrong.json"
        with open(state_file, "w") as f:
            json.dump(sample_state_data, f, default=str)

        loaded_state = state_manager.load_state(999, "Wrong")

        assert loaded_state is None

    def test_load_state_corrupted_file(self, temp_state_dir):
        """Test loading corrupted state file."""
        state_manager = StateManager(state_dir=temp_state_dir)

        # Create corrupted JSON file
        state_file = Path(temp_state_dir) / "collection_1_Test.json"
        with open(state_file, "w") as f:
            f.write("invalid json content")

        loaded_state = state_manager.load_state(1, "Test")

        assert loaded_state is None

    def test_cleanup_state_file(self, temp_state_dir):
        """Test state file cleanup."""
        state_manager = StateManager(state_dir=temp_state_dir)

        # Create and set current state file
        state_file = Path(temp_state_dir) / "test_state.json"
        state_file.write_text("{}")
        state_manager.current_state_file = state_file

        assert state_file.exists()
        state_manager.cleanup_state_file()
        assert not state_file.exists()

    def test_cleanup_state_file_no_current_file(self, temp_state_dir):
        """Test cleanup when no current state file is set."""
        state_manager = StateManager(state_dir=temp_state_dir)

        # Should not raise an error
        state_manager.cleanup_state_file()

    def test_list_resumable_sessions(self, temp_state_dir):
        """Test listing resumable sessions."""
        state_manager = StateManager(state_dir=temp_state_dir)

        # Create multiple state files
        sessions_data = [
            {
                "collection_id": 1,
                "collection_name": "Collection A",
                "processed_bookmark_ids": [1, 2, 3],
                "stats": {"deleted": 1, "moved": 2},
                "last_updated": "2024-01-15T10:00:00",
            },
            {
                "collection_id": 2,
                "collection_name": "Collection B",
                "processed_bookmark_ids": [4, 5],
                "stats": {"deleted": 0, "moved": 1},
                "last_updated": "2024-01-16T15:00:00",
            },
        ]

        for i, data in enumerate(sessions_data):
            filename = f"collection_{data['collection_id']}_{data['collection_name'].replace(' ', '_')}.json"
            state_file = Path(temp_state_dir) / filename
            with open(state_file, "w") as f:
                json.dump(data, f)

        sessions = state_manager.list_resumable_sessions()

        assert len(sessions) == 2
        # Should be sorted by last_updated (newest first)
        assert sessions[0]["collection_name"] == "Collection B"
        assert sessions[1]["collection_name"] == "Collection A"
        assert sessions[0]["processed_count"] == 2
        assert sessions[1]["processed_count"] == 3

    def test_list_resumable_sessions_empty(self, temp_state_dir):
        """Test listing sessions when none exist."""
        state_manager = StateManager(state_dir=temp_state_dir)
        sessions = state_manager.list_resumable_sessions()

        assert sessions == []

    def test_clean_state_files(self, temp_state_dir):
        """Test cleaning up state files."""
        state_manager = StateManager(state_dir=temp_state_dir)

        # Create some state files
        for i in range(3):
            state_file = Path(temp_state_dir) / f"collection_{i}_Test.json"
            state_file.write_text("{}")

        with patch("builtins.input", return_value="y"):
            count = state_manager.clean_state_files()

        assert count == 3
        # Verify files are deleted
        remaining_files = list(Path(temp_state_dir).glob("collection_*.json"))
        assert len(remaining_files) == 0

    def test_clean_state_files_cancelled(self, temp_state_dir):
        """Test cancelling state file cleanup."""
        state_manager = StateManager(state_dir=temp_state_dir)

        # Create a state file
        state_file = Path(temp_state_dir) / "collection_1_Test.json"
        state_file.write_text("{}")

        with patch("builtins.input", return_value="n"):
            count = state_manager.clean_state_files()

        assert count == 0
        assert state_file.exists()

    def test_clean_state_files_none_found(self, temp_state_dir):
        """Test cleaning when no state files exist."""
        state_manager = StateManager(state_dir=temp_state_dir)
        count = state_manager.clean_state_files()

        assert count == 0

    @patch("builtins.print")
    def test_print_stats(self, mock_print, temp_state_dir):
        """Test printing statistics."""
        state_manager = StateManager(state_dir=temp_state_dir)
        state_manager.stats.update(
            {
                "processed": 10,
                "kept": 5,
                "deleted": 3,
                "archived": 1,
                "moved": 1,
                "errors": 0,
                "skipped": 2,
            }
        )

        state_manager.print_stats(dry_run=False)

        # Verify some key outputs were printed
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any("BOOKMARK CLEANUP COMPLETE!" in call for call in print_calls)
        assert any("Total processed: 10" in call for call in print_calls)
        assert any("Deleted: 3" in call for call in print_calls)

    @patch("builtins.print")
    def test_print_stats_dry_run(self, mock_print, temp_state_dir):
        """Test printing statistics in dry run mode."""
        state_manager = StateManager(state_dir=temp_state_dir)
        state_manager.print_stats(dry_run=True)

        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any("BOOKMARK CLEANUP SIMULATION!" in call for call in print_calls)

    def test_add_processed_bookmark(self, temp_state_dir):
        """Test adding processed bookmark ID."""
        state_manager = StateManager(state_dir=temp_state_dir)

        state_manager.add_processed_bookmark(123)
        state_manager.add_processed_bookmark(456)

        assert 123 in state_manager.processed_bookmark_ids
        assert 456 in state_manager.processed_bookmark_ids
        assert len(state_manager.processed_bookmark_ids) == 2

    def test_is_bookmark_processed(self, temp_state_dir):
        """Test checking if bookmark is processed."""
        state_manager = StateManager(state_dir=temp_state_dir)

        state_manager.add_processed_bookmark(123)

        assert state_manager.is_bookmark_processed(123) is True
        assert state_manager.is_bookmark_processed(456) is False

    def test_update_stats(self, temp_state_dir):
        """Test updating statistics."""
        state_manager = StateManager(state_dir=temp_state_dir)

        initial_processed = state_manager.stats["processed"]
        initial_deleted = state_manager.stats["deleted"]

        state_manager.update_stats(processed=5, deleted=2)

        assert state_manager.stats["processed"] == initial_processed + 5
        assert state_manager.stats["deleted"] == initial_deleted + 2

    def test_update_stats_invalid_key(self, temp_state_dir):
        """Test updating stats with invalid key (should be ignored)."""
        state_manager = StateManager(state_dir=temp_state_dir)

        # Should not raise an error, just ignore invalid keys
        state_manager.update_stats(invalid_key=10, processed=1)

        assert state_manager.stats["processed"] == 1
        assert "invalid_key" not in state_manager.stats
