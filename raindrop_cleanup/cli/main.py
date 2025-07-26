"""Command line interface for the Raindrop bookmark cleanup tool."""

import argparse
import os
from collections.abc import Sequence
from typing import Any, Optional

from ..core.processor import RaindropBookmarkCleaner


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="🌧️  Interactive Raindrop Bookmark Cleanup Tool - AI-powered bookmark curation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  raindrop-cleanup                            # Interactive mode
  raindrop-cleanup --batch-size 5             # Smaller batches
  raindrop-cleanup --list-collections         # Show collections and exit
  raindrop-cleanup --dry-run                  # Test without making changes

Environment Variables:
  ANTHROPIC_API_KEY   - Your Claude API key (required)
  RAINDROP_TOKEN      - Your Raindrop.io API token (required)
  RAINDROP_DEBUG      - Enable debug logging (1/true/yes/on)

ADHD-Friendly Features:
  • Shows Claude's recommendations with reasoning
  • You choose which actions to execute
  • Processes in small batches (default: 6 items)
  • Suggests breaks every 25 items
  • Shows real-time progress and statistics
  • Conservative defaults (keeps items when uncertain)
        """,
    )

    parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=6,
        help="Number of bookmarks to process in each batch (default: 6, recommended 4-8)",
    )

    parser.add_argument(
        "--list-collections",
        "-l",
        action="store_true",
        help="List all collections and exit (useful for planning)",
    )

    parser.add_argument(
        "--archive-name",
        default="Archive",
        help='Name of archive collection (default: "Archive")',
    )

    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be done without making changes",
    )

    parser.add_argument(
        "--resume",
        "-r",
        action="store_true",
        help="Show resumable sessions and choose one to continue",
    )

    parser.add_argument(
        "--clean-state", action="store_true", help="Clean up old state files"
    )

    parser.add_argument(
        "--text-mode",
        "-t",
        action="store_true",
        help="Use text-based interface instead of keyboard navigation",
    )

    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug logging for Claude AI analysis",
    )

    args = parser.parse_args()

    print("🌧️  Interactive Raindrop Bookmark Cleanup Tool")
    print("============================================")

    # Check for debug mode - CLI flag or environment variable
    debug_mode = args.debug or os.getenv("RAINDROP_DEBUG", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    if debug_mode:
        print(
            "🐛 Debug mode enabled - Claude AI analysis will be logged to .raindrop_debug/"
        )

    try:
        cleaner = RaindropBookmarkCleaner(
            dry_run=args.dry_run, text_mode=args.text_mode, debug=debug_mode
        )

        # Clean state files if requested
        if args.clean_state:
            count = cleaner.state_manager.clean_state_files()
            if count == 0:
                print("📝 No state files found to clean")
            return

        # Show resumable sessions if requested
        if args.resume:
            sessions = cleaner.state_manager.show_resumable_sessions()
            if not sessions:
                print("Starting a new session instead...")
            else:
                selected_session = _handle_resume_selection(sessions)
                if selected_session:
                    _resume_session(cleaner, selected_session, args)
                    return

        # Get all collections
        collections = cleaner.raindrop_client.get_collections()
        if not collections:
            print("❌ No collections found or API error")
            return

        # List collections if requested
        if args.list_collections:
            _list_collections(collections)
            return

        # Find archive collection
        archive_collection_id = cleaner.raindrop_client.find_collection_by_name(
            collections, args.archive_name
        )
        if archive_collection_id:
            print(f"📦 Found archive collection: {args.archive_name}")
        else:
            print(f"⚠️  Archive collection '{args.archive_name}' not found")

        # Interactive collection selection
        selected_collection = _select_collection(collections)
        if not selected_collection:
            return

        print(f"\n🚀 Starting cleanup of '{selected_collection['title']}'")
        print(f"📊 {selected_collection.get('count', 0)} bookmarks to review")

        if args.dry_run:
            print("🧪 DRY-RUN MODE: No changes will be made")

        input("\nPress Enter to begin...")

        # Process the selected collection
        cleaner.process_collection(
            collection_id=selected_collection["_id"],
            collection_name=selected_collection["title"],
            batch_size=args.batch_size,
            archive_collection_id=archive_collection_id,
            all_collections=collections,
            resume_from_state=True,  # Always try to resume by default
        )

        # Show final statistics
        cleaner.print_stats()

    except KeyboardInterrupt:
        print("\n\n⏹️  Cleanup interrupted by user")
        if "cleaner" in locals():
            cleaner.print_stats()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


def _handle_resume_selection(
    sessions: Sequence[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Handle selection of a resumable session."""
    print("🔄 Choose a session to resume:")
    print("Enter number, or 'new' for a fresh session:")

    while True:
        choice = input("📝 Your choice: ").strip().lower()

        if choice in ["new", "fresh", "n"]:
            return None  # Continue to regular collection selection

        try:
            session_index = int(choice) - 1
            if 0 <= session_index < len(sessions):
                return sessions[session_index]
        except (ValueError, IndexError):
            pass

        print("❌ Invalid choice. Try a number, or 'new' for fresh session.")


