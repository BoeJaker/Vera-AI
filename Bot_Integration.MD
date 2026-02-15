# Vera Bot Integration Guide

## Overview

This guide shows how to integrate messaging bots (Telegram, Discord, Slack) into Vera's main initialization so they're available to all components like the Questions stage, API endpoints, and proactive focus system.

## Architecture

```
Vera.__init__()
    ├── Initialize core components
    ├── Initialize ProactiveFocusManager
    ├── Initialize agents & tools
    ├── Initialize chat handler
    └── Initialize messaging bots (NEW!)
        ├── Auto-start if configured
        ├── Run in background thread
        └── Store references (self.telegram_bot, etc.)
```

## Configuration

### Step 1: Update `vera_config.yaml`

Add this section to your `Configuration/vera_config.yaml`:

```yaml
# Messaging Bots Configuration
bots:
  enabled: true  # Master switch
  
  platforms:
    telegram:
      enabled: true
      token: null  # Or set TELEGRAM_BOT_TOKEN env var
      allowed_users: []  # Empty = all users allowed
      
    discord:
      enabled: false
      token: null
      allowed_channels: []
      
    slack:
      enabled: false
      token: null
      allowed_channels: []
  
  auto_start: true  # Start bots on Vera init
  background_thread: true  # Run in background (non-blocking)
  
  security:
    require_auth: true
    owner_ids: [123456789]  # Telegram user IDs with admin access
```

### Step 2: Set Environment Variables

```bash
export TELEGRAM_BOT_TOKEN="your-bot-token-here"
export DISCORD_BOT_TOKEN="your-discord-token"
export SLACK_BOT_TOKEN="your-slack-token"
```

## Code Changes

### 1. Modify `Vera.__init__` 

Add these methods to the `Vera` class:

```python
def _initialize_bots(self):
    """Initialize and start messaging bots in background"""
    try:
        from Vera.ChatBots.run_bots import BotManager
        import threading
        import asyncio
        
        # Build bot config from Vera config
        bot_config = self._build_bot_config_from_vera_config()
        
        # Check if any platforms enabled
        enabled_platforms = [p for p, cfg in bot_config.items() if cfg.get('enabled')]
        
        if not enabled_platforms:
            self.logger.warning("Bots enabled but no platforms configured")
            return
        
        self.logger.info(f"Starting bots for: {', '.join(enabled_platforms)}")
        
        # Create bot manager
        self.bot_manager = BotManager(bot_config, vera_instance=self)
        
        # Store telegram bot reference if enabled
        if 'telegram' in enabled_platforms:
            from Vera.ChatBots.telegram_bot import TelegramBot
            self.telegram_bot = TelegramBot(self, bot_config['telegram'])
        
        # Start in background thread
        if self.config.bots.background_thread:
            def run_bots():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.bot_manager.run())
                finally:
                    loop.close()
            
            bot_thread = threading.Thread(target=run_bots, daemon=True, name="BotManager")
            bot_thread.start()
            
            self.logger.success(f"Bots running in background: {', '.join(enabled_platforms)}")
        
    except Exception as e:
        self.logger.error(f"Failed to initialize bots: {e}", exc_info=True)


def _build_bot_config_from_vera_config(self) -> dict:
    """Build bot config dict from Vera config"""
    config = {}
    
    for platform in ['telegram', 'discord', 'slack']:
        platform_cfg = getattr(self.config.bots.platforms, platform, None)
        
        if platform_cfg:
            config[platform] = {
                'enabled': platform_cfg.enabled,
                'token': platform_cfg.token or os.getenv(f'{platform.upper()}_BOT_TOKEN'),
            }
            
            # Platform-specific settings
            if platform == 'telegram':
                config[platform]['allowed_users'] = platform_cfg.allowed_users or []
                config[platform]['owner_ids'] = self.config.bots.security.owner_ids or []
            elif platform in ['discord', 'slack']:
                config[platform]['allowed_channels'] = platform_cfg.allowed_channels or []
    
    return config
```

### 2. Update `__init__` Body

Add this AFTER chat initialization:

```python
# Initialize chat handler (AFTER all other components)
self.chat = VeraChat(self)

# --- Initialize Messaging Bots (if enabled) ---
self.telegram_bot = None
self.bot_manager = None

if self.config.bots.enabled and self.config.bots.auto_start:
    self.logger.info("Initializing messaging bots...")
    self._initialize_bots()

self.logger.success("Vera initialization complete!")
```

### 3. Update `start_bots()` Method

Replace the existing `start_bots()` method with one that respects config:

