# Vera Messaging Integration

Connect Vera AI to Slack, Discord, and Telegram for multi-platform chat support.

## Features

- ✅ **Multi-Platform Support**: Slack, Discord, and Telegram
- ✅ **Real-time Streaming**: Responses stream and update in real-time
- ✅ **Thread/Conversation Context**: Maintains conversation history per user
- ✅ **DM & Channel Support**: Works in direct messages and channels/groups
- ✅ **Rich Formatting**: Platform-specific formatting (markdown, HTML, etc.)
- ✅ **Session Persistence**: Each user gets their own Vera session
- ✅ **Command Support**: Built-in commands for help, status, etc.

## Installation

### 1. Install Dependencies

Install only the packages for the platforms you want to use:

```bash
# All platforms
pip install -r requirements-messaging.txt

# Or install individually:
pip install slack-sdk              # For Slack
pip install discord.py             # For Discord
pip install python-telegram-bot    # For Telegram
pip install pyyaml                 # For config files
```

### 2. Setup Platform Bots

#### Slack Setup

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click "Create New App" → "From scratch"
3. Name your app (e.g., "Vera AI") and select your workspace

**Enable Socket Mode:**
1. Go to "Socket Mode" in sidebar
2. Enable Socket Mode
3. Generate an App-Level Token with `connections:write` scope
4. Save the token (starts with `xapp-`)

**Add Bot Permissions:**
1. Go to "OAuth & Permissions"
2. Add these Bot Token Scopes:
   - `chat:write` - Send messages
   - `channels:history` - Read channel messages
   - `groups:history` - Read private channel messages
   - `im:history` - Read DM messages
   - `app_mentions:read` - Detect @mentions
3. Install app to workspace
4. Copy the Bot Token (starts with `xoxb-`)

**Enable Event Subscriptions:**
1. Go to "Event Subscriptions"
2. Enable Events
3. Subscribe to bot events:
   - `message.channels`
   - `message.groups`
   - `message.im`
   - `app_mention`

**Set Environment Variables:**
```bash
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_APP_TOKEN="xapp-your-app-token"
```

#### Discord Setup

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click "New Application"
3. Name your application (e.g., "Vera AI")

**Create Bot:**
1. Go to "Bot" section
2. Click "Add Bot"
3. Under "Privileged Gateway Intents", enable:
   - ✅ MESSAGE CONTENT INTENT (required!)
   - ✅ SERVER MEMBERS INTENT
4. Copy the Bot Token

**Invite to Server:**
1. Go to "OAuth2" → "URL Generator"
2. Select scopes:
   - `bot`
3. Select bot permissions:
   - Read Messages/View Channels
   - Send Messages
   - Send Messages in Threads
   - Embed Links
   - Attach Files
   - Read Message History
4. Copy the generated URL and open it to invite bot

**Set Environment Variable:**
```bash
export DISCORD_BOT_TOKEN="your-discord-bot-token"
```

#### Telegram Setup

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow instructions to name your bot
4. Copy the bot token you receive

**Optional: Set Commands Menu:**
```
/setcommands to @BotFather
Then paste:
start - Start conversation with Vera
help - Show help message
status - Check bot status
models - List available models
clear - Clear conversation history
```

**Set Environment Variable:**
```bash
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
```

## Usage

### Quick Start (Environment Variables)

Set your bot tokens as environment variables and run:

```bash
# Run all configured platforms
python run_messaging_bots.py

# Run specific platforms
python run_messaging_bots.py --slack
python run_messaging_bots.py --discord
python run_messaging_bots.py --telegram
python run_messaging_bots.py --platforms slack discord
```

### Configuration File

Create a config file for easier management:

```bash
# Create sample config
python run_messaging_bots.py --create-config config.yaml

# Edit config.yaml with your tokens

# Run with config
python run_messaging_bots.py --config config.yaml
```

**Sample config.yaml:**
```yaml
slack:
  enabled: true
  bot_token: "xoxb-your-bot-token"
  app_token: "xapp-your-app-token"
  respond_to_all: false  # Only respond to DMs and mentions

discord:
  enabled: true
  bot_token: "your-discord-bot-token"
  prefix: "!"
  respond_to_all: false  # Only respond to DMs and mentions

telegram:
  enabled: true
  bot_token: "your-telegram-bot-token"
```

### Individual Bot Runners

You can also run bots individually:

```bash
# Slack only
python slack_bot.py

# Discord only
python discord_bot.py

# Telegram only
python telegram_bot.py
```

## Usage Examples

### Slack

**Direct Message:**
```
You: Hi Vera, explain quantum computing
Vera: 🤔 Thinking...
      [streams response in real-time]
```

**Channel (requires mention):**
```
You: @Vera what's the weather in NYC?
Vera: [responds with current weather]
```

**Thread Support:**
```
You: @Vera start analysis
Vera: [responds]
You: continue with more details
     [in thread - Vera maintains context]
```

### Discord

**Direct Message:**
```
You: explain machine learning
Vera: 🤔 Thinking...
      [streams response]
```

**Commands:**
```
!help     - Show help
!status   - Check status
!models   - List AI models
!clear    - Clear history
```

**Channel (requires mention):**
```
You: @Vera help me debug this code
Vera: [responds with debugging help]
```

### Telegram

