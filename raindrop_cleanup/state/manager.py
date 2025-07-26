"""Session state management and persistence for resumable bookmark cleanup."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class StateManager:
    """Manages session state and persistence for resumable bookmark cleanup."""

    def __init__(self, state_dir: str = ".raindrop_state"):
        """Initialize the state manager.

        Args:
            state_dir: Directory to store state files
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        self.current_state_file: Optional[Path] = None
        self.processed_bookmark_ids: set[int] = set()

        # Initialize stats
        self.stats: dict[str, Any] = {
            "processed": 0,
            "kept": 0,
            "deleted": 0,
            "archived": 0,
            "moved": 0,
            "errors": 0,
            "skipped": 0,
            "start_time": datetime.now(),
            "session_time": 0,  # Track time across resume sessions
        }

    def get_state_filename(self, collection_id: int, collection_name: str) -> Path:
        """Generate state filename for a collection.

        Args:
            collection_id: ID of the collection
            collection_name: Name of the collection

        Returns:
            Path to the state file
        """
        safe_name = "".join(
            c for c in collection_name if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        safe_name = safe_name.replace(" ", "_")
        return self.state_dir / f"collection_{collection_id}_{safe_name}.json"

    def save_state(
        self, collection_id: int, collection_name: str, current_page: int = 0
    ) -> None:
        """Save current processing state.

        Args:
            collection_id: ID of the collection being processed
            collection_name: Name of the collection
            current_page: Current page number being processed
        """
        state: dict[str, Any] = {
            "collection_id": collection_id,
            "collection_name": collection_name,
            "current_page": current_page,
            "processed_bookmark_ids": list(self.processed_bookmark_ids),
            "stats": self.stats.copy(),
            "last_updated": datetime.now().isoformat(),
            "dry_run": False,  # Will be set by processor if needed
        }

        # Update session time
        if "start_time" in self.stats and isinstance(
            self.stats["start_time"], datetime
        ):
            elapsed = datetime.now() - self.stats["start_time"]
            state["stats"]["session_time"] = (
                self.stats.get("session_time", 0) + elapsed.total_seconds()
            )

        state_file = self.get_state_filename(collection_id, collection_name)
        self.current_state_file = state_file

        with open(state_file, "w") as f:
            json.dump(state, f, indent=2, default=str)

        print(f"💾 State saved to {state_file.name}")

    def load_state(
        self, collection_id: int, collection_name: str
    ) -> Optional[dict[str, Any]]:
        """Load previous processing state if it exists.

        Args:
            collection_id: ID of the collection
            collection_name: Name of the collection

        Returns:
            Loaded state dictionary or None if not found/invalid
        """
        state_file = self.get_state_filename(collection_id, collection_name)

        if not state_file.exists():
            return None

        try:
            with open(state_file) as f:
                state: dict[str, Any] = json.load(f)

            # Validate state
            if (
                state.get("collection_id") != collection_id
                or state.get("collection_name") != collection_name
            ):
                return None

            self.processed_bookmark_ids = set(state.get("processed_bookmark_ids", []))

            # Restore stats but update start time
            saved_stats = state.get("stats", {})
            self.stats.update(saved_stats)
            self.stats["start_time"] = datetime.now()  # Reset for this session

            # Track the state file so it can be cleaned up later
            self.current_state_file = state_file

            return state

        except (json.JSONDecodeError, KeyError) as e:
            print(f"⚠️  Error loading state file: {e}")
            print("Starting fresh...")
            return None

    def cleanup_state_file(self) -> None:
        """Remove state file when collection processing is complete."""
        if self.current_state_file and self.current_state_file.exists():
            self.current_state_file.unlink()
            print(f"🧹 Cleaned up state file: {self.current_state_file.name}")

    def list_resumable_sessions(self) -> list[dict[str, Any]]:
        """List all resumable sessions.

        Returns:
            List of session dictionaries with metadata
        """
        sessions = []

        for state_file in self.state_dir.glob("collection_*.json"):
            try:
                with open(state_file) as f:
                    state = json.load(f)

                last_updated = datetime.fromisoformat(
                    state.get("last_updated", "1970-01-01")
                )
                sessions.append(
                    {
                        "file": state_file,
                        "collection_name": state.get("collection_name", "Unknown"),
                        "collection_id": state.get("collection_id"),
                        "processed_count": len(state.get("processed_bookmark_ids", [])),
                        "last_updated": last_updated,
                        "stats": state.get("stats", {}),
                    }
                )
            except (json.JSONDecodeError, KeyError):
                continue

        return sorted(sessions, key=lambda x: x["last_updated"], reverse=True)

    def show_resumable_sessions(self) -> Optional[list[dict[str, Any]]]:
        """Show available sessions that can be resumed.

        Returns:
            List of sessions or None if no sessions found
        """
        sessions = self.list_resumable_sessions()

        if not sessions:
            print("📝 No resumable sessions found.")
            return None

        print(f"\n📚 Resumable Sessions ({len(sessions)} found):")
        print("=" * 70)

        for i, session in enumerate(sessions):
            stats = session["stats"]
            elapsed_str = ""
            if stats.get("session_time"):
                session_time = stats["session_time"]
                if isinstance(session_time, (int, float)):
                    elapsed_str = f" | {session_time/60:.1f}min"

            print(f"{i+1:2d}. {session['collection_name']}")
            print(
                f"    📊 {session['processed_count']} processed | "
                f"{stats.get('deleted', 0)} deleted | "
                f"{stats.get('moved', 0)} moved{elapsed_str}"
            )
            print(
                f"    📅 Last updated: {session['last_updated'].strftime('%Y-%m-%d %H:%M')}"
            )
            print()

        return sessions

    def clean_state_files(self) -> int:
        """Clean up all state files in the state directory.

        Returns:
            Number of files cleaned up
        """
        state_files = list(self.state_dir.glob("collection_*.json"))

        if not state_files:
            return 0

        print(f"🧹 Found {len(state_files)} state files to clean:")
        for state_file in state_files:
            print(f"   {state_file.name}")

        confirm = input("Delete all? (y/N): ").strip().lower()
        if confirm in ["y", "yes"]:
            for state_file in state_files:
                state_file.unlink()
            print("✅ State files cleaned!")
            return len(state_files)
        else:
            print("❌ Cancelled")
            return 0

    def print_stats(
        self,
        dry_run: bool = False,
        initial_count: Optional[int] = None,
        final_count: Optional[int] = None,
    ) -> None:
        """Print final statistics.

        Args:
            dry_run: Whether this was a dry run
            initial_count: Initial bookmark count in collection
            final_count: Final bookmark count in collection
        """
        start_time = self.stats.get("start_time")
        if not isinstance(start_time, datetime):
            start_time = datetime.now()  # Fallback

        current_elapsed = datetime.now() - start_time
        total_session_time = (
            self.stats.get("session_time", 0) + current_elapsed.total_seconds()
        )

        print(f"\n{'='*60}")
        print(f"🎉 BOOKMARK CLEANUP {'SIMULATION' if dry_run else 'COMPLETE'}!")
        print(f"{ '='*60}")
        print(f"⏱️  This session: {current_elapsed}")
        if self.stats.get("session_time", 0) > 0:
            print(
                f"⏱️  Total time: {total_session_time/60:.1f} minutes (across sessions)"
            )
        # Show collection statistics if available
        if initial_count is not None and final_count is not None:
            print(f"📊 Collection at start: {initial_count} bookmarks")
            print(f"📊 Collection now: {final_count} bookmarks")
            print(f"📊 Net change: {initial_count - final_count} bookmarks")
            print()

        print(f"📊 Total processed: {len(self.processed_bookmark_ids)}")
        print(f"📋 Actions taken: {self.stats['processed']}")
        print(f"✅ Kept: {self.stats['kept']}")
        print(f"❌ Deleted: {self.stats['deleted']}")
        print(f"📦 Archived: {self.stats['archived']}")
        print(f"🔄 Moved: {self.stats['moved']}")
        print(f"⏭️  Skipped: {self.stats['skipped']}")
        print(f"⚠️  Errors: {self.stats['errors']}")

        # Calculate percentages based on total actions taken (excluding skipped items)
        total_actions = (
            self.stats["kept"]
            + self.stats["deleted"]
            + self.stats["archived"]
            + self.stats["moved"]
        )
        if total_actions > 0:
            kept_pct = (self.stats["kept"] / total_actions) * 100
            deleted_pct = (self.stats["deleted"] / total_actions) * 100
            print(f"📈 Kept: {kept_pct:.1f}% | Deleted: {deleted_pct:.1f}%")

    def add_processed_bookmark(self, bookmark_id: int) -> None:
        """Add a bookmark ID to the processed set.

        Args:
            bookmark_id: ID of the processed bookmark
        """
        self.processed_bookmark_ids.add(bookmark_id)

    def is_bookmark_processed(self, bookmark_id: int) -> bool:
        """Check if a bookmark has already been processed.

        Args:
            bookmark_id: ID of the bookmark to check

        Returns:
            True if bookmark has been processed, False otherwise
        """
        return bookmark_id in self.processed_bookmark_ids

    def update_stats(self, **kwargs: Any) -> None:
        """Update statistics counters.

        Args:
            **kwargs: Stat names and values to update
        """
        for key, value in kwargs.items():
            if key in self.stats:
                self.stats[key] += value
