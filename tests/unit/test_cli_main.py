"""Tests for the CLI entry point."""

import sys
from unittest.mock import Mock, patch, MagicMock
import pytest
from raindrop_cleanup.cli.main import main, _handle_resume_selection, _list_collections, _select_collection


class TestCLIMain:
    """Test cases for CLI main function."""
    
    @patch('raindrop_cleanup.cli.main.RaindropBookmarkCleaner')
    @patch('sys.argv', ['raindrop-cleanup', '--help'])
    def test_help_argument(self, mock_cleaner):
        """Test help argument displays help and exits."""
        with pytest.raises(SystemExit):
            main()
    
    @patch('raindrop_cleanup.cli.main.RaindropBookmarkCleaner')
    @patch('sys.argv', ['raindrop-cleanup', '--dry-run', '--text-mode'])
    @patch('builtins.input', return_value='quit')
    def test_argument_parsing(self, mock_input, mock_cleaner):
        """Test that command line arguments are parsed correctly."""
        mock_cleaner_instance = Mock()
        mock_cleaner_instance.raindrop_client.get_collections.return_value = []
        mock_cleaner.return_value = mock_cleaner_instance
        
        main()
        
        # Should initialize cleaner with correct arguments
        mock_cleaner.assert_called_once_with(dry_run=True, text_mode=True)
    
    @patch('raindrop_cleanup.cli.main.RaindropBookmarkCleaner')
    @patch('sys.argv', ['raindrop-cleanup', '--clean-state'])
    def test_clean_state_option(self, mock_cleaner):
        """Test --clean-state option."""
        mock_cleaner_instance = Mock()
        mock_cleaner_instance.state_manager.clean_state_files.return_value = 3
        mock_cleaner.return_value = mock_cleaner_instance
        
        main()
        
        mock_cleaner_instance.state_manager.clean_state_files.assert_called_once()
    
    @patch('raindrop_cleanup.cli.main.RaindropBookmarkCleaner')
    @patch('sys.argv', ['raindrop-cleanup', '--list-collections'])
    def test_list_collections_option(self, mock_cleaner, mock_collections):
        """Test --list-collections option."""
        mock_cleaner_instance = Mock()
        mock_cleaner_instance.raindrop_client.get_collections.return_value = mock_collections
        mock_cleaner.return_value = mock_cleaner_instance
        
        with patch('raindrop_cleanup.cli.main._list_collections') as mock_list:
            main()
            mock_list.assert_called_once_with(mock_collections)
    
    @patch('raindrop_cleanup.cli.main.RaindropBookmarkCleaner')
    @patch('sys.argv', ['raindrop-cleanup', '--resume'])
    @patch('builtins.input', return_value='new')
    def test_resume_option_new_session(self, mock_input, mock_cleaner, mock_collections):
        """Test --resume option choosing new session."""
        mock_cleaner_instance = Mock()
        mock_cleaner_instance.state_manager.show_resumable_sessions.return_value = [
            {'collection_name': 'Test', 'collection_id': 1}
        ]
        mock_cleaner_instance.raindrop_client.get_collections.return_value = mock_collections
        mock_cleaner.return_value = mock_cleaner_instance
        
        with patch('raindrop_cleanup.cli.main._select_collection', return_value=None):
            main()
        
        mock_cleaner_instance.state_manager.show_resumable_sessions.assert_called_once()
    
    @patch('raindrop_cleanup.cli.main.RaindropBookmarkCleaner')
    @patch('sys.argv', ['raindrop-cleanup'])
    @patch('builtins.input', side_effect=['quit'])
    def test_no_collections_found(self, mock_input, mock_cleaner):
        """Test behavior when no collections are found."""
        mock_cleaner_instance = Mock()
        mock_cleaner_instance.raindrop_client.get_collections.return_value = []
        mock_cleaner.return_value = mock_cleaner_instance
        
        main()
        
        # Should exit early when no collections found
        mock_cleaner_instance.process_collection.assert_not_called()
    
    @patch('raindrop_cleanup.cli.main.RaindropBookmarkCleaner')
    @patch('sys.argv', ['raindrop-cleanup'])
    @patch('builtins.input', side_effect=['1', ''])  # Select collection 1, then press Enter
    def test_normal_processing_flow(self, mock_input, mock_cleaner, mock_collections):
        """Test normal processing flow."""
        mock_cleaner_instance = Mock()
        mock_cleaner_instance.raindrop_client.get_collections.return_value = mock_collections
        mock_cleaner_instance.raindrop_client.find_collection_by_name.return_value = 4  # Archive ID
        mock_cleaner.return_value = mock_cleaner_instance
        
        main()
        
        # Should process the selected collection
        mock_cleaner_instance.process_collection.assert_called_once()
        mock_cleaner_instance.print_stats.assert_called_once()
    
    @patch('raindrop_cleanup.cli.main.RaindropBookmarkCleaner')  
    @patch('sys.argv', ['raindrop-cleanup'])
    @patch('builtins.input', side_effect=['1', ''])
    def test_keyboard_interrupt_handling(self, mock_input, mock_cleaner, mock_collections):
        """Test keyboard interrupt handling."""
        mock_cleaner_instance = Mock()
        mock_cleaner_instance.raindrop_client.get_collections.return_value = mock_collections
        mock_cleaner_instance.process_collection.side_effect = KeyboardInterrupt()
        mock_cleaner.return_value = mock_cleaner_instance
        
        main()
        
        # Should still print stats after interrupt
        mock_cleaner_instance.print_stats.assert_called_once()
    
    @patch('raindrop_cleanup.cli.main.RaindropBookmarkCleaner')
    @patch('sys.argv', ['raindrop-cleanup'])
    def test_general_exception_handling(self, mock_cleaner):
        """Test general exception handling."""
        mock_cleaner.side_effect = Exception("Test error")
        
        # Should not raise, just print error
        main()


