"""Tests for the Claude AI analyzer."""

import time
import pytest
from unittest.mock import Mock, patch
from raindrop_cleanup.ai.claude_analyzer import ClaudeAnalyzer


class TestClaudeAnalyzer:
    """Test cases for ClaudeAnalyzer."""

    def test_init_with_client(self, mock_anthropic_client):
        """Test initialization with provided client."""
        analyzer = ClaudeAnalyzer(client=mock_anthropic_client)
        assert analyzer.client == mock_anthropic_client

    @patch("raindrop_cleanup.ai.claude_analyzer.anthropic.Anthropic")
    def test_init_without_client(self, mock_anthropic_class):
        """Test initialization without provided client."""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        analyzer = ClaudeAnalyzer()
        assert analyzer.client == mock_client
        mock_anthropic_class.assert_called_once()

    @patch("raindrop_cleanup.ai.claude_analyzer.time.sleep")
    def test_rate_limit_applies_delay(self, mock_sleep, mock_anthropic_client):
        """Test that rate limiting applies appropriate delay."""
        analyzer = ClaudeAnalyzer(client=mock_anthropic_client)
        analyzer.last_call_time = 0

        with patch(
            "raindrop_cleanup.ai.claude_analyzer.time.time", side_effect=[0.5, 0.5]
        ):
            analyzer._rate_limit()

        mock_sleep.assert_called_once_with(
            0.5
        )  # Should sleep for remaining 0.5 seconds

    @patch("raindrop_cleanup.ai.claude_analyzer.time.sleep")
    def test_rate_limit_no_delay_needed(self, mock_sleep, mock_anthropic_client):
        """Test that rate limiting skips delay when enough time has passed."""
        analyzer = ClaudeAnalyzer(client=mock_anthropic_client)
        analyzer.last_call_time = 0

        with patch(
            "raindrop_cleanup.ai.claude_analyzer.time.time", side_effect=[2.0, 2.0]
        ):
            analyzer._rate_limit()

        mock_sleep.assert_not_called()

    def test_build_batch_info(self, mock_anthropic_client, mock_bookmarks):
        """Test building batch information string."""
        analyzer = ClaudeAnalyzer(client=mock_anthropic_client)
        batch_info = analyzer._build_batch_info(mock_bookmarks)

        assert "Python Tutorial" in batch_info
        assert "python.org" in batch_info
        assert "2024-01-15" in batch_info
        assert "https://python.org/tutorial" in batch_info
        assert "Learn Python programming" in batch_info

    def test_build_collection_info(self, mock_anthropic_client, mock_collections):
        """Test building collection information string."""
        analyzer = ClaudeAnalyzer(client=mock_anthropic_client)
        collection_info = analyzer._build_collection_info(
            mock_collections, "Development"
        )

        assert "AVAILABLE COLLECTIONS:" in collection_info
        assert "Development (150 items) ← CURRENT" in collection_info
        assert "Gaming (75 items)" in collection_info
        assert "Archive (500 items)" in collection_info

    def test_build_collection_info_no_collections(self, mock_anthropic_client):
        """Test building collection info with no collections."""
        analyzer = ClaudeAnalyzer(client=mock_anthropic_client)
        collection_info = analyzer._build_collection_info(None, "Test")

        assert collection_info == ""

    def test_build_analysis_prompt(self, mock_anthropic_client):
        """Test building complete analysis prompt."""
        analyzer = ClaudeAnalyzer(client=mock_anthropic_client)

        batch_info = "1. [Test Bookmark] - example.com"
        collection_info = "Collections: Test"

        prompt = analyzer._build_analysis_prompt(
            batch_info, collection_info, 1, "Development"
        )

        assert "helping someone with ADHD" in prompt
        assert "CURRENT COLLECTION: Development" in prompt
        assert batch_info in prompt
        assert collection_info in prompt
        assert "NEVER suggest MOVE to the current collection (Development)" in prompt

    def test_parse_batch_response_valid_responses(self, mock_anthropic_client):
        """Test parsing valid Claude responses."""
        analyzer = ClaudeAnalyzer(client=mock_anthropic_client)

        response = """1. DELETE - outdated tutorial
2. MOVE:Gaming - game guide
3. KEEP - useful reference
4. ARCHIVE - historical document"""

        decisions = analyzer._parse_batch_response(response, 4)

        assert len(decisions) == 4
        assert decisions[0] == {"action": "DELETE", "reasoning": "outdated tutorial"}
        assert decisions[1] == {
            "action": "MOVE",
            "target": "Gaming",
            "reasoning": "game guide",
        }
        assert decisions[2] == {"action": "KEEP", "reasoning": "useful reference"}
        assert decisions[3] == {"action": "ARCHIVE", "reasoning": "historical document"}

    def test_parse_batch_response_malformed_move(self, mock_anthropic_client):
        """Test parsing MOVE response without proper reasoning separator."""
        analyzer = ClaudeAnalyzer(client=mock_anthropic_client)

        response = "1. MOVE:InvalidFormat"

        decisions = analyzer._parse_batch_response(response, 1)

        assert len(decisions) == 1
        assert decisions[0]["action"] == "MOVE"
        assert decisions[0]["target"] == "InvalidFormat"
        assert decisions[0]["reasoning"] == "better organization"

    def test_parse_batch_response_unknown_action(self, mock_anthropic_client):
        """Test parsing unknown action response."""
        analyzer = ClaudeAnalyzer(client=mock_anthropic_client)

        response = "1. UNKNOWN - some reasoning"

        decisions = analyzer._parse_batch_response(response, 1)

        assert len(decisions) == 1
        assert decisions[0] == {"action": "KEEP", "reasoning": "unclear recommendation"}

    def test_parse_batch_response_insufficient_responses(self, mock_anthropic_client):
        """Test parsing when Claude doesn't provide enough responses."""
        analyzer = ClaudeAnalyzer(client=mock_anthropic_client)

        response = "1. DELETE - outdated"

        decisions = analyzer._parse_batch_response(response, 3)

        assert len(decisions) == 3
        assert decisions[0] == {"action": "DELETE", "reasoning": "outdated"}
        assert decisions[1] == {
            "action": "KEEP",
            "reasoning": "no recommendation received",
        }
        assert decisions[2] == {
            "action": "KEEP",
            "reasoning": "no recommendation received",
        }

    @patch("raindrop_cleanup.ai.claude_analyzer.time.time")
    def test_analyze_batch_success(
        self, mock_time, mock_anthropic_client, mock_bookmarks, mock_collections
    ):
        """Test successful batch analysis."""
        mock_time.return_value = 100.0

        mock_message = Mock()
        mock_message.content = [Mock()]
        mock_message.content[
            0
        ].text = """1. MOVE:Development - programming tutorial
2. MOVE:Gaming - game guide  
3. DELETE - outdated content"""

        mock_anthropic_client.messages.create.return_value = mock_message

        analyzer = ClaudeAnalyzer(client=mock_anthropic_client)
        decisions = analyzer.analyze_batch(mock_bookmarks, mock_collections, "Unsorted")

        assert len(decisions) == 3
        assert decisions[0]["action"] == "MOVE"
        assert decisions[0]["target"] == "Development"
        assert decisions[1]["action"] == "MOVE"
        assert decisions[1]["target"] == "Gaming"
        assert decisions[2]["action"] == "DELETE"

        # Verify API call was made with correct parameters
        mock_anthropic_client.messages.create.assert_called_once()
        call_args = mock_anthropic_client.messages.create.call_args
        assert call_args[1]["model"] == "claude-3-haiku-20240307"
        assert call_args[1]["max_tokens"] == 500
        assert len(call_args[1]["messages"]) == 1

    @patch("raindrop_cleanup.ai.claude_analyzer.time.time")
    def test_analyze_batch_api_error(
        self, mock_time, mock_anthropic_client, mock_bookmarks
    ):
        """Test batch analysis with API error."""
        mock_time.return_value = 100.0
        mock_anthropic_client.messages.create.side_effect = Exception("API Error")

        analyzer = ClaudeAnalyzer(client=mock_anthropic_client)
        decisions = analyzer.analyze_batch(mock_bookmarks)

        # Should return default KEEP decisions for all bookmarks
        assert len(decisions) == 3
        for decision in decisions:
            assert decision["action"] == "KEEP"
            assert decision["reasoning"] == "API error"

    def test_analyze_batch_empty_bookmarks(self, mock_anthropic_client):
        """Test batch analysis with empty bookmark list."""
        mock_message = Mock()
        mock_message.content = [Mock()]
        mock_message.content[0].text = ""
        mock_anthropic_client.messages.create.return_value = mock_message

        analyzer = ClaudeAnalyzer(client=mock_anthropic_client)
        decisions = analyzer.analyze_batch([])

        assert decisions == []
