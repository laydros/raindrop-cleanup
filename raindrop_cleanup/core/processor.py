"""Core bookmark processing logic that orchestrates all components."""

import anthropic
from datetime import datetime
from typing import List, Dict, Optional

from ..api.raindrop_client import RaindropClient
from ..ai.claude_analyzer import ClaudeAnalyzer
from ..ui.interfaces import UserInterface
from ..state.manager import StateManager


class RaindropBookmarkCleaner:
    """Main processor that orchestrates bookmark cleanup workflow."""

    def __init__(
        self,
        dry_run: bool = False,
        state_dir: str = ".raindrop_state",
        text_mode: bool = False,
    ):
        """Initialize the bookmark cleaner.

        Args:
            dry_run: If True, don't make actual changes to bookmarks
            state_dir: Directory to store session state files
            text_mode: If True, use text interface instead of keyboard navigation
        """
        # Initialize components
        self.raindrop_client = RaindropClient()
        self.claude_analyzer = ClaudeAnalyzer()
        self.ui = UserInterface(text_mode=text_mode)
        self.state_manager = StateManager(state_dir=state_dir)

        # Configuration
        self.dry_run = dry_run

    def process_collection(
        self,
        collection_id: int,
        collection_name: str,
        batch_size: int = 6,
        archive_collection_id: Optional[int] = None,
        all_collections: Optional[List[Dict]] = None,
        resume_from_state: bool = True,
    ):
        """Process all bookmarks in a collection with interactive decisions.

        Args:
            collection_id: ID of the collection to process
            collection_name: Name of the collection
            batch_size: Number of bookmarks to process in each batch
            archive_collection_id: ID of archive collection if available
            all_collections: List of all collections for MOVE operations
            resume_from_state: Whether to attempt to resume from saved state
        """
        print(f"\n🚀 Processing collection: {collection_name}")
        print(f"Collection ID: {collection_id}")

        # Try to load previous state
        start_page = 0
        if resume_from_state:
            previous_state = self.state_manager.load_state(
                collection_id, collection_name
            )
            if previous_state:
                start_page = previous_state.get("current_page", 0)
                processed_count = len(self.state_manager.processed_bookmark_ids)
                print(f"\n🔄 Found previous session state:")
                print(f"   📊 {processed_count} bookmarks already processed")
                print(f"   📄 Ready to resume from page {start_page + 1}")
                print(f"\n⚠️  IMPORTANT: This will continue from where you left off.")
                print(f"   You will see recommendations for NEW bookmarks only.")
                
                resume_choice = (
                    input(f"\n🔄 Resume this session? (Y/n): ")
                    .strip()
                    .lower()
                )
                if resume_choice in ["n", "no"]:
                    print("🆕 Starting completely fresh session")
                    self.state_manager.processed_bookmark_ids.clear()
                    start_page = 0
                    # Reset stats
                    self.state_manager.stats = {
                        "processed": 0,
                        "kept": 0,
                        "deleted": 0,
                        "archived": 0,
                        "moved": 0,
                        "errors": 0,
                        "skipped": 0,
                        "start_time": datetime.now(),
                        "session_time": 0,
                    }
                else:
                    print("✅ Resuming previous session")

        page = start_page
        total_processed = 0
        global_batch_num = 0

        try:
            while True:
                # Get batch of bookmarks
                data = self.raindrop_client.get_bookmarks_from_collection(
                    collection_id, page
                )
                bookmarks = data.get("items", [])

                if not bookmarks:
                    break

                # Filter out already processed bookmarks
                unprocessed_bookmarks = [
                    bookmark
                    for bookmark in bookmarks
                    if not self.state_manager.is_bookmark_processed(bookmark["_id"])
                ]

                if not unprocessed_bookmarks:
                    print(
                        f"📄 Page {page + 1}: All {len(bookmarks)} bookmarks already processed, skipping..."
                    )
                    page += 1
                    continue

                print(
                    f"\n📦 Processing page {page + 1} - {len(unprocessed_bookmarks)} new bookmarks (of {len(bookmarks)} total)"
                )

                # Process in smaller batches for ADHD-friendly sessions
                for i in range(0, len(unprocessed_bookmarks), batch_size):
                    batch = unprocessed_bookmarks[i : i + batch_size]
                    global_batch_num += 1

                    print(f"\n{'='*60}")
                    print(
                        f"📋 BATCH {global_batch_num} ({len(batch)} bookmarks)"
                    )
                    print(f"{'='*60}")

                    # Get AI recommendations
                    print("🤖 Getting Claude's recommendations...")
                    print(
                        "    (Based on: title, URL, domain, and excerpt - not full content)"
                    )
                    decisions = self.claude_analyzer.analyze_batch(
                        batch, all_collections, collection_name
                    )

                    # Show recommendations and get user choices  
                    print(f"\n🔍 Claude's recommendations ready - showing interface...")
                    batch_info = f"Batch {global_batch_num}"
                    selected_indices = self.ui.display_batch_decisions(
                        batch, decisions, collection_name, batch_info
                    )
                    
                    # Safety confirmation - never execute without explicit user confirmation
                    if selected_indices:
                        print(f"\n⚠️  About to execute {len(selected_indices)} actions:")
                        for i in selected_indices:
                            bookmark = batch[i]
                            decision = decisions[i]
                            title = bookmark.get("title", "Untitled")[:50]
                            action = decision.get("action", "KEEP")
                            if action == "MOVE":
                                target = decision.get("target", "Unknown")
                                print(f"    🔄 MOVE to {target}: {title}")
                            elif action == "DELETE":
                                print(f"    ❌ DELETE: {title}")
                            elif action == "ARCHIVE":
                                print(f"    📦 ARCHIVE: {title}")
                        print("\nPress Enter to confirm, or Ctrl+C to cancel...")
                        try:
                            input()
                        except KeyboardInterrupt:
                            print("❌ Actions cancelled by user")
                            return

                    # Execute user's choices
                    self._execute_user_selections(
                        batch,
                        decisions,
                        selected_indices,
                        all_collections,
                        archive_collection_id,
                    )

                    total_processed += len(batch)

                    # Save state after each batch
                    self.state_manager.save_state(collection_id, collection_name, page)

                    # Progress update
                    elapsed = datetime.now() - self.state_manager.stats["start_time"]
                    rate = (
                        len(self.state_manager.processed_bookmark_ids)
                        / elapsed.total_seconds()
                        * 60
                        if elapsed.total_seconds() > 0
                        else 0
                    )
                    print(
                        f"\n📊 Session Progress: {len(self.state_manager.processed_bookmark_ids)} total processed | Rate: {rate:.1f}/min"
                    )

                page += 1

                # Safety check to avoid infinite loops
                if page > 100:
                    print("⚠️  Reached page limit, stopping")
                    break

        except KeyboardInterrupt:
            print(f"\n\n⏹️  Processing interrupted - progress saved!")
            self.state_manager.save_state(collection_id, collection_name, page)
            raise

        # Collection completed - clean up state file
        self.state_manager.cleanup_state_file()

        print(f"\n✅ Completed collection: {collection_name}")
        print(f"   Total bookmarks processed this session: {total_processed}")
        print(
            f"   Total bookmarks processed overall: {len(self.state_manager.processed_bookmark_ids)}"
        )

    def _execute_user_selections(
        self,
        bookmarks: List[Dict],
        decisions: List[Dict],
        selected_indices: List[int],
        all_collections: Optional[List[Dict]],
        archive_collection_id: Optional[int] = None,
    ):
        """Execute the user's selected actions.

        Args:
            bookmarks: List of bookmark dictionaries
            decisions: List of AI decision dictionaries
            selected_indices: Indices of bookmarks to process
            all_collections: List of all collections for MOVE operations
            archive_collection_id: ID of archive collection if available
        """
        if not selected_indices:
            print("⏭️  Skipping all items in this batch")
            # Still mark these as processed so we don't see them again
            for bookmark in bookmarks:
                self.state_manager.add_processed_bookmark(bookmark["_id"])
            self.state_manager.update_stats(skipped=len(bookmarks))
            return

        print(f"\n🚀 EXECUTING {len(selected_indices)} ACTIONS...")

        # Mark all bookmarks in this batch as processed (including unselected ones)
        for bookmark in bookmarks:
            self.state_manager.add_processed_bookmark(bookmark["_id"])

        for i in selected_indices:
            bookmark = bookmarks[i]
            decision = decisions[i]
            bookmark_id = bookmark["_id"]
            title = bookmark.get("title", "Untitled")[:50]
            action = decision.get("action", "KEEP")

            if action == "DELETE":
                if self.dry_run or self.raindrop_client.delete_bookmark(bookmark_id):
                    print(
                        f"    ❌ {'[DRY-RUN] ' if self.dry_run else ''}DELETED: {title}"
                    )
                    self.state_manager.update_stats(deleted=1)
                else:
                    print(f"    ⚠️  Failed to delete: {title}")
                    self.state_manager.update_stats(errors=1)

            elif action == "ARCHIVE" and archive_collection_id:
                if self.dry_run or self.raindrop_client.move_bookmark_to_collection(
                    bookmark_id, archive_collection_id
                ):
                    print(
                        f"    📦 {'[DRY-RUN] ' if self.dry_run else ''}ARCHIVED: {title}"
                    )
                    self.state_manager.update_stats(archived=1)
                else:
                    print(f"    ⚠️  Failed to archive: {title}")
                    self.state_manager.update_stats(errors=1)

            elif action == "MOVE" and all_collections:
                target_name = decision.get("target", "")
                target_id = self.raindrop_client.find_collection_by_name(
                    all_collections, target_name
                )

                if target_id:
                    if (
                        self.dry_run
                        or self.raindrop_client.move_bookmark_to_collection(
                            bookmark_id, target_id
                        )
                    ):
                        print(
                            f"    🔄 {'[DRY-RUN] ' if self.dry_run else ''}MOVED to {target_name}: {title}"
                        )
                        self.state_manager.update_stats(moved=1)
                    else:
                        print(f"    ⚠️  Failed to move to {target_name}: {title}")
                        self.state_manager.update_stats(errors=1)
                else:
                    print(f"    ⚠️  Collection '{target_name}' not found: {title}")
                    self.state_manager.update_stats(errors=1)

            self.state_manager.update_stats(processed=1)

        # Mark unselected items as kept
        unselected_count = len(bookmarks) - len(selected_indices)
        if unselected_count > 0:
            self.state_manager.update_stats(kept=unselected_count)

    def print_stats(self):
        """Print final statistics."""
        self.state_manager.print_stats(dry_run=self.dry_run)
