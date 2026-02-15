#!/usr/bin/env python3
# telegram_bot.py - Telegram Integration with Proactive Messaging

"""
Telegram Bot for Vera
Connects Vera to Telegram with security hardening and proactive messaging.

FEATURES:
- Secure owner/admin authentication
- Proactive messaging to owners
- Background notification support
- Chat ID registry for user tracking
"""

import asyncio
import os
import time
import re
from collections import defaultdict
from typing import Optional, Set, Dict
import json

from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from Vera.vera import Vera
from Vera.Logging.logging import LogContext
from Vera.ChatBots.vera_messaging import VeraMessaging, Message, Platform

# Load environment variables from .env file
load_dotenv()


# ====================================================================
# SECURITY CONFIGURATION
# ====================================================================

class SecurityConfig:
    """
    Security settings for Telegram bot.
    
    User IDs are loaded from .env file:
    - TELEGRAM_OWNER_IDS: Comma-separated list of owner user IDs
    - TELEGRAM_ADMIN_IDS: Comma-separated list of admin user IDs (optional)
    - TELEGRAM_ALLOWED_CHATS: Comma-separated list of allowed chat IDs (optional)
    
    To get your Telegram user ID, message @userinfobot on Telegram.
    """
    
    @staticmethod
    def _parse_id_list(env_var: str) -> Set[int]:
        """Parse comma-separated IDs from environment variable"""
        value = os.getenv(env_var, '').strip()
        if not value:
            return set()
        
        try:
            return {int(id.strip()) for id in value.split(',') if id.strip()}
        except ValueError as e:
            print(f"⚠️  Warning: Invalid ID format in {env_var}: {e}")
            return set()
    
    # User authorization - loaded from .env
    OWNERS = _parse_id_list.__func__('TELEGRAM_OWNER_IDS')
    ADMINS = _parse_id_list.__func__('TELEGRAM_ADMIN_IDS')
    ALLOWED_CHATS = _parse_id_list.__func__('TELEGRAM_ALLOWED_CHATS')
    
    # Rate limiting
    RATE_LIMIT_SECONDS = int(os.getenv('TELEGRAM_RATE_LIMIT_SECONDS', '2'))
    
    # Message constraints
    MAX_MESSAGE_LENGTH = int(os.getenv('TELEGRAM_MAX_MESSAGE_LENGTH', '4000'))
    
    # Proactive messaging
    CHAT_ID_REGISTRY_FILE = os.getenv('TELEGRAM_CHAT_ID_REGISTRY', '.telegram_chat_ids.json')


# ====================================================================
# TEXT PROCESSING FOR TELEGRAM
# ====================================================================

def clean_text_for_telegram(text: str) -> str:
    """
    Clean text for Telegram HTML parsing.
    
    - Converts <thought> tags to formatted blocks
    - Strips other unsupported tags
    - Escapes special characters
    """
    # Convert thought blocks to italic code blocks
    text = re.sub(
        r'<thought>(.*?)</thought>',
        lambda m: f"\n\n💭 <i>Thinking...</i>\n<code>{m.group(1).strip()[:200]}</code>\n",
        text,
        flags=re.DOTALL
    )
    
    # Remove any remaining unsupported tags
    supported_tags = {'b', 'i', 'code', 'pre', 'a', 'strong', 'em', 's', 'u'}
    
    def filter_tag(match):
        tag = match.group(1).lower().split()[0]
        if tag in supported_tags or tag.startswith('/'):
            return match.group(0)
        else:
            return ''
    
    text = re.sub(r'<(/?\w+[^>]*)>', filter_tag, text)
    
    return text


