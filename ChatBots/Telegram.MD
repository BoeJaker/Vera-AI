# Telegram Bot Setup Guide

## Quick Start

### 1. Install Dependencies

```bash
pip install python-telegram-bot python-dotenv
```

### 2. Get Your Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the instructions
3. Copy the bot token you receive

### 3. Get Your User ID

1. Open Telegram and search for `@userinfobot`
2. Send `/start`
3. Copy your numeric user ID

### 4. Create .env File

Create a `.env` file in the same directory as `telegram_bot.py`:

```bash
# Copy the example file
cp .env.example .env

# Edit with your values
nano .env
```

Add your credentials:

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_OWNER_IDS=123456789
```

### 5. Run the Bot

```bash
python telegram_bot.py
```

## Configuration Options

### Required Variables

- **TELEGRAM_BOT_TOKEN**: Your bot token from @BotFather
- **TELEGRAM_OWNER_IDS**: Your Telegram user ID (comma-separated for multiple owners)

### Optional Variables

- **TELEGRAM_ADMIN_IDS**: Additional admin user IDs (comma-separated)
  ```env
  TELEGRAM_ADMIN_IDS=987654321,111222333
  ```

- **TELEGRAM_ALLOWED_CHATS**: Restrict bot to specific chat IDs
  ```env
  TELEGRAM_ALLOWED_CHATS=-10012345678,-10087654321
  ```

- **TELEGRAM_RATE_LIMIT_SECONDS**: Minimum seconds between messages per user (default: 2)
  ```env
  TELEGRAM_RATE_LIMIT_SECONDS=3
  ```

- **TELEGRAM_MAX_MESSAGE_LENGTH**: Maximum message length to process (default: 4000)
  ```env
  TELEGRAM_MAX_MESSAGE_LENGTH=5000
  ```

- **TELEGRAM_CHAT_ID_REGISTRY**: File to store chat IDs (default: .telegram_chat_ids.json)
  ```env
  TELEGRAM_CHAT_ID_REGISTRY=.telegram_chat_ids.json
  ```

## Features

### Security

- **Owner Authentication**: Only configured owners can use the bot
- **Admin Roles**: Separate admin role with same permissions
- **Chat Restrictions**: Optional chat ID whitelist
- **Rate Limiting**: Prevents message spam
- **Message Size Limits**: Prevents abuse

### Proactive Messaging

The bot can send messages to users without them initiating:

```python
# Send to specific user
await bot.send_to_user(user_id, "Hello!")

# Send to all owners
await bot.send_to_owners("System alert!")

# Send to all admins
await bot.send_to_admins("Admin notification")

# Queue message (non-blocking)
await bot.queue_message(user_id, "Async notification")
```

### Chat ID Registry

The bot automatically registers chat IDs when users interact with it. This enables:

- Proactive messaging to users
- Persistent user tracking across restarts
- Stored in JSON file (configurable location)

## Usage

### User Commands

- `/start` - Start conversation with Vera
- `/help` - Show help message
- `/status` - Check bot status
- `/models` - List available AI models
- `/clear` - Clear conversation history
- `/chatid` - Show your chat ID

### Admin Commands

- `/notify` - Test proactive notification

## Troubleshooting

### "No owner IDs configured"

Make sure your `.env` file contains:
```env
TELEGRAM_OWNER_IDS=your_user_id_here
```

### "Not authorized"

Your user ID is not in the TELEGRAM_OWNER_IDS list. Use `/chatid` to verify your ID matches.

### "User must start conversation first"

For proactive messaging to work, users must send at least one message to the bot first. This registers their chat ID.

### Bot doesn't respond in groups

Make sure to mention the bot with `@bot_username` in group chats.

## Example .env File

```env
# Bot token from @BotFather
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Your user ID from @userinfobot
TELEGRAM_OWNER_IDS=123456789

# Optional: Additional admins
TELEGRAM_ADMIN_IDS=987654321

# Optional: Rate limiting
TELEGRAM_RATE_LIMIT_SECONDS=2

# Optional: Message size limit
TELEGRAM_MAX_MESSAGE_LENGTH=4000
```

## Security Best Practices

1. **Never commit .env files** - Add `.env` to `.gitignore`
2. **Keep bot token secret** - Treat it like a password
3. **Use chat restrictions** - Limit bot to specific groups if needed
4. **Monitor logs** - Check for unauthorized access attempts
5. **Rotate tokens** - Periodically regenerate bot token via @BotFather