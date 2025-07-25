import os
import requests
import anthropic
import time
import json
import curses
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

class RaindropBookmarkCleaner:
    def __init__(self, dry_run=False, state_dir=".raindrop_state", text_mode=False):
        # Initialize APIs
        self.claude_client = anthropic.Anthropic()
        self.raindrop_token = os.getenv('RAINDROP_TOKEN')
        self.dry_run = dry_run
        self.text_mode = text_mode
        
        if not self.raindrop_token:
            raise ValueError("Please set RAINDROP_TOKEN environment variable")
        
        self.raindrop_headers = {
            'Authorization': f'Bearer {self.raindrop_token}',
            'Content-Type': 'application/json'
        }
        
        # State management
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        self.current_state_file = None
        self.processed_bookmark_ids = set()
        
        # Processing stats
        self.stats = {
            'processed': 0,
            'kept': 0,
            'deleted': 0,
            'archived': 0,
            'moved': 0,
            'errors': 0,
            'skipped': 0,
            'start_time': datetime.now(),
            'session_time': 0  # Track time across resume sessions
        }
        
        # Rate limiting
        self.last_claude_call = 0
        self.claude_delay = 1  # seconds between Claude calls
        
    def get_raindrop_collections(self) -> List[Dict]:
        """Get all Raindrop collections"""
        url = "https://api.raindrop.io/rest/v1/collections"
        response = requests.get(url, headers=self.raindrop_headers)
        
        if response.status_code == 200:
            return response.json().get('items', [])
        else:
            print(f"Error fetching collections: {response.status_code}")
            return []
    
    def get_bookmarks_from_collection(self, collection_id: int, page: int = 0) -> Dict:
        """Get bookmarks from a specific collection"""
        url = f"https://api.raindrop.io/rest/v1/raindrops/{collection_id}"
        params = {
            'page': page,
            'perpage': 50,  # Max allowed by API
            'sort': '-created'  # Newest first
        }
        
        response = requests.get(url, headers=self.raindrop_headers, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching bookmarks: {response.status_code}")
            return {}
    
    def delete_bookmark(self, bookmark_id: int) -> bool:
        """Delete a bookmark from Raindrop"""
        if self.dry_run:
            return True  # Pretend success in dry-run mode
            
        url = f"https://api.raindrop.io/rest/v1/raindrop/{bookmark_id}"
        response = requests.delete(url, headers=self.raindrop_headers)
        return response.status_code == 200
    
    def move_bookmark_to_collection(self, bookmark_id: int, collection_id: int) -> bool:
        """Move bookmark to different collection (for archiving)"""
        if self.dry_run:
            return True  # Pretend success in dry-run mode
            
        url = f"https://api.raindrop.io/rest/v1/raindrop/{bookmark_id}"
        data = {'collection': {'$id': collection_id}}
        response = requests.put(url, headers=self.raindrop_headers, json=data)
        return response.status_code == 200
    
    def rate_limit_claude(self):
        """Simple rate limiting for Claude API"""
        elapsed = time.time() - self.last_claude_call
        if elapsed < self.claude_delay:
            time.sleep(self.claude_delay - elapsed)
        self.last_claude_call = time.time()
    
    def analyze_batch_with_claude(self, bookmarks: List[Dict], all_collections: List[Dict] = None, current_collection_name: str = None) -> List[Dict]:
        """Analyze a batch of bookmarks with Claude for efficiency"""
        self.rate_limit_claude()
        
        # Build batch prompt
        batch_info = ""
        for i, bookmark in enumerate(bookmarks):
            title = bookmark.get('title', 'Untitled')
            url = bookmark.get('link', '')
            domain = bookmark.get('domain', '')
            excerpt = bookmark.get('excerpt', '')[:150] if bookmark.get('excerpt') else ''
            created = bookmark.get('created', '')[:10] if bookmark.get('created') else ''  # Just date part
            
            batch_info += f"\n{i+1}. [{title}] - {domain} - {created}\n   URL: {url}\n"
            if excerpt:
                batch_info += f"   Content: {excerpt}\n"
            batch_info += "\n"
        
        # Include collection info if provided
        collection_info = ""
        if all_collections:
            collection_info = "\nAVAILABLE COLLECTIONS:\n"
            for col in all_collections:
                is_current = " ← CURRENT" if current_collection_name and col['title'] == current_collection_name else ""
                collection_info += f"- {col['title']} ({col.get('count', 0)} items){is_current}\n"
        
        current_collection_info = f"\nCURRENT COLLECTION: {current_collection_name}\n" if current_collection_name else ""
        
        prompt_content = f"""
You are helping someone with ADHD declutter bookmarks. Analyze these {len(bookmarks)} bookmarks and provide recommendations:
{current_collection_info}
{batch_info}

{collection_info}

For each bookmark, recommend the BEST action:

ACTIONS:
- DELETE: Can find via search, old news, "might read someday", outdated tutorials, duplicate content
- KEEP: Already in the right collection, frequently referenced, active project tools
- ARCHIVE: Historical reference (if Archive collection exists)
- MOVE:[CollectionName]: Should be in a different collection for better organization

CRITICAL RULES:
- NEVER suggest MOVE to the current collection ({current_collection_name}) - use KEEP instead
- Be ruthless with DELETE - they can find things again with search
- MOVE suggestions should improve organization
- When in doubt between KEEP and DELETE, lean toward DELETE
- Look for patterns: multiple similar links, outdated tutorials, dead projects

CATEGORIZATION HINTS (examine URL, title, and domain carefully):
- Gaming: game names (Metroid, Zelda, Pokemon), gaming sites (Steam, IGN, GameFAQs), ROM hacking, speedrunning, game guides
- Development: GitHub, Stack Overflow, documentation, coding tutorials, development tools, programming languages
- Reading: articles, blogs, Medium, news sites, opinion pieces
- Tools: apps, services, utilities, online tools
- Learning: courses, tutorials, educational content, how-to guides

URL PATTERN CLUES:
- github.com/user/repo = development
- steamcommunity.com, store.steampowered.com = gaming  
- medium.com/@author, blog.* = reading
- docs.* = development (usually)
- reddit.com/r/gamedev = development, reddit.com/r/gaming = gaming

BE VERY CAREFUL: 
- "Metroid ROM hacking tutorial" = GAMING (it's about a game)
- "JavaScript tutorial" = DEVELOPMENT (it's about programming)
- "How to speedrun Zelda" = GAMING (it's about playing a game)
- "How to code a game in Unity" = DEVELOPMENT (it's about programming)

Respond with ONLY the numbers and decisions:
1. DELETE - outdated tutorial
2. MOVE:development - coding tool  
3. KEEP - active reference
4. ARCHIVE - historical doc
etc.

Include brief reasoning after each decision.
"""

        try:
            message = self.claude_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=500,  # Increased for reasoning
                messages=[{"role": "user", "content": prompt_content}]
            ).content[0].text
            
            # Parse batch response
            decisions = []
            lines = message.strip().split('\n')
            for line in lines:
                if '. ' in line and line[0].isdigit():
                    parts = line.split('. ', 1)[1].strip()
                    
                    # Parse different decision types
                    if parts.upper().startswith('MOVE:'):
                        # Extract collection name and reasoning
                        try:
                            move_part = parts.split(' - ', 1)
                            collection_name = move_part[0].split(':', 1)[1].strip()
                            reasoning = move_part[1] if len(move_part) > 1 else "better organization"
                            decisions.append({'action': 'MOVE', 'target': collection_name, 'reasoning': reasoning})
                        except:
                            decisions.append({'action': 'KEEP', 'reasoning': 'parse error'})
                    else:
                        # Handle DELETE, KEEP, ARCHIVE with reasoning
                        decision_parts = parts.split(' - ', 1)
                        action = decision_parts[0].strip().upper()
                        reasoning = decision_parts[1] if len(decision_parts) > 1 else "no reason given"
                        
                        if action in ['DELETE', 'KEEP', 'ARCHIVE']:
                            decisions.append({'action': action, 'reasoning': reasoning})
                        else:
                            decisions.append({'action': 'KEEP', 'reasoning': 'unclear recommendation'})
            
            # Ensure we have decisions for all bookmarks
            while len(decisions) < len(bookmarks):
                decisions.append({'action': 'KEEP', 'reasoning': 'no recommendation received'})
            
            return decisions[:len(bookmarks)]
            
        except Exception as e:
            print(f"Batch Claude API error: {e}")
            self.stats['errors'] += 1
            return [{'action': 'KEEP', 'reasoning': 'API error'}] * len(bookmarks)
    
    def find_collection_by_name(self, collections: List[Dict], name: str) -> Optional[int]:
        """Find collection ID by name (fuzzy matching)"""
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
    
    def get_state_filename(self, collection_id: int, collection_name: str) -> Path:
        """Generate state filename for a collection"""
        safe_name = "".join(c for c in collection_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        return self.state_dir / f"collection_{collection_id}_{safe_name}.json"
    
    def save_state(self, collection_id: int, collection_name: str, current_page: int = 0):
        """Save current processing state"""
        state = {
            'collection_id': collection_id,
            'collection_name': collection_name,
            'current_page': current_page,
            'processed_bookmark_ids': list(self.processed_bookmark_ids),
            'stats': self.stats.copy(),
            'last_updated': datetime.now().isoformat(),
            'dry_run': self.dry_run
        }
        
        # Update session time
        if 'start_time' in self.stats:
            elapsed = datetime.now() - self.stats['start_time']
            state['stats']['session_time'] = self.stats.get('session_time', 0) + elapsed.total_seconds()
        
        state_file = self.get_state_filename(collection_id, collection_name)
        self.current_state_file = state_file
        
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        
        print(f"💾 State saved to {state_file.name}")
    
    def load_state(self, collection_id: int, collection_name: str) -> Optional[Dict]:
        """Load previous processing state if it exists"""
        state_file = self.get_state_filename(collection_id, collection_name)
        
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                
                # Validate state
                if (state.get('collection_id') == collection_id and 
                    state.get('collection_name') == collection_name):
                    
                    self.processed_bookmark_ids = set(state.get('processed_bookmark_ids', []))
                    
                    # Restore stats but update start time
                    saved_stats = state.get('stats', {})
                    self.stats.update(saved_stats)
                    self.stats['start_time'] = datetime.now()  # Reset for this session
                    
                    print(f"📂 Resuming from previous session:")
                    print(f"   Already processed: {len(self.processed_bookmark_ids)} bookmarks")
                    print(f"   Last page: {state.get('current_page', 0)}")
                    
                    session_time = saved_stats.get('session_time', 0)
                    if session_time > 0:
                        print(f"   Previous session time: {session_time/60:.1f} minutes")
                    
                    return state
                    
            except (json.JSONDecodeError, KeyError) as e:
                print(f"⚠️  Error loading state file: {e}")
                print("Starting fresh...")
        
        return None
    
    def cleanup_state_file(self):
        """Remove state file when collection processing is complete"""
        if self.current_state_file and self.current_state_file.exists():
            self.current_state_file.unlink()
            print(f"🧹 Cleaned up state file: {self.current_state_file.name}")
    
    def list_resumable_sessions(self) -> List[Dict]:
        """List all resumable sessions"""
        sessions = []
        
        for state_file in self.state_dir.glob("collection_*.json"):
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                
                last_updated = datetime.fromisoformat(state.get('last_updated', '1970-01-01'))
                sessions.append({
                    'file': state_file,
                    'collection_name': state.get('collection_name', 'Unknown'),
                    'collection_id': state.get('collection_id'),
                    'processed_count': len(state.get('processed_bookmark_ids', [])),
                    'last_updated': last_updated,
                    'stats': state.get('stats', {})
                })
            except (json.JSONDecodeError, KeyError):
                continue
        
        return sorted(sessions, key=lambda x: x['last_updated'], reverse=True)
    
    def display_batch_decisions_keyboard(self, bookmarks: List[Dict], decisions: List[Dict]) -> List[int]:
        """Keyboard-driven interface for selecting bookmark actions"""
        
        # Prepare selections - start with Claude's recommendations
        selections = []
        action_options = ['KEEP', 'MOVE', 'DELETE', 'ARCHIVE']
        
        for decision in decisions:
            action = decision.get('action', 'KEEP')
            if action in action_options:
                selections.append(action_options.index(action))
            else:
                selections.append(0)  # Default to KEEP
        
        def draw_interface(stdscr):
            current_bookmark = 0
            
            while True:
                stdscr.clear()
                height, width = stdscr.getmaxyx()
                
                # Header
                header = f"📋 Batch Review ({len(bookmarks)} bookmarks) - Navigate: ↑↓/jk, Select: ←→/hl, Accept: Enter, Quit: q"
                stdscr.addstr(0, 0, header[:width-1], curses.A_BOLD)
                stdscr.addstr(1, 0, "─" * min(width-1, 80))
                
                # Show bookmarks
                start_row = 3
                for i, (bookmark, decision) in enumerate(zip(bookmarks, decisions)):
                    if start_row + i * 5 >= height - 2:  # Changed from 4 to 5 for extra line
                        break  # Don't overflow screen
                    
                    title = bookmark.get('title', 'Untitled')[:60]
                    domain = bookmark.get('domain', '')[:30]
                    reasoning = decision.get('reasoning', '')[:80]
                    current_action = action_options[selections[i]]
                    
                    # Show target collection for MOVE actions
                    move_target = ""
                    if decision.get('action') == 'MOVE':
                        target = decision.get('target', 'Unknown')
                        move_target = f" → {target}"
                    
                    # Highlight current bookmark
                    title_attr = curses.A_REVERSE if i == current_bookmark else curses.A_NORMAL
                    
                    # Bookmark info
                    row = start_row + i * 5  # Changed from 4 to 5
                    stdscr.addstr(row, 0, f"{'►' if i == current_bookmark else ' '} {title}", title_attr)
                    stdscr.addstr(row + 1, 2, f"🌐 {domain}")
                    stdscr.addstr(row + 2, 2, f"💭 {reasoning}")
                    if move_target:
                        stdscr.addstr(row + 3, 2, f"📂 {move_target}")
                    
                    # Action selection with highlighting
                    actions_row = row + 4  # Changed from 3 to 4
                    stdscr.addstr(actions_row, 4, "Actions: ")
                    x_pos = 13
                    
                    for j, action in enumerate(action_options):
                        if action == 'MOVE' and decision.get('action') != 'MOVE':
                            continue  # Skip MOVE if not suggested by Claude
                        if action == 'ARCHIVE' and decision.get('action') != 'ARCHIVE':
                            continue  # Skip ARCHIVE if not suggested by Claude
                        
                        # Highlight selected action for current bookmark
                        if i == current_bookmark and j == selections[i]:
                            attr = curses.A_REVERSE | curses.A_BOLD
                        elif j == selections[i]:
                            attr = curses.A_BOLD
                        else:
                            attr = curses.A_NORMAL
                        
                        action_text = f"[{action}]"
                        stdscr.addstr(actions_row, x_pos, action_text, attr)
                        x_pos += len(action_text) + 1
                
                # Instructions at bottom
                if height > 10:
                    stdscr.addstr(height - 2, 0, "Press Enter to execute selections, 'q' to quit with save")
                
                stdscr.refresh()
                
                # Handle input
                try:
                    key = stdscr.getch()
                except KeyboardInterrupt:
                    raise
                
                # Navigation
                if key in [ord('j'), curses.KEY_DOWN]:
                    current_bookmark = min(current_bookmark + 1, len(bookmarks) - 1)
                elif key in [ord('k'), curses.KEY_UP]:
                    current_bookmark = max(current_bookmark - 1, 0)
                elif key in [ord('h'), curses.KEY_LEFT]:
                    # Move to previous action (skip unavailable ones)
                    available_actions = []
                    for j, action in enumerate(action_options):
                        if action in ['KEEP', 'DELETE']:
                            available_actions.append(j)
                        elif action == 'MOVE' and decisions[current_bookmark].get('action') == 'MOVE':
                            available_actions.append(j)
                        elif action == 'ARCHIVE' and decisions[current_bookmark].get('action') == 'ARCHIVE':
                            available_actions.append(j)
                    
                    current_idx = available_actions.index(selections[current_bookmark]) if selections[current_bookmark] in available_actions else 0
                    new_idx = (current_idx - 1) % len(available_actions)
                    selections[current_bookmark] = available_actions[new_idx]
                    
                elif key in [ord('l'), curses.KEY_RIGHT]:
                    # Move to next action (skip unavailable ones)
                    available_actions = []
                    for j, action in enumerate(action_options):
                        if action in ['KEEP', 'DELETE']:
                            available_actions.append(j)
                        elif action == 'MOVE' and decisions[current_bookmark].get('action') == 'MOVE':
                            available_actions.append(j)
                        elif action == 'ARCHIVE' and decisions[current_bookmark].get('action') == 'ARCHIVE':
                            available_actions.append(j)
                    
                    current_idx = available_actions.index(selections[current_bookmark]) if selections[current_bookmark] in available_actions else 0
                    new_idx = (current_idx + 1) % len(available_actions)
                    selections[current_bookmark] = available_actions[new_idx]
                    
                elif key in [ord('\n'), ord('\r'), 10]:  # Enter
                    # Return selected indices based on actions
                    selected_indices = []
                    for i, selection in enumerate(selections):
                        action = action_options[selection]
                        if action != 'KEEP':  # Only return indices for actions to execute
                            selected_indices.append(i)
                    return selected_indices
                    
                elif key in [ord('q'), ord('Q')]:
                    raise KeyboardInterrupt()  # Quit with save
        
        try:
            return curses.wrapper(draw_interface)
        except KeyboardInterrupt:
            print("💾 Saving progress and exiting...")
            raise
    
    def display_batch_decisions_text(self, bookmarks: List[Dict], decisions: List[Dict]) -> List[int]:
        """Fallback text-based interface for selecting bookmark actions"""
        print(f"\n{'='*80}")
        print(f"🤖 CLAUDE'S RECOMMENDATIONS FOR {len(bookmarks)} BOOKMARKS")
        print(f"{'='*80}")
        
        for i, (bookmark, decision) in enumerate(zip(bookmarks, decisions)):
            title = bookmark.get('title', 'Untitled')[:60]
            domain = bookmark.get('domain', '')
            action = decision.get('action', 'KEEP')
            reasoning = decision.get('reasoning', '')
            
            action_color = {'DELETE': '❌', 'KEEP': '✅', 'ARCHIVE': '📦', 'MOVE': '🔄'}
            
            print(f"\n{i+1:2d}. {action_color.get(action, '?')} {action}")
            print(f"    📰 {title}")
            print(f"    🌐 {domain}")
            print(f"    💭 {reasoning}")
            
            if action == 'MOVE':
                target = decision.get('target', 'Unknown')
                print(f"    📂 Target: {target}")
        
        print(f"\n{'='*80}")
        print("💡 Enter your choice:")
        print("  'deletes' - Execute all DELETE recommendations")
        print("  'moves' - Execute all MOVE recommendations") 
        print("  'all' - Execute ALL Claude's recommendations")
        print("  'none' - Skip this batch (keep everything)")
        print("  'quit' - Save progress and exit")
        
        while True:
            try:
                user_input = input("\n📝 Your choice: ").strip().lower()
                
                if user_input in ['quit', 'q', 'exit']:
                    raise KeyboardInterrupt()
                elif user_input in ['none', 'skip', '']:
                    return []
                elif user_input == 'all':
                    return list(range(len(bookmarks)))
                elif user_input == 'deletes':
                    return [i for i, d in enumerate(decisions) if d.get('action') == 'DELETE']
                elif user_input == 'moves':
                    return [i for i, d in enumerate(decisions) if d.get('action') == 'MOVE']
                elif user_input == 'archives':
                    return [i for i, d in enumerate(decisions) if d.get('action') == 'ARCHIVE']
                else:
                    print("❌ Try: 'deletes', 'moves', 'all', 'none', or 'quit'")
                    continue
            except (ValueError, IndexError):
                print("❌ Try: 'deletes', 'moves', 'all', 'none', or 'quit'")
                continue

    def display_batch_decisions(self, bookmarks: List[Dict], decisions: List[Dict]) -> List[int]:
        """Router method to choose between keyboard and text interfaces"""
        
        # Check if we can use curses (keyboard interface)
        can_use_curses = not self.text_mode
        
        # Try to use curses interface if not explicitly disabled
        if can_use_curses:
            try:
                # Test if curses is available and terminal supports it
                import curses
                if hasattr(curses, 'wrapper') and os.isatty(0):  # Check if stdin is a terminal
                    return self.display_batch_decisions_keyboard(bookmarks, decisions)
                else:
                    print("⚠️  Terminal doesn't support interactive mode, falling back to text interface")
                    return self.display_batch_decisions_text(bookmarks, decisions)
            except (ImportError, curses.error):
                print("⚠️  Curses not available, using text interface")
                return self.display_batch_decisions_text(bookmarks, decisions)
        else:
            return self.display_batch_decisions_text(bookmarks, decisions)
    
    def execute_user_selections(self, bookmarks: List[Dict], decisions: List[Dict], 
                              selected_indices: List[int], all_collections: List[Dict],
                              archive_collection_id: Optional[int] = None):
        """Execute the user's selected actions"""
        if not selected_indices:
            print("⏭️  Skipping all items in this batch")
            # Still mark these as processed so we don't see them again
            for bookmark in bookmarks:
                self.processed_bookmark_ids.add(bookmark['_id'])
            self.stats['skipped'] += len(bookmarks)
            return
        
        print(f"\n🚀 EXECUTING {len(selected_indices)} ACTIONS...")
        
        # Mark all bookmarks in this batch as processed (including unselected ones)
        for bookmark in bookmarks:
            self.processed_bookmark_ids.add(bookmark['_id'])
        
        for i in selected_indices:
            bookmark = bookmarks[i]
            decision = decisions[i]
            bookmark_id = bookmark['_id']
            title = bookmark.get('title', 'Untitled')[:50]
            action = decision.get('action', 'KEEP')
            
            if action == 'DELETE':
                if self.delete_bookmark(bookmark_id):
                    print(f"    ❌ {'[DRY-RUN] ' if self.dry_run else ''}DELETED: {title}")
                    self.stats['deleted'] += 1
                else:
                    print(f"    ⚠️  Failed to delete: {title}")
                    self.stats['errors'] += 1
                    
            elif action == 'ARCHIVE' and archive_collection_id:
                if self.move_bookmark_to_collection(bookmark_id, archive_collection_id):
                    print(f"    📦 {'[DRY-RUN] ' if self.dry_run else ''}ARCHIVED: {title}")
                    self.stats['archived'] += 1
                else:
                    print(f"    ⚠️  Failed to archive: {title}")
                    self.stats['errors'] += 1
                    
            elif action == 'MOVE' and all_collections:
                target_name = decision.get('target', '')
                target_id = self.find_collection_by_name(all_collections, target_name)
                
                if target_id:
                    if self.move_bookmark_to_collection(bookmark_id, target_id):
                        print(f"    🔄 {'[DRY-RUN] ' if self.dry_run else ''}MOVED to {target_name}: {title}")
                        self.stats['moved'] += 1
                    else:
                        print(f"    ⚠️  Failed to move to {target_name}: {title}")
                        self.stats['errors'] += 1
                else:
                    print(f"    ⚠️  Collection '{target_name}' not found: {title}")
                    self.stats['errors'] += 1
            
            self.stats['processed'] += 1
        
        # Mark unselected items as kept
        unselected_count = len(bookmarks) - len(selected_indices)
        if unselected_count > 0:
            self.stats['kept'] += unselected_count
    
    def process_collection(self, collection_id: int, collection_name: str, 
                          batch_size: int = 10, archive_collection_id: Optional[int] = None, 
                          all_collections: List[Dict] = None, resume_from_state: bool = True):
        """Process all bookmarks in a collection with interactive decisions"""
        print(f"\n🚀 Processing collection: {collection_name}")
        print(f"Collection ID: {collection_id}")
        
        # Try to load previous state
        start_page = 0
        if resume_from_state:
            previous_state = self.load_state(collection_id, collection_name)
            if previous_state:
                start_page = previous_state.get('current_page', 0)
                resume_choice = input(f"\n🔄 Resume from page {start_page}? (Y/n): ").strip().lower()
                if resume_choice in ['n', 'no']:
                    print("🆕 Starting fresh session")
                    self.processed_bookmark_ids.clear()
                    start_page = 0
                    # Reset stats
                    self.stats = {
                        'processed': 0, 'kept': 0, 'deleted': 0, 'archived': 0, 
                        'moved': 0, 'errors': 0, 'skipped': 0, 'start_time': datetime.now(),
                        'session_time': 0
                    }
        
        page = start_page
        total_processed = 0
        
        try:
            while True:
                # Get batch of bookmarks
                data = self.get_bookmarks_from_collection(collection_id, page)
                bookmarks = data.get('items', [])
                
                if not bookmarks:
                    break
                
                # Filter out already processed bookmarks
                unprocessed_bookmarks = [
                    bookmark for bookmark in bookmarks 
                    if bookmark['_id'] not in self.processed_bookmark_ids
                ]
                
                if not unprocessed_bookmarks:
                    print(f"📄 Page {page + 1}: All {len(bookmarks)} bookmarks already processed, skipping...")
                    page += 1
                    continue
                
                print(f"\n📦 Processing page {page + 1} - {len(unprocessed_bookmarks)} new bookmarks (of {len(bookmarks)} total)")
                
                # Process in smaller batches for ADHD-friendly sessions
                for i in range(0, len(unprocessed_bookmarks), batch_size):
                    batch = unprocessed_bookmarks[i:i + batch_size]
                    batch_num = i//batch_size + 1
                    total_batches = (len(unprocessed_bookmarks) + batch_size - 1) // batch_size
                    
                    print(f"\n{'='*60}")
                    print(f"📋 BATCH {batch_num} of {total_batches} ({len(batch)} bookmarks)")
                    print(f"{'='*60}")
                    
                    # Get AI recommendations
                    print("🤖 Getting Claude's recommendations...")
                    print("    (Based on: title, URL, domain, and excerpt - not full content)")
                    decisions = self.analyze_batch_with_claude(batch, all_collections, collection_name)
                    
                    # Show recommendations and get user choices
                    selected_indices = self.display_batch_decisions(batch, decisions)
                    
                    # Execute user's choices
                    self.execute_user_selections(batch, decisions, selected_indices, 
                                               all_collections, archive_collection_id)
                    
                    total_processed += len(batch)
                    
                    # Save state after each batch
                    self.save_state(collection_id, collection_name, page)
                    
                    # Progress update
                    elapsed = datetime.now() - self.stats['start_time']
                    rate = len(self.processed_bookmark_ids) / elapsed.total_seconds() * 60 if elapsed.total_seconds() > 0 else 0
                    print(f"\n📊 Session Progress: {len(self.processed_bookmark_ids)} total processed | Rate: {rate:.1f}/min")
                    
                    # ADHD break suggestion
                    if total_processed % 25 == 0 and batch_num < total_batches:
                        print(f"\n💡 You've processed {total_processed} bookmarks this session - great work!")
                        break_choice = input("Take a 5-minute break? (y/N/quit): ").strip().lower()
                        if break_choice in ['quit', 'q', 'exit']:
                            print("💾 Progress saved! You can resume later with the same command.")
                            return
                        elif break_choice in ['y', 'yes']:
                            print("☕ Take your break! Press Enter when ready to continue...")
                            input()
                
                page += 1
                
                # Safety check to avoid infinite loops
                if page > 100:
                    print("⚠️  Reached page limit, stopping")
                    break
        
        except KeyboardInterrupt:
            print(f"\n\n⏹️  Processing interrupted - progress saved!")
            self.save_state(collection_id, collection_name, page)
            raise
        
        # Collection completed - clean up state file
        self.cleanup_state_file()
        
        print(f"\n✅ Completed collection: {collection_name}")
        print(f"   Total bookmarks processed this session: {total_processed}")
        print(f"   Total bookmarks processed overall: {len(self.processed_bookmark_ids)}")
    
    def print_stats(self):
        """Print final statistics"""
        current_elapsed = datetime.now() - self.stats['start_time']
        total_session_time = self.stats.get('session_time', 0) + current_elapsed.total_seconds()
        
        print(f"\n{'='*60}")
        print(f"🎉 BOOKMARK CLEANUP {'SIMULATION' if self.dry_run else 'COMPLETE'}!")
        print(f"{'='*60}")
        print(f"⏱️  This session: {current_elapsed}")
        if self.stats.get('session_time', 0) > 0:
            print(f"⏱️  Total time: {total_session_time/60:.1f} minutes (across sessions)")
        print(f"📊 Total processed: {self.stats['processed']}")
        print(f"✅ Kept: {self.stats['kept']}")
        print(f"❌ Deleted: {self.stats['deleted']}")
        print(f"📦 Archived: {self.stats['archived']}")
        print(f"🔄 Moved: {self.stats['moved']}")
        print(f"⏭️  Skipped: {self.stats['skipped']}")
        print(f"⚠️  Errors: {self.stats['errors']}")
        
        total_items = (self.stats['processed'] + self.stats['skipped'])
        if total_items > 0:
            kept_pct = (self.stats['kept'] / total_items) * 100
            deleted_pct = (self.stats['deleted'] / total_items) * 100
            print(f"📈 Kept: {kept_pct:.1f}% | Deleted: {deleted_pct:.1f}%")
    
    def show_resumable_sessions(self):
        """Show available sessions that can be resumed"""
        sessions = self.list_resumable_sessions()
        
        if not sessions:
            print("📝 No resumable sessions found.")
            return None
        
        print(f"\n📚 Resumable Sessions ({len(sessions)} found):")
        print("="*70)
        
        for i, session in enumerate(sessions):
            stats = session['stats']
            elapsed_str = ""
            if stats.get('session_time'):
                elapsed_str = f" | {stats['session_time']/60:.1f}min"
            
            print(f"{i+1:2d}. {session['collection_name']}")
            print(f"    📊 {session['processed_count']} processed | "
                  f"{stats.get('deleted', 0)} deleted | "
                  f"{stats.get('moved', 0)} moved{elapsed_str}")
            print(f"    📅 Last updated: {session['last_updated'].strftime('%Y-%m-%d %H:%M')}")
            print()
        
        return sessions

def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="🌧️  Interactive Raindrop Bookmark Cleanup Tool - AI-powered bookmark curation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 raindrop_cleanup.py                    # Interactive mode
  python3 raindrop_cleanup.py --batch-size 5     # Smaller batches 
  python3 raindrop_cleanup.py --list-collections # Show collections and exit
  python3 raindrop_cleanup.py --dry-run          # Test without making changes
  
Environment Variables Required:
  ANTHROPIC_API_KEY   - Your Claude API key
  RAINDROP_TOKEN      - Your Raindrop.io API token
  
ADHD-Friendly Features:
  • Shows Claude's recommendations with reasoning
  • You choose which actions to execute  
  • Processes in small batches (default: 10 items)
  • Suggests breaks every 25 items  
  • Shows real-time progress and statistics
  • Conservative defaults (keeps items when uncertain)
        """
    )
    
    parser.add_argument(
        '--batch-size', '-b',
        type=int,
        default=8,
        help='Number of bookmarks to process in each batch (default: 8, recommended 5-12)'
    )
    
    parser.add_argument(
        '--list-collections', '-l',
        action='store_true',
        help='List all collections and exit (useful for planning)'
    )
    
    parser.add_argument(
        '--archive-name',
        default='Archive',
        help='Name of archive collection (default: "Archive")'
    )
    
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    parser.add_argument(
        '--resume', '-r',
        action='store_true',
        help='Show resumable sessions and choose one to continue'
    )
    
    parser.add_argument(
        '--clean-state',
        action='store_true',
        help='Clean up old state files'
    )
    
    parser.add_argument(
        '--text-mode', '-t',
        action='store_true', 
        help='Use text-based interface instead of keyboard navigation'
    )
    
    args = parser.parse_args()
    
    print("🌧️  Interactive Raindrop Bookmark Cleanup Tool")
    print("============================================")
    
    try:
        cleaner = RaindropBookmarkCleaner(dry_run=args.dry_run, text_mode=args.text_mode)
        
        # Clean state files if requested
        if args.clean_state:
            state_files = list(cleaner.state_dir.glob("collection_*.json"))
            if state_files:
                print(f"🧹 Found {len(state_files)} state files to clean:")
                for state_file in state_files:
                    print(f"   {state_file.name}")
                confirm = input("Delete all? (y/N): ").strip().lower()
                if confirm in ['y', 'yes']:
                    for state_file in state_files:
                        state_file.unlink()
                    print("✅ State files cleaned!")
                else:
                    print("❌ Cancelled")
            else:
                print("📝 No state files found to clean")
            return
        
        # Show resumable sessions if requested
        if args.resume:
            sessions = cleaner.show_resumable_sessions()
            if not sessions:
                print("Starting a new session instead...")
            else:
                print("🔄 Choose a session to resume:")
                print("Enter number, or 'new' for a fresh session:")
                
                while True:
                    choice = input("📝 Your choice: ").strip().lower()
                    
                    if choice in ['new', 'fresh', 'n']:
                        break  # Continue to regular collection selection
                    
                    try:
                        session_index = int(choice) - 1
                        if 0 <= session_index < len(sessions):
                            selected_session = sessions[session_index]
                            
                            # Load this session's collection
                            collections = cleaner.get_raindrop_collections()
                            selected_collection = None
                            for col in collections:
                                if col['_id'] == selected_session['collection_id']:
                                    selected_collection = col
                                    break
                            
                            if selected_collection:
                                print(f"\n🔄 Resuming '{selected_collection['title']}'...")
                                
                                # Find archive collection
                                archive_collection_id = cleaner.find_collection_by_name(collections, args.archive_name)
                                
                                # Resume processing
                                cleaner.process_collection(
                                    collection_id=selected_collection['_id'],
                                    collection_name=selected_collection['title'],
                                    batch_size=args.batch_size,
                                    archive_collection_id=archive_collection_id,
                                    all_collections=collections,
                                    resume_from_state=True
                                )
                                
                                cleaner.print_stats()
                                return
                            else:
                                print("❌ Collection no longer exists")
                                return
                    except (ValueError, IndexError):
                        print("❌ Invalid choice. Try a number, or 'new' for fresh session.")
                        continue
                    break
        
        # Get all collections
        collections = cleaner.get_raindrop_collections()
        if not collections:
            print("❌ No collections found or API error")
            return
        
        # List collections if requested
        if args.list_collections:
            print(f"\n📚 Found {len(collections)} collections:")
            for col in collections:
                count = col.get('count', 0)
                print(f"  📁 {col['title']} ({count} items) - ID: {col['_id']}")
            return
        
        # Find archive collection
        archive_collection_id = None
        archive_collection = cleaner.find_collection_by_name(collections, args.archive_name)
        if archive_collection:
            archive_collection_id = archive_collection
            print(f"📦 Found archive collection: {args.archive_name}")
        else:
            print(f"⚠️  Archive collection '{args.archive_name}' not found")
        
        # Interactive collection selection
        print(f"\n📚 Available collections:")
        for i, col in enumerate(collections):
            count = col.get('count', 0)
            print(f"  {i+1:2d}. {col['title']} ({count} items)")
        
        print(f"\n🎯 Which collection would you like to process?")
        print("Enter number, name, or 'quit' to exit:")
        
        while True:
            choice = input("📝 Your choice: ").strip()
            
            if choice.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                return
            
            # Try to parse as number
            try:
                col_index = int(choice) - 1
                if 0 <= col_index < len(collections):
                    selected_collection = collections[col_index]
                    break
            except ValueError:
                pass
            
            # Try to find by name
            for col in collections:
                if choice.lower() in col['title'].lower():
                    selected_collection = col
                    break
            else:
                print("❌ Collection not found. Try again or 'quit' to exit.")
                continue
            break
        
        print(f"\n🚀 Starting cleanup of '{selected_collection['title']}'")
        print(f"📊 {selected_collection.get('count', 0)} bookmarks to review")
        
        if args.dry_run:
            print("🧪 DRY-RUN MODE: No changes will be made")
        
        input("\nPress Enter to begin...")
        
        # Process the selected collection
        cleaner.process_collection(
            collection_id=selected_collection['_id'],
            collection_name=selected_collection['title'],
            batch_size=args.batch_size,
            archive_collection_id=archive_collection_id,
            all_collections=collections,
            resume_from_state=True  # Always try to resume by default
        )
        
        # Show final statistics
        cleaner.print_stats()
        
    except KeyboardInterrupt:
        print(f"\n\n⏹️  Cleanup interrupted by user")
        if 'cleaner' in locals():
            cleaner.print_stats()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()