class TelegramBot:
    """Telegram bot for Vera with security hardening and proactive messaging"""
    
    def __init__(self, vera_instance: Vera, config: dict):
        """
        Initialize Telegram bot
        
        Args:
            vera_instance: Vera instance
            config: Telegram configuration
        """

        self.vera = vera_instance
        self.logger = vera_instance.logger
        self.config = config
        
        # Resolve token: try 'bot_token', then 'token', then env var
        bot_token = (
            config.get('bot_token') 
            or config.get('token') 
            or os.getenv('TELEGRAM_BOT_TOKEN')
        )
        
        if not bot_token:
            raise ValueError(
                "No Telegram bot token found. Set it via:\n"
                "  1. vera_config.yaml: bots.platforms.telegram.token\n"
                "  2. Environment variable: TELEGRAM_BOT_TOKEN\n"
                "  3. .env file: TELEGRAM_BOT_TOKEN=your_token"
            )
            
        # Build application
        self.app = Application.builder().token(config['bot_token']).build()
        
        # Messaging integration
        self.messaging = VeraMessaging(vera_instance, {'telegram': config})
        
        # Bot info
        self.bot_username = None
        self.bot_user_id = None
        
        # Runtime security state
        self._last_message_time = defaultdict(float)
        
        # Chat ID registry for proactive messaging
        self.user_chat_ids: Dict[int, int] = {}  # user_id -> chat_id
        self._load_chat_registry()
        
        # Message queue for proactive messages
        self.message_queue = asyncio.Queue()
        self._message_sender_task = None
    
    # ====================================================================
    # CHAT ID REGISTRY
    # ====================================================================
    
    def _load_chat_registry(self):
        """Load chat ID registry from file"""
        registry_file = SecurityConfig.CHAT_ID_REGISTRY_FILE
        
        if os.path.exists(registry_file):
            try:
                with open(registry_file, 'r') as f:
                    data = json.load(f)
                    # Convert string keys back to ints
                    self.user_chat_ids = {int(k): int(v) for k, v in data.items()}
                self.logger.debug(f"Loaded {len(self.user_chat_ids)} chat IDs from registry")
            except Exception as e:
                self.logger.warning(f"Failed to load chat registry: {e}")
                self.user_chat_ids = {}
        else:
            self.user_chat_ids = {}
    
    def _save_chat_registry(self):
        """Save chat ID registry to file"""
        registry_file = SecurityConfig.CHAT_ID_REGISTRY_FILE
        
        try:
            with open(registry_file, 'w') as f:
                # Convert to string keys for JSON
                data = {str(k): v for k, v in self.user_chat_ids.items()}
                json.dump(data, f, indent=2)
            self.logger.debug(f"Saved {len(self.user_chat_ids)} chat IDs to registry")
        except Exception as e:
            self.logger.error(f"Failed to save chat registry: {e}")
    
    def _register_user_chat(self, user_id: int, chat_id: int):
        """Register a user's chat ID for proactive messaging"""
        if user_id not in self.user_chat_ids or self.user_chat_ids[user_id] != chat_id:
            self.user_chat_ids[user_id] = chat_id
            self._save_chat_registry()
            self.logger.debug(f"Registered chat_id {chat_id} for user {user_id}")
    
    # ====================================================================
    # PROACTIVE MESSAGING
    # ====================================================================
    
    async def send_to_user(self, user_id: int, message: str, parse_mode: str = 'HTML') -> bool:
        """
        Send a message to a specific user proactively.
        
        Args:
            user_id: Telegram user ID
            message: Message text
            parse_mode: 'HTML' or 'Markdown'
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        # Check if we have a chat ID for this user
        if user_id not in self.user_chat_ids:
            self.logger.warning(f"No chat_id found for user {user_id}. User must start conversation first.")
            return False
        
        chat_id = self.user_chat_ids[user_id]
        
        try:
            # Clean text if using HTML
            if parse_mode == 'HTML':
                message = clean_text_for_telegram(message)
            
            # Send message
            await self.app.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=parse_mode
            )
            
            self.logger.success(f"Sent proactive message to user {user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send proactive message to user {user_id}: {e}")
            return False
    
    async def send_to_owners(self, message: str, parse_mode: str = 'HTML') -> int:
        """
        Send a message to all owners.
        
        Args:
            message: Message text
            parse_mode: 'HTML' or 'Markdown'
            
        Returns:
            int: Number of owners successfully messaged
        """
        success_count = 0
        
        for owner_id in SecurityConfig.OWNERS:
            if await self.send_to_user(owner_id, message, parse_mode):
                success_count += 1
        
        self.logger.info(f"Sent proactive message to {success_count}/{len(SecurityConfig.OWNERS)} owners")
        return success_count
    
    async def send_to_admins(self, message: str, parse_mode: str = 'HTML') -> int:
        """
        Send a message to all admins.
        
        Args:
            message: Message text
            parse_mode: 'HTML' or 'Markdown'
            
        Returns:
            int: Number of admins successfully messaged
        """
        success_count = 0
        
        for admin_id in SecurityConfig.ADMINS:
            if await self.send_to_user(admin_id, message, parse_mode):
                success_count += 1
        
        self.logger.info(f"Sent proactive message to {success_count}/{len(SecurityConfig.ADMINS)} admins")
        return success_count
    
    async def queue_message(self, user_id: int, message: str, parse_mode: str = 'HTML'):
        """
        Queue a message to be sent asynchronously.
        
        Useful for non-blocking proactive notifications.
        """
        await self.message_queue.put({
            'user_id': user_id,
            'message': message,
            'parse_mode': parse_mode
        })
    
    async def _message_sender_worker(self):
        """Background worker to send queued messages"""
        while True:
            try:
                msg_data = await self.message_queue.get()
                
                if msg_data is None:  # Shutdown signal
                    break
                
                await self.send_to_user(
                    msg_data['user_id'],
                    msg_data['message'],
                    msg_data['parse_mode']
                )
                
                # Rate limit between messages
                await asyncio.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Message sender worker error: {e}")
    
    # ====================================================================
    # SECURITY HELPERS
    # ====================================================================
    
    def _is_owner(self, user_id: int) -> bool:
        """Check if user is an owner"""
        return user_id in SecurityConfig.OWNERS
    
    def _is_admin(self, user_id: int) -> bool:
        """Check if user is an admin (includes owners)"""
        return user_id in SecurityConfig.ADMINS or self._is_owner(user_id)
    
    def _is_user_allowed(self, user_id: int, chat_id: int) -> bool:
        """Check if user is allowed to use the bot"""
        if SecurityConfig.ALLOWED_CHATS:
            if chat_id not in SecurityConfig.ALLOWED_CHATS:
                return False
        return self._is_admin(user_id)
    
    def _rate_limited(self, user_id: int) -> bool:
        """Check if user is rate limited"""
        now = time.time()
        last = self._last_message_time[user_id]
        if now - last < SecurityConfig.RATE_LIMIT_SECONDS:
            return True
        self._last_message_time[user_id] = now
        return False
    
    async def _reject(self, update: Update, reason: str = "Not authorized"):
        """Send rejection message to user"""
        if update.message:
            await update.message.reply_text(f"⛔ {reason}")
    
    async def _secure_command(self, update: Update, handler, admin_only: bool = False):
        """Wrapper for secured command execution"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if not self._is_user_allowed(user_id, chat_id):
            self.logger.warning(f"Unauthorized command attempt from user {user_id}")
            await self._reject(update)
            return
        
        if admin_only and not self._is_admin(user_id):
            await self._reject(update, "Admin only command")
            return
        
        await handler(update, None)
    
    # ====================================================================
    # STARTUP / SHUTDOWN
    # ====================================================================
    
    async def start(self):
        """Start the Telegram bot"""
        try:
            # Initialize messaging
            await self.messaging.initialize()
            
            # Get bot info
            bot_info = await self.app.bot.get_me()
            self.bot_username = bot_info.username
            self.bot_user_id = bot_info.id
            
            self.logger.success(f"✓ Telegram bot connected as @{self.bot_username}")
            
            # Setup handlers
            self._setup_handlers()
            
            # Set bot commands
            await self._setup_commands()
            
            # Initialize and start
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            
            # Start message sender worker
            self._message_sender_task = asyncio.create_task(self._message_sender_worker())
            
            self.logger.info("🚀 Telegram bot is running")
            self.logger.info(f"📋 Registered chat IDs: {len(self.user_chat_ids)}")
            
            # Send startup notification to owners
            if SecurityConfig.OWNERS:  # Only if configured
                startup_msg = "🤖 <b>Vera Bot Started</b>\n\nI'm now online and ready to assist!"
                await self.send_to_owners(startup_msg)
            
            # Keep running
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Shutting down Telegram bot...")
            await self.shutdown()
        except Exception as e:
            self.logger.error(f"Telegram bot error: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown Telegram bot"""
        # Send shutdown notification to owners
        if SecurityConfig.OWNERS:
            shutdown_msg = "🛑 <b>Vera Bot Shutting Down</b>\n\nI'll be back soon!"
            await self.send_to_owners(shutdown_msg)
        
        # Stop message sender
        if self._message_sender_task:
            await self.message_queue.put(None)  # Shutdown signal
            await self._message_sender_task
        
        await self.messaging.shutdown()
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        self.logger.info("Telegram bot stopped")
    
    # ====================================================================
    # HANDLERS SETUP
    # ====================================================================
    
    def _setup_handlers(self):
        """Setup message and command handlers with security wrappers"""
        self.app.add_handler(
            CommandHandler("start", lambda u, c: self._secure_command(u, self._start_command))
        )
        self.app.add_handler(
            CommandHandler("help", lambda u, c: self._secure_command(u, self._help_command))
        )
        self.app.add_handler(
            CommandHandler("status", lambda u, c: self._secure_command(u, self._status_command))
        )
        self.app.add_handler(
            CommandHandler("models", lambda u, c: self._secure_command(u, self._models_command))
        )
        self.app.add_handler(
            CommandHandler("clear", lambda u, c: self._secure_command(u, self._clear_command))
        )
        self.app.add_handler(
            CommandHandler("notify", lambda u, c: self._secure_command(u, self._notify_command, admin_only=True))
        )
        self.app.add_handler(
            CommandHandler("chatid", lambda u, c: self._secure_command(u, self._chatid_command))
        )
        
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )
    
    async def _setup_commands(self):
        """Setup bot command menu"""
        commands = [
            BotCommand("start", "Start conversation with Vera"),
            BotCommand("help", "Show help message"),
            BotCommand("status", "Check bot status"),
            BotCommand("models", "List available models"),
            BotCommand("clear", "Clear conversation history"),
            BotCommand("chatid", "Show your chat ID"),
            BotCommand("notify", "Test proactive notification (admin)")
        ]
        
        await self.app.bot.set_my_commands(commands)
    
    # ====================================================================
    # COMMAND HANDLERS
    # ====================================================================
    
    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        # Register user's chat ID
        self._register_user_chat(update.effective_user.id, update.effective_chat.id)
        
        welcome_msg = """
👋 <b>Welcome to Vera AI!</b>

I'm Vera, an advanced AI assistant powered by multiple language models.

<b>How to use:</b>
- Just send me a message and I'll respond
- Use /help to see available commands
- Use /models to see which AI models I use

<b>What I can do:</b>
- Answer questions and provide information
- Help with coding and technical tasks
- Analyze and reason through complex problems
- Execute tools and commands (when configured)
- Send you proactive notifications and insights

Let's get started! What can I help you with?
"""
        
        await update.message.reply_html(welcome_msg)
    
    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_msg = """
<b>📚 Vera Commands</b>

<b>General:</b>
/start - Start conversation
/help - Show this message
/clear - Clear conversation history

<b>Information:</b>
/status - Check bot status
/models - List available AI models
/chatid - Show your chat ID

<b>Admin:</b>
/notify - Test proactive notification

<b>💬 Chat:</b>
Just send me a message to chat!

<b>Tips:</b>
- Be specific in your questions
- I maintain conversation context
- Use /clear to start fresh
- I can send you proactive notifications!
"""
        
        await update.message.reply_html(help_msg)
    
    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        status_msg = "<b>🤖 Bot Status</b>\n\n"
        
        if hasattr(self.vera, 'selected_models'):
            models = self.vera.selected_models
            status_msg += f"<b>Models:</b>\n"
            status_msg += f"⚡ Fast: <code>{models.fast_llm}</code>\n"
            status_msg += f"🧠 Deep: <code>{models.deep_llm}</code>\n"
        
        if hasattr(self.vera, 'orchestrator') and self.vera.orchestrator.running:
            status_msg += f"\n⚙️ Orchestrator: ✓ Running\n"
        else:
            status_msg += f"\n⚙️ Orchestrator: ✗ Offline\n"
        
        if hasattr(self.vera, 'toolchain'):
            status_msg += f"🛠️ Toolchain: ✓ Available\n"
        
        status_msg += f"\n📋 Registered Users: {len(self.user_chat_ids)}\n"
        status_msg += f"📬 Queued Messages: {self.message_queue.qsize()}\n"
        
        await update.message.reply_html(status_msg)
    
    async def _models_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /models command"""
        if not hasattr(self.vera, 'selected_models'):
            await update.message.reply_text("❌ Model information not available")
            return
        
        models = self.vera.selected_models
        
        models_msg = "<b>🤖 Available Models</b>\n\n"
        models_msg += "Vera uses different models for different tasks:\n\n"
        
        models_msg += f"⚡ <b>Fast:</b> <code>{models.fast_llm}</code>\n"
        models_msg += f"   Quick responses and simple tasks\n\n"
        
        models_msg += f"🧠 <b>Deep:</b> <code>{models.deep_llm}</code>\n"
        models_msg += f"   Complex analysis and detailed responses\n\n"
        
        if hasattr(models, 'intermediate_llm'):
            models_msg += f"📊 <b>Intermediate:</b> <code>{models.intermediate_llm}</code>\n"
            models_msg += f"   Balanced performance\n\n"
        
        if hasattr(models, 'reasoning_llm'):
            models_msg += f"🎯 <b>Reasoning:</b> <code>{models.reasoning_llm}</code>\n"
            models_msg += f"   Deep reasoning and problem solving\n"
        
        await update.message.reply_html(models_msg)
    
    async def _clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /clear command"""
        chat_id = str(update.effective_chat.id)
        
        session_key = f"telegram:{chat_id}"
        
        if session_key in self.messaging.sessions:
            del self.messaging.sessions[session_key]
            await update.message.reply_text("✓ Conversation history cleared!")
        else:
            await update.message.reply_text("No active conversation to clear.")
    
    async def _chatid_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /chatid command - show user their chat ID"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        msg = f"<b>Your Chat Info</b>\n\n"
        msg += f"User ID: <code>{user_id}</code>\n"
        msg += f"Chat ID: <code>{chat_id}</code>\n"
        
        if self._is_owner(user_id):
            msg += f"\n✅ You are an <b>OWNER</b>"
        elif self._is_admin(user_id):
            msg += f"\n✅ You are an <b>ADMIN</b>"
        
        await update.message.reply_html(msg)
    
    async def _notify_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /notify command - test proactive notification"""
        test_msg = "🔔 <b>Test Notification</b>\n\nThis is a proactive message from Vera!"
        
        success = await self.send_to_user(update.effective_user.id, test_msg)
        
        if success:
            # The message was already sent above, just acknowledge in chat
            pass
        else:
            await update.message.reply_text("❌ Failed to send notification")
    
    # ====================================================================
    # SECURED MESSAGE HANDLER
    # ====================================================================
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages with security checks"""
        if not update.message or not update.message.text:
            return
        
        user = update.effective_user
        user_id = user.id
        chat_id = update.effective_chat.id
        username = user.username or user.first_name or str(user_id)
        text = update.message.text
        
        # Register user's chat ID
        self._register_user_chat(user_id, chat_id)
        
        # Authorization check
        if not self._is_user_allowed(user_id, chat_id):
            self.logger.warning(f"Unauthorized message attempt from user {user_id}")
            await self._reject(update)
            return
        
        # Rate limiting
        if self._rate_limited(user_id):
            return
        
        # Message size validation
        if len(text) > SecurityConfig.MAX_MESSAGE_LENGTH:
            await self._reject(update, "Message too long")
            return
        
        # Audit logging
        self.logger.info(f"Telegram message from {user_id} ({username}): {text[:120]}")
        
        # Check if this is a group chat
        is_group = update.effective_chat.type in ['group', 'supergroup']
        
        # In groups, only respond if mentioned
        if is_group:
            bot_username = f"@{self.bot_username}"
            if bot_username not in text:
                return
            text = text.replace(bot_username, '').strip()
        
        # Create message object
        vera_message = Message(
            platform=Platform.TELEGRAM,
            user_id=str(user_id),
            username=username,
            text=text,
            channel_id=str(chat_id),
            thread_id=None,
            timestamp=str(update.message.date.timestamp())
        )
        
        # Process with messaging integration
        try:
            await self.messaging.process_message(vera_message)
        except Exception as e:
            self.logger.error(f"Vera processing error: {e}")
            await update.message.reply_text("⚠️ Internal error occurred while processing your message")


