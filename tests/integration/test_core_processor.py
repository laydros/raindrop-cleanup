"""Integration tests for the core processor."""

from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import pytest
from raindrop_cleanup.core.processor import RaindropBookmarkCleaner


class TestRaindropBookmarkCleaner:
    """Integration test cases for RaindropBookmarkCleaner."""
    
    @patch('raindrop_cleanup.core.processor.RaindropClient')
    @patch('raindrop_cleanup.core.processor.ClaudeAnalyzer')
    @patch('raindrop_cleanup.core.processor.UserInterface')
    @patch('raindrop_cleanup.core.processor.StateManager')
    def test_init_components(self, mock_state_manager, mock_ui, mock_claude, mock_raindrop):
        """Test that all components are initialized properly."""
        cleaner = RaindropBookmarkCleaner(dry_run=True, state_dir="test_dir", text_mode=True)
        
        assert cleaner.dry_run is True
        mock_raindrop.assert_called_once()
        mock_claude.assert_called_once()
        mock_ui.assert_called_once_with(text_mode=True)
        mock_state_manager.assert_called_once_with(state_dir="test_dir")
    
    @patch('raindrop_cleanup.core.processor.RaindropClient')
    @patch('raindrop_cleanup.core.processor.ClaudeAnalyzer')
    @patch('raindrop_cleanup.core.processor.UserInterface')
    @patch('raindrop_cleanup.core.processor.StateManager')
    def test_execute_user_selections_skip_all(self, mock_state_manager, mock_ui, mock_claude, mock_raindrop, mock_bookmarks, mock_claude_decisions):
        """Test executing selections when user skips all items."""
        mock_state_instance = Mock()
        mock_state_manager.return_value = mock_state_instance
        
        cleaner = RaindropBookmarkCleaner()
        cleaner._execute_user_selections(
            mock_bookmarks, mock_claude_decisions, [], None
        )
        
        # Should mark all bookmarks as processed
        assert mock_state_instance.add_processed_bookmark.call_count == 3
        mock_state_instance.update_stats.assert_called_once_with(skipped=3)
    
    @patch('raindrop_cleanup.core.processor.RaindropClient')
    @patch('raindrop_cleanup.core.processor.ClaudeAnalyzer')
    @patch('raindrop_cleanup.core.processor.UserInterface')
    @patch('raindrop_cleanup.core.processor.StateManager')
    def test_execute_user_selections_delete_action(self, mock_state_manager, mock_ui, mock_claude, mock_raindrop, mock_bookmarks, mock_claude_decisions):
        """Test executing DELETE action."""
        mock_state_instance = Mock()
        mock_state_manager.return_value = mock_state_instance
        mock_raindrop_instance = Mock()
        mock_raindrop.return_value = mock_raindrop_instance
        mock_raindrop_instance.delete_bookmark.return_value = True
        
        cleaner = RaindropBookmarkCleaner()
        # Select index 2 which has DELETE action
        cleaner._execute_user_selections(
            mock_bookmarks, mock_claude_decisions, [2], None
        )
        
        mock_raindrop_instance.delete_bookmark.assert_called_once_with(103)
        mock_state_instance.update_stats.assert_any_call(deleted=1)
        mock_state_instance.update_stats.assert_any_call(processed=1)
        mock_state_instance.update_stats.assert_any_call(kept=2)  # 2 unselected items
    
    @patch('raindrop_cleanup.core.processor.RaindropClient')
    @patch('raindrop_cleanup.core.processor.ClaudeAnalyzer')
    @patch('raindrop_cleanup.core.processor.UserInterface')  
    @patch('raindrop_cleanup.core.processor.StateManager')
    def test_execute_user_selections_move_action(self, mock_state_manager, mock_ui, mock_claude, mock_raindrop, mock_bookmarks, mock_claude_decisions, mock_collections):
        """Test executing MOVE action."""
        mock_state_instance = Mock()
        mock_state_manager.return_value = mock_state_instance
        mock_raindrop_instance = Mock()
        mock_raindrop.return_value = mock_raindrop_instance
        mock_raindrop_instance.move_bookmark_to_collection.return_value = True
        mock_raindrop_instance.find_collection_by_name.return_value = 2  # Development collection ID
        
        cleaner = RaindropBookmarkCleaner()
        # Select index 0 which has MOVE action to Development
        cleaner._execute_user_selections(
            mock_bookmarks, mock_claude_decisions, [0], mock_collections
        )
        
        mock_raindrop_instance.find_collection_by_name.assert_called_once_with(mock_collections, 'Development')
        mock_raindrop_instance.move_bookmark_to_collection.assert_called_once_with(101, 2)
        mock_state_instance.update_stats.assert_any_call(moved=1)
    
    @patch('raindrop_cleanup.core.processor.RaindropClient')
    @patch('raindrop_cleanup.core.processor.ClaudeAnalyzer')
    @patch('raindrop_cleanup.core.processor.UserInterface')
    @patch('raindrop_cleanup.core.processor.StateManager')
    def test_execute_user_selections_archive_action(self, mock_state_manager, mock_ui, mock_claude, mock_raindrop, mock_bookmarks):
        """Test executing ARCHIVE action."""
        mock_state_instance = Mock()
        mock_state_manager.return_value = mock_state_instance
        mock_raindrop_instance = Mock()
        mock_raindrop.return_value = mock_raindrop_instance
        mock_raindrop_instance.move_bookmark_to_collection.return_value = True
        
        # Create decision with ARCHIVE action
        decisions = [{'action': 'ARCHIVE', 'reasoning': 'historical value'}]
        
        cleaner = RaindropBookmarkCleaner()
        cleaner._execute_user_selections(
            mock_bookmarks[:1], decisions, [0], None, archive_collection_id=4
        )
        
        mock_raindrop_instance.move_bookmark_to_collection.assert_called_once_with(101, 4)
        mock_state_instance.update_stats.assert_any_call(archived=1)
    
    @patch('raindrop_cleanup.core.processor.RaindropClient')
    @patch('raindrop_cleanup.core.processor.ClaudeAnalyzer')
    @patch('raindrop_cleanup.core.processor.UserInterface')
    @patch('raindrop_cleanup.core.processor.StateManager')
    def test_execute_user_selections_dry_run(self, mock_state_manager, mock_ui, mock_claude, mock_raindrop, mock_bookmarks, mock_claude_decisions):
        """Test executing actions in dry-run mode."""
        mock_state_instance = Mock()
        mock_state_manager.return_value = mock_state_instance
        mock_raindrop_instance = Mock()
        mock_raindrop.return_value = mock_raindrop_instance
        
        cleaner = RaindropBookmarkCleaner(dry_run=True)
        cleaner._execute_user_selections(
            mock_bookmarks, mock_claude_decisions, [2], None  # DELETE action
        )
        
        # Should not call actual API methods in dry-run
        mock_raindrop_instance.delete_bookmark.assert_not_called()
        # But should still update stats
        mock_state_instance.update_stats.assert_any_call(deleted=1)
    
    @patch('raindrop_cleanup.core.processor.RaindropClient')
    @patch('raindrop_cleanup.core.processor.ClaudeAnalyzer')
    @patch('raindrop_cleanup.core.processor.UserInterface')
    @patch('raindrop_cleanup.core.processor.StateManager')
    def test_execute_user_selections_api_failures(self, mock_state_manager, mock_ui, mock_claude, mock_raindrop, mock_bookmarks, mock_claude_decisions):
        """Test handling of API failures during execution."""
        mock_state_instance = Mock()
        mock_state_manager.return_value = mock_state_instance
        mock_raindrop_instance = Mock()
        mock_raindrop.return_value = mock_raindrop_instance
        mock_raindrop_instance.delete_bookmark.return_value = False  # Simulate failure
        
        cleaner = RaindropBookmarkCleaner()
        cleaner._execute_user_selections(
            mock_bookmarks, mock_claude_decisions, [2], None  # DELETE action
        )
        
        mock_state_instance.update_stats.assert_any_call(errors=1)
    
    @patch('raindrop_cleanup.core.processor.RaindropClient')
    @patch('raindrop_cleanup.core.processor.ClaudeAnalyzer')
    @patch('raindrop_cleanup.core.processor.UserInterface')
    @patch('raindrop_cleanup.core.processor.StateManager')
    @patch('builtins.input')
    def test_process_collection_fresh_start(self, mock_input, mock_state_manager, mock_ui, mock_claude, mock_raindrop, mock_bookmarks, mock_claude_decisions):
        """Test processing collection from fresh start."""
        mock_input.return_value = 'n'  # Don't resume
        
        # Setup mocks
        mock_state_instance = Mock()
        mock_state_instance.load_state.return_value = {'current_page': 1}
        mock_state_instance.processed_bookmark_ids = set()
        mock_state_manager.return_value = mock_state_instance
        
        mock_raindrop_instance = Mock()
        mock_raindrop_instance.get_bookmarks_from_collection.side_effect = [
            {'items': mock_bookmarks},
            {'items': []}  # Empty response to end loop
        ]
        mock_raindrop.return_value = mock_raindrop_instance
        
        mock_claude_instance = Mock()
        mock_claude_instance.analyze_batch.return_value = mock_claude_decisions
        mock_claude.return_value = mock_claude_instance
        
        mock_ui_instance = Mock()
        mock_ui_instance.display_batch_decisions.return_value = [0]  # Select first bookmark
        mock_ui.return_value = mock_ui_instance
        
        cleaner = RaindropBookmarkCleaner()
        cleaner.process_collection(1, "Test Collection", batch_size=5)
        
        # Should reset processed bookmark IDs for fresh start
        assert len(mock_state_instance.processed_bookmark_ids) == 0
    
    @patch('raindrop_cleanup.core.processor.RaindropClient')
    @patch('raindrop_cleanup.core.processor.ClaudeAnalyzer')
    @patch('raindrop_cleanup.core.processor.UserInterface')
    @patch('raindrop_cleanup.core.processor.StateManager')
    def test_process_collection_keyboard_interrupt(self, mock_state_manager, mock_ui, mock_claude, mock_raindrop):
        """Test handling keyboard interrupt during processing."""
        mock_state_instance = Mock()
        mock_state_instance.load_state.return_value = None
        mock_state_manager.return_value = mock_state_instance
        
        mock_raindrop_instance = Mock()
        mock_raindrop_instance.get_bookmarks_from_collection.side_effect = KeyboardInterrupt()
        mock_raindrop.return_value = mock_raindrop_instance
        
        cleaner = RaindropBookmarkCleaner()
        
        with pytest.raises(KeyboardInterrupt):
            cleaner.process_collection(1, "Test Collection")
        
        # Should save state before re-raising
        mock_state_instance.save_state.assert_called()
    
    @patch('raindrop_cleanup.core.processor.RaindropClient')
    @patch('raindrop_cleanup.core.processor.ClaudeAnalyzer')
    @patch('raindrop_cleanup.core.processor.UserInterface')
    @patch('raindrop_cleanup.core.processor.StateManager')
    def test_process_collection_completed(self, mock_state_manager, mock_ui, mock_claude, mock_raindrop):
        """Test successful collection completion."""
        mock_state_instance = Mock()
        mock_state_instance.load_state.return_value = None
        mock_state_instance.processed_bookmark_ids = set()
        mock_state_manager.return_value = mock_state_instance
        
        mock_raindrop_instance = Mock()
        mock_raindrop_instance.get_bookmarks_from_collection.return_value = {'items': []}  # Empty collection
        mock_raindrop.return_value = mock_raindrop_instance
        
        cleaner = RaindropBookmarkCleaner()
        cleaner.process_collection(1, "Test Collection")
        
        # Should clean up state file when completed
        mock_state_instance.cleanup_state_file.assert_called_once()
    
    @patch('raindrop_cleanup.core.processor.RaindropClient')
    @patch('raindrop_cleanup.core.processor.ClaudeAnalyzer')
    @patch('raindrop_cleanup.core.processor.UserInterface')
    @patch('raindrop_cleanup.core.processor.StateManager')
    def test_print_stats_delegates_to_state_manager(self, mock_state_manager, mock_ui, mock_claude, mock_raindrop):
        """Test that print_stats delegates to state manager."""
        mock_state_instance = Mock()
        mock_state_manager.return_value = mock_state_instance
        
        cleaner = RaindropBookmarkCleaner(dry_run=True)
        cleaner.print_stats()
        
        mock_state_instance.print_stats.assert_called_once_with(dry_run=True)
    
    @patch('raindrop_cleanup.core.processor.RaindropClient')
    @patch('raindrop_cleanup.core.processor.ClaudeAnalyzer')
    @patch('raindrop_cleanup.core.processor.UserInterface')
    @patch('raindrop_cleanup.core.processor.StateManager')
    @patch('builtins.input')
    def test_process_collection_break_suggestion(self, mock_input, mock_state_manager, mock_ui, mock_claude, mock_raindrop):
        """Test ADHD break suggestion functionality."""
        # Setup to trigger break suggestion after 25 items
        mock_input.side_effect = ['', 'quit']  # Empty for break prompt, quit for second
        
        mock_state_instance = Mock()
        mock_state_instance.load_state.return_value = None
        mock_state_instance.processed_bookmark_ids = set()
        mock_state_instance.is_bookmark_processed.return_value = False  # No bookmarks pre-processed
        mock_state_instance.stats = {'start_time': datetime.now()}  # Mock stats dict
        mock_state_manager.return_value = mock_state_instance
        
        # Create 26 bookmarks to trigger break suggestion  
        many_bookmarks = []
        for i in range(26):
            many_bookmarks.append({
                '_id': i,
                'title': f'Bookmark {i}',
                'link': f'https://example.com/{i}',
                'domain': 'example.com'
            })
        
        mock_raindrop_instance = Mock()
        mock_raindrop_instance.get_bookmarks_from_collection.side_effect = [
            {'items': many_bookmarks},
            {'items': []}
        ]
        mock_raindrop.return_value = mock_raindrop_instance
        
        mock_claude_instance = Mock()
        # Need to return the right number of decisions for each batch
        mock_claude_instance.analyze_batch.side_effect = [
            [{'action': 'KEEP', 'reasoning': 'test'} for _ in range(25)],  # First batch of 25
            [{'action': 'KEEP', 'reasoning': 'test'}]  # Second batch of 1
        ]
        mock_claude.return_value = mock_claude_instance
        
        mock_ui_instance = Mock()
        mock_ui_instance.display_batch_decisions.return_value = []  # Skip all
        mock_ui.return_value = mock_ui_instance
        
        cleaner = RaindropBookmarkCleaner()
        cleaner.process_collection(1, "Test Collection", batch_size=25)
        
        # Should have prompted for break at least once
        assert mock_input.call_count >= 1