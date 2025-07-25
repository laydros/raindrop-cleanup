"""Raindrop.io API client for bookmark management."""

import os
import requests
from typing import List, Dict, Optional


class RaindropClient:
    """Client for interacting with the Raindrop.io API."""
    
    def __init__(self, token: Optional[str] = None):
        """Initialize the Raindrop API client.
        
        Args:
            token: Raindrop.io API token. If not provided, will look for RAINDROP_TOKEN env var.
            
        Raises:
            ValueError: If no token is provided or found in environment.
        """
        self.token = token or os.getenv('RAINDROP_TOKEN')
        
        if not self.token:
            raise ValueError("Please set RAINDROP_TOKEN environment variable or provide token")
        
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
    
    def get_collections(self) -> List[Dict]:
        """Get all Raindrop collections.
        
        Returns:
            List of collection dictionaries with id, title, count, etc.
        """
        url = "https://api.raindrop.io/rest/v1/collections"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.json().get('items', [])
        else:
            print(f"Error fetching collections: {response.status_code}")
            return []
    
    def get_bookmarks_from_collection(self, collection_id: int, page: int = 0) -> Dict:
        """Get bookmarks from a specific collection.
        
        Args:
            collection_id: ID of the collection to fetch bookmarks from
            page: Page number for pagination (0-based)
            
        Returns:
            Dictionary containing bookmarks and pagination info
        """
        url = f"https://api.raindrop.io/rest/v1/raindrops/{collection_id}"
        params = {
            'page': page,
            'perpage': 50,  # Max allowed by API
            'sort': '-created'  # Newest first
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching bookmarks: {response.status_code}")
            return {}
    
    def delete_bookmark(self, bookmark_id: int) -> bool:
        """Delete a bookmark from Raindrop.
        
        Args:
            bookmark_id: ID of the bookmark to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        url = f"https://api.raindrop.io/rest/v1/raindrop/{bookmark_id}"
        response = requests.delete(url, headers=self.headers)
        return response.status_code == 200
    
    def move_bookmark_to_collection(self, bookmark_id: int, collection_id: int) -> bool:
        """Move bookmark to different collection.
        
        Args:
            bookmark_id: ID of the bookmark to move
            collection_id: ID of the target collection
            
        Returns:
            True if move was successful, False otherwise
        """
        url = f"https://api.raindrop.io/rest/v1/raindrop/{bookmark_id}"
        data = {'collection': {'$id': collection_id}}
        response = requests.put(url, headers=self.headers, json=data)
        return response.status_code == 200
    
    def find_collection_by_name(self, collections: List[Dict], name: str) -> Optional[int]:
        """Find collection ID by name with fuzzy matching.
        
        Args:
            collections: List of collection dictionaries
            name: Name to search for
            
        Returns:
            Collection ID if found, None otherwise
        """
        name_lower = name.lower().strip()
        
        # Exact match first
        for collection in collections:
            if collection['title'].lower() == name_lower:
                return collection['_id']
        
        # Partial match
        for collection in collections:
            if name_lower in collection['title'].lower() or collection['title'].lower() in name_lower:
                return collection['_id']
        
        return None