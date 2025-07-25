"""Tests for the Raindrop API client."""

import os
import pytest
from unittest.mock import Mock, patch
from raindrop_cleanup.api.raindrop_client import RaindropClient


class TestRaindropClient:
    """Test cases for RaindropClient."""
    
    def test_init_with_token(self, mock_raindrop_token):
        """Test initialization with explicit token."""
        client = RaindropClient(token=mock_raindrop_token)
        assert client.token == mock_raindrop_token
        assert client.headers['Authorization'] == f'Bearer {mock_raindrop_token}'
    
    @patch.dict(os.environ, {'RAINDROP_TOKEN': 'env_token_123'})
    def test_init_with_env_token(self):
        """Test initialization with environment variable token."""
        client = RaindropClient()
        assert client.token == 'env_token_123'
        assert client.headers['Authorization'] == 'Bearer env_token_123'
    
    def test_init_no_token_raises_error(self):
        """Test that missing token raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Please set RAINDROP_TOKEN"):
                RaindropClient()
    
    @patch('raindrop_cleanup.api.raindrop_client.requests.get')
    def test_get_collections_success(self, mock_get, mock_raindrop_token, mock_collections):
        """Test successful collection retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'items': mock_collections}
        mock_get.return_value = mock_response
        
        client = RaindropClient(token=mock_raindrop_token)
        collections = client.get_collections()
        
        assert collections == mock_collections
        mock_get.assert_called_once_with(
            "https://api.raindrop.io/rest/v1/collections",
            headers=client.headers
        )
    
    @patch('raindrop_cleanup.api.raindrop_client.requests.get')
    def test_get_collections_failure(self, mock_get, mock_raindrop_token):
        """Test collection retrieval failure."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        client = RaindropClient(token=mock_raindrop_token)
        collections = client.get_collections()
        
        assert collections == []
    
    @patch('raindrop_cleanup.api.raindrop_client.requests.get')
    def test_get_bookmarks_from_collection_success(self, mock_get, mock_raindrop_token, mock_bookmarks):
        """Test successful bookmark retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'items': mock_bookmarks}
        mock_get.return_value = mock_response
        
        client = RaindropClient(token=mock_raindrop_token)
        result = client.get_bookmarks_from_collection(collection_id=1, page=0)
        
        assert result == {'items': mock_bookmarks}
        mock_get.assert_called_once_with(
            "https://api.raindrop.io/rest/v1/raindrops/1",
            headers=client.headers,
            params={
                'page': 0,
                'perpage': 50,
                'sort': '-created'
            }
        )
    
    @patch('raindrop_cleanup.api.raindrop_client.requests.get')
    def test_get_bookmarks_from_collection_failure(self, mock_get, mock_raindrop_token):
        """Test bookmark retrieval failure."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        client = RaindropClient(token=mock_raindrop_token)
        result = client.get_bookmarks_from_collection(collection_id=999)
        
        assert result == {}
    
    @patch('raindrop_cleanup.api.raindrop_client.requests.delete')
    def test_delete_bookmark_success(self, mock_delete, mock_raindrop_token):
        """Test successful bookmark deletion."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_delete.return_value = mock_response
        
        client = RaindropClient(token=mock_raindrop_token)
        result = client.delete_bookmark(bookmark_id=123)
        
        assert result is True
        mock_delete.assert_called_once_with(
            "https://api.raindrop.io/rest/v1/raindrop/123",
            headers=client.headers
        )
    
    @patch('raindrop_cleanup.api.raindrop_client.requests.delete')
    def test_delete_bookmark_failure(self, mock_delete, mock_raindrop_token):
        """Test bookmark deletion failure."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_delete.return_value = mock_response
        
        client = RaindropClient(token=mock_raindrop_token)
        result = client.delete_bookmark(bookmark_id=999)
        
        assert result is False
    
    @patch('raindrop_cleanup.api.raindrop_client.requests.put')
    def test_move_bookmark_success(self, mock_put, mock_raindrop_token):
        """Test successful bookmark move."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_put.return_value = mock_response
        
        client = RaindropClient(token=mock_raindrop_token)
        result = client.move_bookmark_to_collection(bookmark_id=123, collection_id=456)
        
        assert result is True
        mock_put.assert_called_once_with(
            "https://api.raindrop.io/rest/v1/raindrop/123",
            headers=client.headers,
            json={'collection': {'$id': 456}}
        )
    
    @patch('raindrop_cleanup.api.raindrop_client.requests.put')
    def test_move_bookmark_failure(self, mock_put, mock_raindrop_token):
        """Test bookmark move failure."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_put.return_value = mock_response
        
        client = RaindropClient(token=mock_raindrop_token)
        result = client.move_bookmark_to_collection(bookmark_id=123, collection_id=999)
        
        assert result is False
    
    def test_find_collection_by_name_exact_match(self, mock_raindrop_token, mock_collections):
        """Test finding collection by exact name match."""
        client = RaindropClient(token=mock_raindrop_token)
        collection_id = client.find_collection_by_name(mock_collections, "Development")
        
        assert collection_id == 2
    
    def test_find_collection_by_name_partial_match(self, mock_raindrop_token, mock_collections):
        """Test finding collection by partial name match."""
        client = RaindropClient(token=mock_raindrop_token)
        collection_id = client.find_collection_by_name(mock_collections, "dev")
        
        assert collection_id == 2
    
    def test_find_collection_by_name_case_insensitive(self, mock_raindrop_token, mock_collections):
        """Test finding collection with case insensitive matching."""
        client = RaindropClient(token=mock_raindrop_token)
        collection_id = client.find_collection_by_name(mock_collections, "GAMING")
        
        assert collection_id == 3
    
    def test_find_collection_by_name_not_found(self, mock_raindrop_token, mock_collections):
        """Test collection name not found."""
        client = RaindropClient(token=mock_raindrop_token)
        collection_id = client.find_collection_by_name(mock_collections, "NonExistent")
        
        assert collection_id is None