# ====================================================================
# ENTRYPOINT
# ====================================================================

async def main():
    """Main entry point"""
    config = {
        'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
        'enabled': True
    }
    
    if not config['bot_token']:
        print("❌ Error: TELEGRAM_BOT_TOKEN must be set")
        print("\nSetup instructions:")
        print("1. Open Telegram and talk to @BotFather")
        print("2. Send /newbot and follow instructions")
        print("3. Copy the bot token you receive")
        print("4. Message @userinfobot to get your numeric user ID")
        print("5. Add the following to your .env file:")
        print("\n  TELEGRAM_BOT_TOKEN=your_token_here")
        print("  TELEGRAM_OWNER_IDS=your_user_id_here")
        print("\nOptional .env variables:")
        print("  TELEGRAM_ADMIN_IDS=123456,789012  # Comma-separated")
        print("  TELEGRAM_ALLOWED_CHATS=-10012345678  # For specific chats")
        print("  TELEGRAM_RATE_LIMIT_SECONDS=2")
        print("  TELEGRAM_MAX_MESSAGE_LENGTH=4000")
        print("  TELEGRAM_CHAT_ID_REGISTRY=.telegram_chat_ids.json")
        return
    
    if not SecurityConfig.OWNERS:
        print("⚠️  WARNING: No owner IDs configured!")
        print("   Please add TELEGRAM_OWNER_IDS to your .env file")
        print("   Message @userinfobot on Telegram to get your ID")
        print("\n   Example .env entry:")
        print("   TELEGRAM_OWNER_IDS=123456789")
        print()
    
    print("Initializing Vera...")
    vera = Vera()
    
    bot = TelegramBot(vera, config)
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())

"""
💡 Usage Examples

Questions Stage
# Now works automatically!
def should_execute(self, focus_manager) -> bool:
    vera = focus_manager.agent
    return hasattr(vera, 'telegram_bot') and vera.telegram_bot is not None

API Endpoints
@app.post("/notify")
async def notify(message: str, session_id: str):
    vera = sessions[session_id]
    if vera.telegram_bot:
        await vera.telegram_bot.send_to_owners(message)

Proactive Focus
def on_insight(self, insight: str):
    self.agent.telegram_notify(f"💡 {insight}")
"""