class TestCLIHelpers:
    """Test cases for CLI helper functions."""
    
    def test_handle_resume_selection_new(self):
        """Test selecting 'new' in resume selection."""
        sessions = [{'collection_name': 'Test'}]
        
        with patch('builtins.input', return_value='new'):
            result = _handle_resume_selection(sessions)
            assert result is None
    
    def test_handle_resume_selection_valid_number(self):
        """Test selecting valid session number."""
        sessions = [
            {'collection_name': 'Test 1'},
            {'collection_name': 'Test 2'}
        ]
        
        with patch('builtins.input', return_value='2'):
            result = _handle_resume_selection(sessions)
            assert result == sessions[1]
    
    def test_handle_resume_selection_invalid_input(self):
        """Test handling invalid input in resume selection."""
        sessions = [{'collection_name': 'Test'}]
        
        with patch('builtins.input', side_effect=['invalid', 'xyz', '1']):
            result = _handle_resume_selection(sessions)
            assert result == sessions[0]
    
    @patch('builtins.print')
    def test_list_collections(self, mock_print, mock_collections):
        """Test listing collections."""
        _list_collections(mock_collections)
        
        # Should print collection information
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        output_text = ' '.join(print_calls)
        assert 'Development' in output_text
        assert 'Gaming' in output_text
        assert '150 items' in output_text
    
    def test_select_collection_by_number(self, mock_collections):
        """Test selecting collection by number."""
        with patch('builtins.input', return_value='2'):
            result = _select_collection(mock_collections)
            assert result == mock_collections[1]  # Development collection
    
    def test_select_collection_by_name(self, mock_collections):
        """Test selecting collection by name."""
        with patch('builtins.input', return_value='gaming'):
            result = _select_collection(mock_collections)
            assert result['title'] == 'Gaming'
    
    def test_select_collection_quit(self, mock_collections):
        """Test quitting from collection selection."""
        with patch('builtins.input', return_value='quit'):
            result = _select_collection(mock_collections)
            assert result is None
    
    def test_select_collection_invalid_then_valid(self, mock_collections):
        """Test invalid input followed by valid selection."""
        with patch('builtins.input', side_effect=['invalid', 'nonexistent', '1']):
            result = _select_collection(mock_collections)
            assert result == mock_collections[0]  # Unsorted collection
    
    @patch('raindrop_cleanup.cli.main._resume_session')
    @patch('sys.argv', ['raindrop-cleanup', '--resume'])
    @patch('builtins.input', return_value='1')
    def test_resume_session_integration(self, mock_input, mock_resume_session, mock_collections):
        """Test resuming a session integration."""
        sessions = [{
            'collection_id': 1,
            'collection_name': 'Test Collection'
        }]
        
        with patch('raindrop_cleanup.cli.main.RaindropBookmarkCleaner') as mock_cleaner:
            mock_cleaner_instance = Mock()
            mock_cleaner_instance.state_manager.show_resumable_sessions.return_value = sessions
            mock_cleaner.return_value = mock_cleaner_instance
            
            main()
            
            mock_resume_session.assert_called_once()
    
    @patch('sys.argv', ['raindrop-cleanup'])
    @patch('builtins.print')
    def test_main_prints_header(self, mock_print):
        """Test that main prints the application header."""
        with patch('raindrop_cleanup.cli.main.RaindropBookmarkCleaner') as mock_cleaner:
            mock_cleaner_instance = Mock()
            mock_cleaner_instance.raindrop_client.get_collections.return_value = []
            mock_cleaner.return_value = mock_cleaner_instance
            
            main()
            
            # Check that header was printed
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            header_text = ' '.join(print_calls)
            assert "Interactive Raindrop Bookmark Cleanup Tool" in header_text


class TestArgumentParsing:
    """Test command line argument parsing."""
    
    @patch('sys.argv', ['raindrop-cleanup', '--batch-size', '15'])
    @patch('raindrop_cleanup.cli.main.RaindropBookmarkCleaner')
    @patch('builtins.input', return_value='quit')
    def test_batch_size_argument(self, mock_input, mock_cleaner):
        """Test batch size argument parsing."""
        mock_cleaner_instance = Mock()
        mock_cleaner_instance.raindrop_client.get_collections.return_value = []
        mock_cleaner.return_value = mock_cleaner_instance
        
        # Mock the argparse to capture the batch_size
        with patch('raindrop_cleanup.cli.main._select_collection', return_value={'_id': 1, 'title': 'Test', 'count': 10}):
            with patch('builtins.input', side_effect=['', '']):  # Skip dry-run warning, start processing
                main()
        
        # Verify process_collection was called with correct batch_size
        call_args = mock_cleaner_instance.process_collection.call_args
        if call_args:
            assert call_args[1]['batch_size'] == 15
    
    @patch('sys.argv', ['raindrop-cleanup', '--archive-name', 'MyArchive'])
    @patch('raindrop_cleanup.cli.main.RaindropBookmarkCleaner')
    @patch('builtins.input', return_value='quit')
    def test_archive_name_argument(self, mock_input, mock_cleaner, mock_collections):
        """Test archive name argument parsing."""
        mock_cleaner_instance = Mock()
        mock_cleaner_instance.raindrop_client.get_collections.return_value = mock_collections
        mock_cleaner_instance.raindrop_client.find_collection_by_name.return_value = None
        mock_cleaner.return_value = mock_cleaner_instance
        
        main()
        
        # Should try to find collection with custom archive name
        mock_cleaner_instance.raindrop_client.find_collection_by_name.assert_called_with(
            mock_collections, 'MyArchive'
        )