**Private Chat:**
```
/start
[Welcome message]

You: What's the capital of France?
Vera: [responds]
```

**Group Chat (requires mention):**
```
You: @verabot analyze this data
Vera: [responds with analysis]
```

**Commands:**
```
/help    - Show help
/status  - Bot status
/models  - List models
/clear   - Clear history
```

## Architecture

### Component Overview

```
run_messaging_bots.py          # Unified launcher
├── vera_messaging.py          # Core integration framework
│   ├── Platform adapters      # Slack/Discord/Telegram specific
│   ├── Message formatters     # Platform-specific formatting
│   └── Session management     # User session tracking
│
├── slack_bot.py               # Slack runner
├── discord_bot.py             # Discord runner
└── telegram_bot.py            # Telegram runner
```

### Message Flow

```
User Message
    ↓
Platform Bot (Slack/Discord/Telegram)
    ↓
VeraMessaging.process_message()
    ↓
Get/Create Vera Session
    ↓
vera.chat.async_run(query)
    ↓
Stream response chunks
    ↓
Update message in real-time
    ↓
Final formatted response
```

### Session Management

Each user gets a unique Vera session based on:
- Platform (slack/discord/telegram)
- User ID
- Channel/Thread ID

Sessions persist across bot restarts via Vera's session manager.

## Features Detail

### Real-time Streaming

Responses stream in real-time with periodic updates:

```python
# Discord example
full_response = ""
for chunk in vera.chat.async_run(query):
    full_response += chunk
    # Update every 1 second
    await message.edit(content=full_response + " ⏳")

# Final update
await message.edit(content=full_response)
```

### Platform-Specific Formatting

Each platform has its own formatter:

**Slack:**
- Uses `*bold*` and `_italic_`
- Code blocks with ```language```

**Discord:**
- Full Markdown support
- Embeds for rich content
- Code blocks with syntax highlighting

**Telegram:**
- HTML formatting: `<b>`, `<i>`, `<code>`
- Inline keyboard buttons (future)

### Error Handling

- Connection failures → Auto-reconnect
- Message too long → Auto-split
- Rate limiting → Queue and retry
- Platform errors → Graceful fallback

## Advanced Configuration

### Custom Response Behavior

Edit the config to customize bot behavior:

```yaml
slack:
  respond_to_all: true      # Respond to all messages in channels
  update_interval: 0.5      # Update frequency (seconds)
  max_message_length: 3000  # Split messages longer than this

discord:
  prefix: "vera "           # Custom command prefix
  respond_to_bots: false    # Ignore other bots
  
telegram:
  parse_mode: "HTML"        # or "Markdown"
```

### Integration with Vera Features

The bots automatically support all Vera features:

- **Multiple Models**: Triage routes to appropriate model
- **Toolchain**: Can execute tools (if configured)
- **Memory**: Uses Neo4j/ChromaDB for context
- **Orchestrator**: Background task execution
- **Proactive Thinking**: Can be triggered

### Logging

All bot activity is logged via Vera's logging system:

```python
# View logs
tail -f logs/vera_slack_bot.log
tail -f logs/vera_discord_bot.log
tail -f logs/vera_telegram_bot.log
```

## Troubleshooting

### Slack

**Bot doesn't respond:**
- Check Socket Mode is enabled
- Verify bot token (xoxb-) and app token (xapp-)
- Ensure event subscriptions are configured
- Check bot has proper scopes

**"channel_not_found" error:**
- Invite bot to channel first
- Use `/invite @YourBot` in channel

### Discord

**Bot can't read messages:**
- Enable MESSAGE CONTENT INTENT in bot settings
- Regenerate token after enabling intent

**Slash commands not working:**
- This version uses prefix commands (!)
- Enable slash commands in Discord developer portal

### Telegram

**Bot doesn't respond in groups:**
- Mention bot with @botname
- Or use commands (/help)

**Commands not showing:**
- Set commands with @BotFather using /setcommands

### General

**"Module not found" errors:**
```bash
pip install -r requirements-messaging.txt
```

**Vera not initializing:**
- Ensure Vera is properly configured
- Check Vera's config files
- Verify database connections (Neo4j, ChromaDB)

## Security Considerations

- **Never commit tokens**: Use environment variables or config files (add to .gitignore)
- **Restrict permissions**: Only grant necessary bot permissions
- **Rate limiting**: Built-in to prevent abuse
- **Input validation**: All inputs are sanitized
- **Session isolation**: Each user has isolated session

## Performance

- **Concurrent users**: Handles multiple users simultaneously via async
- **Streaming**: Real-time updates minimize perceived latency
- **Caching**: Vera's memory system caches common queries
- **Rate limits**: Respects platform rate limits automatically

## Future Enhancements

Potential additions:
- [ ] Voice message support (Telegram)
- [ ] File analysis (upload documents)
- [ ] Rich embeds with images
- [ ] Interactive buttons/menus
- [ ] Multi-user collaboration
- [ ] Admin commands
- [ ] Usage analytics
- [ ] Slash command support (Discord)

## License

Same as Vera project.

## Support

For issues or questions:
1. Check Vera documentation
2. Review bot setup steps
3. Check platform documentation
4. Open GitHub issue

## Contributing

Contributions welcome! Areas of interest:
- Additional platforms (WhatsApp, Teams, etc.)
- Enhanced formatting
- Interactive features
- Performance optimizations