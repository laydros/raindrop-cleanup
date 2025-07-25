# 🌧️ Raindrop Cleanup Tool

An interactive, AI-powered bookmark cleanup tool for [Raindrop.io](https://raindrop.io) designed with ADHD-friendly features to help you declutter and organize your bookmarks efficiently.

## ✨ Features

### 🤖 AI-Powered Analysis
- Uses Claude AI to analyze bookmarks and provide smart recommendations
- Examines title, URL, domain, and excerpt to suggest appropriate actions
- Provides reasoning for each recommendation to help you make informed decisions

### 🧠 ADHD-Friendly Design
- **Small batches**: Processes bookmarks in manageable chunks (default: 10 items)
- **Break reminders**: Suggests breaks every 25 items to prevent overwhelm
- **Progress tracking**: Shows real-time statistics and processing rate
- **State persistence**: Resume sessions anytime - never lose progress
- **Conservative defaults**: Keeps items when uncertain rather than deleting

### 🎮 Interactive Interfaces
- **Keyboard navigation**: Arrow keys or vim-style (hjkl) navigation
- **Text mode fallback**: Works in any terminal environment
- **Batch review**: See all recommendations at once before taking action
- **Visual feedback**: Clear progress indicators and action confirmations

### 🔄 Smart Actions
- **DELETE**: Remove outdated tutorials, old news, duplicates
- **KEEP**: Items already well-organized in current collection
- **ARCHIVE**: Move to archive collection for historical reference
- **MOVE**: Relocate to more appropriate collections for better organization

### 💾 Session Management
- **Resume capability**: Pick up exactly where you left off
- **State persistence**: Automatic saving after each batch
- **Multiple sessions**: Track progress across different collections
- **Clean state management**: Automatic cleanup when collections complete

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- [Raindrop.io](https://raindrop.io) account
- [Anthropic Claude](https://console.anthropic.com/) API access

### Install from PyPI (coming soon)
```bash
pip install raindrop-cleanup
```

### Install from Source
```bash
git clone https://github.com/laydros/raindrop-cleanup.git
cd raindrop-cleanup
pip install -e .
```

## ⚙️ Configuration

### Required Environment Variables

Create a `.env` file or set these environment variables:

```bash
# Required: Your Raindrop.io API token
export RAINDROP_TOKEN="your_raindrop_token_here"

# Required: Your Anthropic Claude API key  
export ANTHROPIC_API_KEY="your_claude_api_key_here"
```

### Getting API Keys

#### Raindrop.io Token
1. Go to [Raindrop.io App Settings](https://app.raindrop.io/settings/integrations)
2. Navigate to "Integrations" → "For Developers"
3. Create a new app or use existing
4. Copy your API token

#### Anthropic Claude API Key
1. Visit [Anthropic Console](https://console.anthropic.com/)
2. Sign up/sign in to your account
3. Navigate to API Keys section
4. Generate a new API key

## 🎯 Usage

### Basic Usage
```bash
# Interactive mode - choose collection to process
raindrop-cleanup

# List all collections first to plan your session
raindrop-cleanup --list-collections

# Process with smaller batches (good for focus)
raindrop-cleanup --batch-size 5

# Test run without making changes
raindrop-cleanup --dry-run
```

### Session Management
```bash
# Resume a previous session
raindrop-cleanup --resume

# Use text-only interface (no keyboard navigation)
raindrop-cleanup --text-mode

# Clean up old session files
raindrop-cleanup --clean-state
```

### Advanced Options
```bash
# Specify custom archive collection name
raindrop-cleanup --archive-name "My Archive"

# Combine options for your preferred workflow
raindrop-cleanup --batch-size 6 --text-mode --dry-run
```

## 🎛️ Command Line Options

| Option | Short | Description |
|--------|-------|-------------|
| `--batch-size` | `-b` | Items per batch (default: 10, recommended: 5-12) |
| `--list-collections` | `-l` | Show all collections and exit |
| `--archive-name` | | Archive collection name (default: "Archive") |
| `--dry-run` | `-n` | Preview changes without executing |
| `--resume` | `-r` | Show and resume previous sessions |
| `--text-mode` | `-t` | Use text interface instead of keyboard navigation |
| `--clean-state` | | Remove old session state files |

## 🎮 Interactive Controls

### Keyboard Navigation Mode
- `↑/↓` or `j/k`: Navigate between bookmarks
- `←/→` or `h/l`: Change action for current bookmark  
- `Enter`: Execute selected actions
- `q`: Save progress and quit

### Available Actions
- **KEEP**: Leave bookmark in current collection
- **DELETE**: Remove bookmark permanently
- **MOVE**: Move to suggested collection (when available)
- **ARCHIVE**: Move to archive collection (when available)

### Text Mode
- Enter choice: `all`, `deletes`, `moves`, `archives`, `none`, or `quit`
- All decisions made per batch with simple text commands

## 📊 Understanding AI Recommendations

Claude analyzes each bookmark considering:

### 🎯 Categorization Hints
- **Gaming**: Game names, gaming sites, ROMs, guides, speedrunning
- **Development**: GitHub, docs, Stack Overflow, tutorials, tools
- **Reading**: Articles, blogs, news, Medium posts, opinion pieces
- **Tools**: Apps, services, utilities, online tools
- **Learning**: Courses, how-to guides, educational content

### 🔍 URL Pattern Recognition
- `github.com/user/repo` → Development
- `steamcommunity.com` → Gaming
- `medium.com/@author` → Reading
- `docs.*` → Development (usually)
- `reddit.com/r/gamedev` → Development vs `reddit.com/r/gaming` → Gaming

### 💡 Decision Logic
- **DELETE**: Can find via search, outdated content, "might read someday" items
- **KEEP**: Frequently referenced, active projects, already well-organized
- **ARCHIVE**: Historical reference value but not actively needed
- **MOVE**: Would be better organized in a different collection

## 📈 Statistics and Progress

The tool tracks comprehensive statistics:
- **Processed**: Total bookmarks reviewed
- **Kept**: Items left in original collection
- **Deleted**: Items removed permanently
- **Archived**: Items moved to archive
- **Moved**: Items relocated to other collections
- **Errors**: Failed operations
- **Session time**: Time spent across all sessions
- **Processing rate**: Bookmarks per minute

## 🔧 Development

### Project Structure
```
raindrop_cleanup/
├── api/            # Raindrop.io API client
├── ai/             # Claude AI analysis
├── cli/            # Command line interface
├── core/           # Main processing logic
├── state/          # Session state management
└── ui/             # User interface components
```

### Running Tests
```bash
pip install -e ".[dev]"
pytest
```

### Code Formatting
```bash
black raindrop_cleanup/
flake8 raindrop_cleanup/
mypy raindrop_cleanup/
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Run the test suite
6. Submit a pull request

## 📄 License

This project is licensed under the BSD 3-Clause License - see the [LICENSE](LICENSE) file for details.

## ❓ FAQ

### Why does the tool sometimes suggest keeping seemingly old bookmarks?
The AI is conservative by design - it prefers to keep items when uncertain rather than delete potentially valuable content. You can always override suggestions.

### Can I undo actions after running the tool?
Not directly. Use `--dry-run` first to preview changes. Raindrop.io may have its own trash/undo features.

### Why does processing seem slow?  
The tool includes intentional rate limiting for the Claude API and uses small batches to prevent cognitive overload. This is by design for sustainability and ADHD-friendliness.

### What if I have thousands of bookmarks?
The tool is designed for this! It saves state automatically, so you can process large collections over multiple sessions at your own pace.

### Can I customize the AI prompts?
Not currently through the CLI, but the code is open source. Check the `ai/claude_analyzer.py` module to understand and modify the prompts.

## 🙏 Acknowledgments

- [Raindrop.io](https://raindrop.io) for the excellent bookmark management service
- [Anthropic](https://www.anthropic.com) for Claude AI
- The ADHD community for inspiration on accessible design patterns

---

**Happy bookmark decluttering! 🌟**