```python
def start_bots(self, platforms=None, config_file=None):
    """
    Start messaging bots using this Vera instance
    
    Args:
        platforms: Override platforms ['telegram', 'discord', 'slack']
        config_file: Override config file (optional)
    """
    from Vera.ChatBots.run_bots import BotManager, load_config_from_file
    import asyncio
    
    # Build config
    if config_file:
        config = load_config_from_file(config_file)
    elif platforms:
        config = self._build_bot_config_from_vera_config()
        for platform in config:
            config[platform]['enabled'] = platform in platforms
    else:
        config = self._build_bot_config_from_vera_config()
    
    # Validate
    enabled = [p for p, cfg in config.items() if cfg.get('enabled', False)]
    if not enabled:
        self.logger.error("No platforms enabled!")
        return
    
    # Create manager
    self.bot_manager = BotManager(config, vera_instance=self)
    
    if 'telegram' in enabled:
        from Vera.ChatBots.telegram_bot import TelegramBot
        self.telegram_bot = TelegramBot(self, config['telegram'])
    
    # Run in background thread
    def run_in_thread():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            new_loop.run_until_complete(self.bot_manager.run())
        finally:
            new_loop.close()
    
    import threading
    thread = threading.Thread(target=run_in_thread, daemon=True, name="BotManager")
    thread.start()
    
    self.logger.success(f"✓ Bots running: {', '.join(enabled)}")
```

## Usage Examples

### Example 1: Standard Startup (Auto-start from config)

```python
from Vera.vera import Vera

# Bots auto-start if bots.enabled=true and bots.auto_start=true
vera = Vera()

# Telegram bot is available immediately
if vera.telegram_bot:
    vera.telegram_notify("Vera initialized!")
```

### Example 2: Disable Auto-start

```yaml
# vera_config.yaml
bots:
  enabled: true
  auto_start: false  # Don't start automatically
```

```python
vera = Vera()

# Start manually
vera.start_bots()
```

### Example 3: Override Platforms

```python
vera = Vera()

# Start only Telegram (ignores config)
vera.start_bots(platforms=['telegram'])
```

### Example 4: Use from Questions Stage

```python
# In Vera/ProactiveFocus/stages/questions.py

def _ask_telegram_question(self, focus_manager, question: str, timeout=300):
    """Ask question via Telegram"""
    
    # Access Telegram bot via focus_manager.agent
    if not hasattr(focus_manager.agent, 'telegram_bot'):
        self._stream_output(focus_manager, "Telegram bot not available", "error")
        return None
    
    telegram = focus_manager.agent.telegram_bot
    
    # Send question to owners
    import asyncio
    loop = asyncio.get_event_loop()
    
    # Send question
    loop.run_until_complete(
        telegram.send_to_owners(f"❓ Question:\n\n{question}")
    )
    
    # Wait for response (simplified - real impl needs message handling)
    # ... response collection logic ...
    
    return response
```

### Example 5: Use from API Endpoints

```python
# In Vera/ChatUI/api/api.py

@app.post("/api/notify/telegram")
async def notify_telegram(message: str, session_id: str):
    """Send Telegram notification"""
    
    vera = get_vera_instance(session_id)
    
    if not vera.telegram_bot:
        raise HTTPException(status_code=503, detail="Telegram bot not available")
    
    await vera.telegram_bot.send_to_owners(message)
    
    return {"status": "sent"}
```

### Example 6: Use from Proactive Focus

```python
# In ProactiveFocusManager

def _on_insight_generated(self, insight: str):
    """Notify via Telegram when insight is generated"""
    
    if hasattr(self.agent, 'telegram_bot') and self.agent.telegram_bot:
        self.agent.telegram_queue_message(
            f"💡 Insight:\n\n{insight}"
        )
```

## Testing

### Test Bot Availability

```python
from Vera.vera import Vera

vera = Vera()

# Check if bots are running
print(f"Bot manager: {vera.bot_manager is not None}")
print(f"Telegram bot: {vera.telegram_bot is not None}")

# Send test message
if vera.telegram_bot:
    vera.telegram_notify("Test message!")
```

### Test from CLI

```bash
# Start with default config
python start_vera_with_bots.py

# Start with specific platforms
python start_vera_with_bots.py --telegram

# Interactive mode
python start_vera_with_bots.py --interactive
```

## Troubleshooting

### Bots Don't Start

1. Check config: `bots.enabled: true`
2. Check platform enabled: `bots.platforms.telegram.enabled: true`
3. Check token: Set `TELEGRAM_BOT_TOKEN` env var
4. Check logs: Look for "Initializing messaging bots..."

### ImportError

```bash
pip install python-telegram-bot discord.py slack-sdk
```

### Event Loop Conflicts

If you get "Event loop is already running" errors:

```yaml
bots:
  background_thread: true  # Run in separate thread
```

## Security Considerations

1. **Never commit tokens** - Use environment variables
2. **Restrict access** - Set `allowed_users` or `owner_ids`
3. **Enable auth** - Set `security.require_auth: true`
4. **Monitor usage** - Check bot logs regularly

## Benefits

✅ **Unified Configuration** - Single config file for everything
✅ **Auto-start** - Bots available immediately on Vera init
✅ **Non-blocking** - Runs in background thread
✅ **Always Available** - All components can use `vera.telegram_bot`
✅ **Easy Testing** - Simple to enable/disable via config
✅ **Production Ready** - Proper error handling and logging

## Migration from Old Method

**Before:**
```python
# Had to manually start bots
vera = Vera()
vera.start_bots(platforms=['telegram'])  # Separate step
```

**After:**
```python
# Bots auto-start from config
vera = Vera()  # Bots already running!

if vera.telegram_bot:
    vera.telegram_notify("Ready!")
```