def _resume_session(
    cleaner: RaindropBookmarkCleaner, session: dict[str, Any], args: argparse.Namespace
) -> None:
    """Resume a selected session."""
    collections = cleaner.raindrop_client.get_collections()
    selected_collection = None

    for col in collections:
        if col["_id"] == session["collection_id"]:
            selected_collection = col
            break

    if not selected_collection:
        print("❌ Collection no longer exists")
        return

    print(f"\n🔄 Resuming '{selected_collection['title']}'...")

    # Find archive collection
    archive_collection_id = cleaner.raindrop_client.find_collection_by_name(
        collections, args.archive_name
    )

    # Resume processing
    cleaner.process_collection(
        collection_id=selected_collection["_id"],
        collection_name=selected_collection["title"],
        batch_size=args.batch_size,
        archive_collection_id=archive_collection_id,
        all_collections=collections,
        resume_from_state=True,
    )

    cleaner.print_stats()


def _list_collections(collections: Sequence[dict[str, Any]]) -> None:
    """List all collections."""
    from ..state.manager import StateManager

    state_manager = StateManager()

    print(f"\n📚 Found {len(collections)} collections:")
    for col in collections:
        count = col.get("count", 0)

        # Check for existing state
        processed_info = ""
        state = state_manager.load_state(col["_id"], col["title"])
        if state:
            processed_count = len(state.get("processed_bookmark_ids", set()))
            processed_info = f" - {processed_count} processed"

        print(f"  📁 {col['title']} ({count} items{processed_info}) - ID: {col['_id']}")


def _select_collection(
    collections: Sequence[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Interactively select a collection to process."""
    from ..state.manager import StateManager

    state_manager = StateManager()

    print("\n📚 Available collections:")
    for i, col in enumerate(collections):
        count = col.get("count", 0)

        # Check for existing state
        processed_info = ""
        state = state_manager.load_state(col["_id"], col["title"])
        if state:
            processed_count = len(state.get("processed_bookmark_ids", set()))
            processed_info = f" - {processed_count} processed"

        print(f"  {i+1:2d}. {col['title']} ({count} items{processed_info})")

    print("\n🎯 Which collection would you like to process?")
    print("Enter number, name, or 'quit' to exit:")

    while True:
        choice = input("📝 Your choice: ").strip()

        if choice.lower() in ["quit", "exit", "q"]:
            print("👋 Goodbye!")
            return None

        # Try to parse as number
        try:
            col_index = int(choice) - 1
            if 0 <= col_index < len(collections):
                return collections[col_index]
        except ValueError:
            pass

        # Try to find by name
        for col in collections:
            if choice.lower() in col["title"].lower():
                return col

        print("❌ Collection not found. Try again or 'quit' to exit.")


if __name__ == "__main__":
    main()
