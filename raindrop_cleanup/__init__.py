"""
🌧️ Raindrop Cleanup Tool

An interactive, AI-powered bookmark cleanup tool for Raindrop.io designed with
ADHD-friendly features to help you declutter and organize your bookmarks efficiently.
"""

__version__ = "1.0.0"
__author__ = "Jason Hamilton"
__license__ = "BSD 3-Clause"

from .core.processor import RaindropBookmarkCleaner

__all__ = ["RaindropBookmarkCleaner"]
