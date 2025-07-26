"""Raindrop.io API client for bookmark management."""

import os
from typing import Any, Optional

import requests
from requests.exceptions import RequestException


class RaindropClient:
    """Client for interacting with the Raindrop.io API."""

    def __init__(self, token: Optional[str] = None):
        """Initialize the Raindrop API client.

        Args:
            token: Raindrop.io API token. If not provided, will look for RAINDROP_TOKEN env var.

        Raises:
            ValueError: If no token is provided or found in environment.
        """
        self.token = token or os.getenv("RAINDROP_TOKEN")

        if not self.token:
            raise ValueError(
                "Please set RAINDROP_TOKEN environment variable or provide token"
            )

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def get_collections(self) -> list[dict[str, Any]]:
        """Get all Raindrop collections.

        Returns:
            List of collection dictionaries with id, title, count, etc.
        """
        url = "https://api.raindrop.io/rest/v1/collections"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json().get("items", [])
        except (RequestException, ValueError) as e:
            print(f"Error fetching collections: {e}")
            return []

    def get_bookmarks_from_collection(
        self, collection_id: int, page: int = 0
    ) -> dict[str, Any]:
        """Get bookmarks from a specific collection.

        Args:
            collection_id: ID of the collection to fetch bookmarks from
            page: Page number for pagination (0-based)

        Returns:
            Dictionary containing bookmarks and pagination info
        """
        url = f"https://api.raindrop.io/rest/v1/raindrops/{collection_id}"
        params = {
            "page": page,
            "perpage": 50,  # Max allowed by API
            "sort": "-created",  # Newest first
        }
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except (RequestException, ValueError) as e:
            print(f"Error fetching bookmarks: {e}")
            return {}

    def delete_bookmark(self, bookmark_id: int) -> bool:
        """Delete a bookmark from Raindrop.

        Args:
            bookmark_id: ID of the bookmark to delete

        Returns:
            True if deletion was successful, False otherwise
        """
        url = f"https://api.raindrop.io/rest/v1/raindrop/{bookmark_id}"
        try:
            response = requests.delete(url, headers=self.headers)
            response.raise_for_status()
            return True
        except RequestException as e:
            print(f"Error deleting bookmark {bookmark_id}: {e}")
            return False

    def move_bookmark_to_collection(self, bookmark_id: int, collection_id: int) -> bool:
        """Move bookmark to different collection.

        Args:
            bookmark_id: ID of the bookmark to move
            collection_id: ID of the target collection

        Returns:
            True if move was successful, False otherwise
        """
        url = f"https://api.raindrop.io/rest/v1/raindrop/{bookmark_id}"
        data = {"collection": {"$id": collection_id}}
        try:
            response = requests.put(url, headers=self.headers, json=data)
            response.raise_for_status()
            return True
        except RequestException as e:
            print(f"Error moving bookmark {bookmark_id}: {e}")
            return False

    def find_collection_by_name(
        self, collections: list[dict[str, Any]], name: str
    ) -> Optional[int]:
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
            if collection["title"].lower() == name_lower:
                return int(collection["_id"])

        # Partial match
        for collection in collections:
            if (
                name_lower in collection["title"].lower()
                or collection["title"].lower() in name_lower
            ):
                return int(collection["_id"])

        return None
