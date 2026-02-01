#!/usr/bin/env python3
# telegram_bot.py - Telegram Integration Runner

"""
Telegram Bot for Vera
Connects Vera to Telegram.

SETUP:
1. Talk to @BotFather on Telegram
2. Create new bot with /newbot
3. Get bot token
4. Set TELEGRAM_BOT_TOKEN environment variable
"""

import asyncio
import os
from typing import Optional

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
from vera_messaging import VeraMessaging, Message, Platform


class TelegramBot:
    """Telegram bot for Vera"""
    
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
        
        # Build application
        self.app = Application.builder().token(config['bot_token']).build()
        
        # Messaging integration
        self.messaging = VeraMessaging(vera_instance, {'telegram': config})
        
        # Bot info
        self.bot_username = None
    
    async def start(self):
        """Start the Telegram bot"""
        try:
            # Initialize messaging
            await self.messaging.initialize()
            
            # Get bot info
            bot_info = await self.app.bot.get_me()
            self.bot_username = bot_info.username
            
            self.logger.success(f"✓ Telegram bot connected as @{self.bot_username}")
            
            # Setup handlers
            self._setup_handlers()
            
            # Set bot commands
            await self._setup_commands()
            
            # Initialize and start
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            
            self.logger.info("🚀 Telegram bot is running")
            
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
        await self.messaging.shutdown()
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        self.logger.info("Telegram bot stopped")
    
    def _setup_handlers(self):
        """Setup message and command handlers"""
        # Commands
        self.app.add_handler(CommandHandler("start", self._start_command))
        self.app.add_handler(CommandHandler("help", self._help_command))
        self.app.add_handler(CommandHandler("status", self._status_command))
        self.app.add_handler(CommandHandler("models", self._models_command))
        self.app.add_handler(CommandHandler("clear", self._clear_command))
        
        # Messages (non-command text)
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
            BotCommand("clear", "Clear conversation history")
        ]
        
        await self.app.bot.set_my_commands(commands)
    
    # ====================================================================
    # COMMAND HANDLERS
    # ====================================================================
    
    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_msg = """
👋 <b>Welcome to Vera AI!</b>

I'm Vera, an advanced AI assistant powered by multiple language models.

<b>How to use:</b>
• Just send me a message and I'll respond
• Use /help to see available commands
• Use /models to see which AI models I use

<b>What I can do:</b>
• Answer questions and provide information
• Help with coding and technical tasks
• Analyze and reason through complex problems
• Execute tools and commands (when configured)

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

<b>💬 Chat:</b>
Just send me a message to chat!

<b>Tips:</b>
• Be specific in your questions
• I maintain conversation context
• Use /clear to start fresh
"""
        
        await update.message.reply_html(help_msg)
    
    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        status_msg = "<b>🤖 Bot Status</b>\n\n"
        
        # Models
        if hasattr(self.vera, 'selected_models'):
            models = self.vera.selected_models
            status_msg += f"<b>Models:</b>\n"
            status_msg += f"⚡ Fast: <code>{models.fast_llm}</code>\n"
            status_msg += f"🧠 Deep: <code>{models.deep_llm}</code>\n"
        
        # Orchestrator
        if hasattr(self.vera, 'orchestrator') and self.vera.orchestrator.running:
            status_msg += f"\n⚙️ Orchestrator: ✓ Running\n"
        else:
            status_msg += f"\n⚙️ Orchestrator: ✗ Offline\n"
        
        # Toolchain
        if hasattr(self.vera, 'toolchain'):
            status_msg += f"🛠️ Toolchain: ✓ Available\n"
        else:
            status_msg += f"🛠️ Toolchain: ✗ Not loaded\n"
        
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
        user_id = str(update.effective_user.id)
        
        session_key = f"telegram:{chat_id}"
        
        if session_key in self.messaging.sessions:
            del self.messaging.sessions[session_key]
            await update.message.reply_text("✓ Conversation history cleared!")
        else:
            await update.message.reply_text("No active conversation to clear.")
    
    # ====================================================================
    # MESSAGE HANDLER
    # ====================================================================
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages"""
        if not update.message or not update.message.text:
            return
        
        # Get user info
        user = update.effective_user
        username = user.username or user.first_name or str(user.id)
        
        # Check if this is a group chat
        is_group = update.effective_chat.type in ['group', 'supergroup']
        
        # In groups, only respond if mentioned
        if is_group:
            bot_username = f"@{self.bot_username}"
            if bot_username not in update.message.text:
                return
            # Remove mention from text
            text = update.message.text.replace(bot_username, '').strip()
        else:
            text = update.message.text
        
        # Create message object
        vera_message = Message(
            platform=Platform.TELEGRAM,
            user_id=str(user.id),
            username=username,
            text=text,
            channel_id=str(update.effective_chat.id),
            thread_id=None,
            timestamp=str(update.message.date.timestamp())
        )
        
        # Process with messaging integration
        await self.messaging.process_message(vera_message)


async def main():
    """Main entry point"""
    # Load configuration
    config = {
        'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
        'enabled': True
    }
    
    # Validate configuration
    if not config['bot_token']:
        print("❌ Error: TELEGRAM_BOT_TOKEN must be set")
        print("\nSetup instructions:")
        print("1. Open Telegram and talk to @BotFather")
        print("2. Send /newbot and follow instructions")
        print("3. Copy the bot token you receive")
        print("\nSet environment variable:")
        print("  export TELEGRAM_BOT_TOKEN=your_token_here")
        return
    
    # Initialize Vera
    print("Initializing Vera...")
    vera = Vera()
    
    # Start Telegram bot
    bot = TelegramBot(vera, config)
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())