#!/usr/bin/env python3
# vera_messaging.py - Multi-Platform Messaging Integration

"""
Vera Messaging Integration
Connects Vera to Slack, Discord, and Telegram for multi-platform chat support.

FEATURES:
- Unified interface for all platforms
- Real-time streaming responses
- Thread/conversation management
- File upload/download support
- Rich formatting per platform
- Session persistence
- Rate limiting and error handling
"""

import asyncio
import threading
import queue
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Iterator, Callable
from dataclasses import dataclass
from enum import Enum
import time

from Vera.Logging.logging import LogContext


class Platform(Enum):
    """Supported messaging platforms"""
    SLACK = "slack"
    DISCORD = "discord"
    TELEGRAM = "telegram"


@dataclass
class Message:
    """Unified message representation"""
    platform: Platform
    user_id: str
    username: str
    text: str
    channel_id: str
    thread_id: Optional[str] = None
    timestamp: Optional[str] = None
    attachments: Optional[list] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = str(time.time())


@dataclass
class MessageContext:
    """Context for message processing"""
    message: Message
    session_id: str
    is_dm: bool
    mentioned: bool = False
    
    def to_log_context(self) -> LogContext:
        """Convert to Vera log context"""
        return LogContext(
            session_id=self.session_id,
            agent=f"{self.message.platform.value}_handler",
            extra={
                "user": self.message.username,
                "channel": self.message.channel_id,
                "thread": self.message.thread_id,
                "is_dm": self.is_dm
            }
        )


class MessageFormatter(ABC):
    """Base class for platform-specific message formatting"""
    
    @abstractmethod
    def format_response(self, text: str) -> str:
        """Format response text for platform"""
        pass
    
    @abstractmethod
    def format_code(self, code: str, language: str = "") -> str:
        """Format code block"""
        pass
    
    @abstractmethod
    def format_bold(self, text: str) -> str:
        """Format bold text"""
        pass
    
    @abstractmethod
    def format_italic(self, text: str) -> str:
        """Format italic text"""
        pass
    
    @abstractmethod
    def format_list(self, items: list) -> str:
        """Format list of items"""
        pass


class SlackFormatter(MessageFormatter):
    """Slack-specific formatting"""
    
    def format_response(self, text: str) -> str:
        # Convert markdown-style formatting to Slack
        text = text.replace("**", "*")  # Bold
        text = text.replace("__", "_")  # Italic
        return text
    
    def format_code(self, code: str, language: str = "") -> str:
        return f"```{language}\n{code}\n```"
    
    def format_bold(self, text: str) -> str:
        return f"*{text}*"
    
    def format_italic(self, text: str) -> str:
        return f"_{text}_"
    
    def format_list(self, items: list) -> str:
        return "\n".join(f"• {item}" for item in items)


class DiscordFormatter(MessageFormatter):
    """Discord-specific formatting"""
    
    def format_response(self, text: str) -> str:
        return text  # Discord uses markdown
    
    def format_code(self, code: str, language: str = "") -> str:
        return f"```{language}\n{code}\n```"
    
    def format_bold(self, text: str) -> str:
        return f"**{text}**"
    
    def format_italic(self, text: str) -> str:
        return f"*{text}*"
    
    def format_list(self, items: list) -> str:
        return "\n".join(f"• {item}" for item in items)


class TelegramFormatter(MessageFormatter):
    """Telegram-specific formatting"""
    
    def format_response(self, text: str) -> str:
        # Telegram uses HTML or Markdown
        return text
    
    def format_code(self, code: str, language: str = "") -> str:
        return f"```{language}\n{code}\n```"
    
    def format_bold(self, text: str) -> str:
        return f"<b>{text}</b>"
    
    def format_italic(self, text: str) -> str:
        return f"<i>{text}</i>"
    
    def format_list(self, items: list) -> str:
        return "\n".join(f"• {item}" for item in items)


class PlatformAdapter(ABC):
    """Base class for platform-specific adapters"""
    
    def __init__(self, config: Dict[str, Any], logger):
        self.config = config
        self.logger = logger
        self.formatter = self._get_formatter()
        self.running = False
        
    @abstractmethod
    def _get_formatter(self) -> MessageFormatter:
        """Get platform-specific formatter"""
        pass
    
    @abstractmethod
    async def start(self):
        """Start the adapter"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop the adapter"""
        pass
    
    @abstractmethod
    async def send_message(self, channel_id: str, text: str, 
                          thread_id: Optional[str] = None) -> Optional[str]:
        """Send a message and return message ID"""
        pass
    
    @abstractmethod
    async def update_message(self, channel_id: str, message_id: str, text: str):
        """Update an existing message"""
        pass
    
    @abstractmethod
    async def upload_file(self, channel_id: str, file_path: str, 
                         comment: Optional[str] = None):
        """Upload a file"""
        pass


class SlackAdapter(PlatformAdapter):
    """Slack platform adapter using slack_sdk"""
    
    def __init__(self, config: Dict[str, Any], logger):
        super().__init__(config, logger)
        self.client = None
        self.socket_client = None
        
    def _get_formatter(self) -> MessageFormatter:
        return SlackFormatter()
    
    async def start(self):
        """Start Slack connection"""
        try:
            from slack_sdk import WebClient
            from slack_sdk.socket_mode import SocketModeClient
            from slack_sdk.socket_mode.response import SocketModeResponse
            from slack_sdk.socket_mode.request import SocketModeRequest
            
            self.client = WebClient(token=self.config['bot_token'])
            self.socket_client = SocketModeClient(
                app_token=self.config['app_token'],
                web_client=self.client
            )
            
            # Test connection
            auth_response = self.client.auth_test()
            self.bot_user_id = auth_response['user_id']
            
            self.logger.success(f"Slack connected as {auth_response['user']}")
            self.running = True
            
        except Exception as e:
            self.logger.error(f"Failed to start Slack adapter: {e}")
            raise
    
    async def stop(self):
        """Stop Slack connection"""
        self.running = False
        if self.socket_client:
            await self.socket_client.close()
        self.logger.info("Slack adapter stopped")
    
    async def send_message(self, channel_id: str, text: str, 
                          thread_id: Optional[str] = None) -> Optional[str]:
        """Send message to Slack"""
        try:
            formatted = self.formatter.format_response(text)
            
            response = self.client.chat_postMessage(
                channel=channel_id,
                text=formatted,
                thread_ts=thread_id
            )
            
            return response['ts']
            
        except Exception as e:
            self.logger.error(f"Failed to send Slack message: {e}")
            return None
    
    async def update_message(self, channel_id: str, message_id: str, text: str):
        """Update Slack message"""
        try:
            formatted = self.formatter.format_response(text)
            
            self.client.chat_update(
                channel=channel_id,
                ts=message_id,
                text=formatted
            )
            
        except Exception as e:
            self.logger.error(f"Failed to update Slack message: {e}")
    
    async def upload_file(self, channel_id: str, file_path: str, 
                         comment: Optional[str] = None):
        """Upload file to Slack"""
        try:
            self.client.files_upload_v2(
                channel=channel_id,
                file=file_path,
                initial_comment=comment
            )
            
        except Exception as e:
            self.logger.error(f"Failed to upload file to Slack: {e}")


class DiscordAdapter(PlatformAdapter):
    """Discord platform adapter using discord.py"""
    
    def __init__(self, config: Dict[str, Any], logger):
        super().__init__(config, logger)
        self.client = None
        
    def _get_formatter(self) -> MessageFormatter:
        return DiscordFormatter()
    
    async def start(self):
        """Start Discord connection"""
        try:
            import discord
            from discord.ext import commands
            
            intents = discord.Intents.default()
            intents.message_content = True
            intents.messages = True
            
            self.client = commands.Bot(
                command_prefix=self.config.get('prefix', '!'),
                intents=intents
            )
            
            @self.client.event
            async def on_ready():
                self.logger.success(f"Discord connected as {self.client.user}")
                self.running = True
            
            # Start in background
            asyncio.create_task(self.client.start(self.config['bot_token']))
            
        except Exception as e:
            self.logger.error(f"Failed to start Discord adapter: {e}")
            raise
    
    async def stop(self):
        """Stop Discord connection"""
        self.running = False
        if self.client:
            await self.client.close()
        self.logger.info("Discord adapter stopped")
    
    async def send_message(self, channel_id: str, text: str, 
                          thread_id: Optional[str] = None) -> Optional[str]:
        """Send message to Discord"""
        try:
            channel = self.client.get_channel(int(channel_id))
            if not channel:
                self.logger.warning(f"Channel {channel_id} not found")
                return None
            
            formatted = self.formatter.format_response(text)
            
            # Split if too long (Discord limit: 2000 chars)
            if len(formatted) > 2000:
                chunks = [formatted[i:i+1900] for i in range(0, len(formatted), 1900)]
                last_msg = None
                for chunk in chunks:
                    last_msg = await channel.send(chunk)
                return str(last_msg.id) if last_msg else None
            else:
                msg = await channel.send(formatted)
                return str(msg.id)
                
        except Exception as e:
            self.logger.error(f"Failed to send Discord message: {e}")
            return None
    
    async def update_message(self, channel_id: str, message_id: str, text: str):
        """Update Discord message"""
        try:
            channel = self.client.get_channel(int(channel_id))
            if not channel:
                return
            
            msg = await channel.fetch_message(int(message_id))
            formatted = self.formatter.format_response(text)
            
            if len(formatted) > 2000:
                formatted = formatted[:1997] + "..."
            
            await msg.edit(content=formatted)
            
        except Exception as e:
            self.logger.error(f"Failed to update Discord message: {e}")
    
    async def upload_file(self, channel_id: str, file_path: str, 
                         comment: Optional[str] = None):
        """Upload file to Discord"""
        try:
            import discord
            
            channel = self.client.get_channel(int(channel_id))
            if not channel:
                return
            
            with open(file_path, 'rb') as f:
                file = discord.File(f)
                await channel.send(content=comment, file=file)
                
        except Exception as e:
            self.logger.error(f"Failed to upload file to Discord: {e}")


class TelegramAdapter(PlatformAdapter):
    """Telegram platform adapter using python-telegram-bot"""
    
    def __init__(self, config: Dict[str, Any], logger):
        super().__init__(config, logger)
        self.app = None
        
    def _get_formatter(self) -> MessageFormatter:
        return TelegramFormatter()
    
    async def start(self):
        """Start Telegram connection"""
        try:
            from telegram.ext import Application
            
            self.app = Application.builder().token(self.config['bot_token']).build()
            
            # Initialize
            await self.app.initialize()
            await self.app.start()
            
            bot_info = await self.app.bot.get_me()
            self.logger.success(f"Telegram connected as @{bot_info.username}")
            self.running = True
            
        except Exception as e:
            self.logger.error(f"Failed to start Telegram adapter: {e}")
            raise
    
    async def stop(self):
        """Stop Telegram connection"""
        self.running = False
        if self.app:
            await self.app.stop()
            await self.app.shutdown()
        self.logger.info("Telegram adapter stopped")
    
    async def send_message(self, channel_id: str, text: str, 
                          thread_id: Optional[str] = None) -> Optional[str]:
        """Send message to Telegram"""
        try:
            formatted = self.formatter.format_response(text)
            
            # Split if too long (Telegram limit: 4096 chars)
            if len(formatted) > 4096:
                chunks = [formatted[i:i+4000] for i in range(0, len(formatted), 4000)]
                last_msg = None
                for chunk in chunks:
                    last_msg = await self.app.bot.send_message(
                        chat_id=channel_id,
                        text=chunk,
                        parse_mode='HTML'
                    )
                return str(last_msg.message_id) if last_msg else None
            else:
                msg = await self.app.bot.send_message(
                    chat_id=channel_id,
                    text=formatted,
                    parse_mode='HTML'
                )
                return str(msg.message_id)
                
        except Exception as e:
            self.logger.error(f"Failed to send Telegram message: {e}")
            return None
    
    async def update_message(self, channel_id: str, message_id: str, text: str):
        """Update Telegram message"""
        try:
            formatted = self.formatter.format_response(text)
            
            if len(formatted) > 4096:
                formatted = formatted[:4093] + "..."
            
            await self.app.bot.edit_message_text(
                chat_id=channel_id,
                message_id=int(message_id),
                text=formatted,
                parse_mode='HTML'
            )
            
        except Exception as e:
            self.logger.error(f"Failed to update Telegram message: {e}")
    
    async def upload_file(self, channel_id: str, file_path: str, 
                         comment: Optional[str] = None):
        """Upload file to Telegram"""
        try:
            with open(file_path, 'rb') as f:
                await self.app.bot.send_document(
                    chat_id=channel_id,
                    document=f,
                    caption=comment
                )
                
        except Exception as e:
            self.logger.error(f"Failed to upload file to Telegram: {e}")


class VeraMessaging:
    """
    Main messaging integration class for Vera.
    Manages multiple platform adapters and routes messages to Vera.
    """
    
    def __init__(self, vera_instance, config: Dict[str, Any]):
        """
        Initialize messaging integration
        
        Args:
            vera_instance: Reference to main Vera instance
            config: Configuration for all platforms
        """
        self.vera = vera_instance
        self.logger = vera_instance.logger
        self.config = config
        
        # Platform adapters
        self.adapters: Dict[Platform, PlatformAdapter] = {}
        
        # Session management
        self.sessions: Dict[str, str] = {}  # user_key -> session_id
        
        # Message handlers
        self.message_queue = queue.Queue()
        self.handler_thread = None
        
        # Streaming state
        self.streaming_messages: Dict[str, Dict] = {}  # message_key -> state
        
        self.running = False
        
    async def initialize(self):
        """Initialize all configured platforms"""
        self.logger.info("Initializing messaging platforms...")
        
        # Initialize Slack
        if 'slack' in self.config and self.config['slack'].get('enabled', False):
            try:
                adapter = SlackAdapter(self.config['slack'], self.logger)
                await adapter.start()
                self.adapters[Platform.SLACK] = adapter
            except Exception as e:
                self.logger.error(f"Failed to initialize Slack: {e}")
        
        # Initialize Discord
        if 'discord' in self.config and self.config['discord'].get('enabled', False):
            try:
                adapter = DiscordAdapter(self.config['discord'], self.logger)
                await adapter.start()
                self.adapters[Platform.DISCORD] = adapter
            except Exception as e:
                self.logger.error(f"Failed to initialize Discord: {e}")
        
        # Initialize Telegram
        if 'telegram' in self.config and self.config['telegram'].get('enabled', False):
            try:
                adapter = TelegramAdapter(self.config['telegram'], self.logger)
                await adapter.start()
                self.adapters[Platform.TELEGRAM] = adapter
            except Exception as e:
                self.logger.error(f"Failed to initialize Telegram: {e}")
        
        self.logger.success(f"Initialized {len(self.adapters)} messaging platform(s)")
        
    async def shutdown(self):
        """Shutdown all platforms"""
        self.running = False
        
        for platform, adapter in self.adapters.items():
            try:
                await adapter.stop()
            except Exception as e:
                self.logger.error(f"Error stopping {platform.value}: {e}")
        
        self.logger.info("Messaging platforms shut down")
    
    def _get_session_key(self, message: Message) -> str:
        """Generate unique session key for user"""
        if message.thread_id:
            return f"{message.platform.value}:{message.channel_id}:{message.thread_id}"
        else:
            return f"{message.platform.value}:{message.user_id}:{message.channel_id}"
    
    def _get_or_create_session(self, message: Message) -> str:
        """Get or create Vera session for user"""
        session_key = self._get_session_key(message)
        
        if session_key not in self.sessions:
            # Create new Vera session
            if hasattr(self.vera, 'sess_manager'):
                session = self.vera.sess_manager.create_session(
                    name=f"{message.platform.value}_{message.username}",
                    metadata={
                        'platform': message.platform.value,
                        'user': message.username,
                        'channel': message.channel_id
                    }
                )
                self.sessions[session_key] = session.id
            else:
                # Fallback to simple ID
                import uuid
                self.sessions[session_key] = str(uuid.uuid4())
        
        return self.sessions[session_key]
    
    async def process_message(self, message: Message):
        """Process incoming message and generate response"""
        session_id = self._get_or_create_session(message)
        
        is_dm = not message.channel_id.startswith(('C', 'G'))  # Slack convention
        mentioned = False  # TODO: Detect @mentions
        
        msg_context = MessageContext(
            message=message,
            session_id=session_id,
            is_dm=is_dm,
            mentioned=mentioned
        )
        
        log_context = msg_context.to_log_context()
        
        self.logger.info(
            f"Processing {message.platform.value} message from {message.username}",
            context=log_context
        )
        
        # Get adapter
        adapter = self.adapters.get(message.platform)
        if not adapter:
            self.logger.error(f"No adapter for {message.platform.value}")
            return
        
        # Should we respond?
        should_respond = is_dm or mentioned or self._should_auto_respond(message)
        
        if not should_respond:
            self.logger.debug("Skipping message (not addressed to bot)", context=log_context)
            return
        
        # Send typing indicator / initial message
        message_key = f"{message.platform.value}:{message.channel_id}:{time.time()}"
        response_msg_id = await adapter.send_message(
            message.channel_id,
            "🤔 Thinking...",
            thread_id=message.thread_id
        )
        
        if not response_msg_id:
            self.logger.error("Failed to send initial message")
            return
        
        # Stream response from Vera
        await self._stream_vera_response(
            message=message,
            adapter=adapter,
            response_msg_id=response_msg_id,
            log_context=log_context
        )
    
    async def _stream_vera_response(self, message: Message, adapter: PlatformAdapter,
                                    response_msg_id: str, log_context: LogContext):
        """Stream Vera response and update message in real-time"""
        full_response = ""
        last_update = time.time()
        update_interval = 1.0  # Update every second
        
        try:
            # Switch to appropriate Vera session
            if hasattr(self.vera, 'sess_manager'):
                session_id = self._get_or_create_session(message)
                self.vera.sess_manager.set_active_session(session_id)
            
            # Stream Vera response
            for chunk in self.vera.chat.async_run(message.text):
                full_response += chunk
                
                # Update message periodically
                if time.time() - last_update >= update_interval:
                    await adapter.update_message(
                        message.channel_id,
                        response_msg_id,
                        full_response + " ⏳"
                    )
                    last_update = time.time()
            
            # Final update
            await adapter.update_message(
                message.channel_id,
                response_msg_id,
                full_response
            )
            
            self.logger.success(
                f"Response complete: {len(full_response)} chars",
                context=log_context
            )
            
        except Exception as e:
            self.logger.error(f"Error streaming response: {e}", context=log_context)
            await adapter.update_message(
                message.channel_id,
                response_msg_id,
                f"❌ Error: {str(e)}"
            )
    
    def _should_auto_respond(self, message: Message) -> bool:
        """Determine if bot should auto-respond to message"""
        # Implement custom logic here
        # For now, only respond to DMs and mentions
        return False
    
    # ====================================================================
    # PLATFORM-SPECIFIC EVENT HANDLERS
    # ====================================================================
    
    async def handle_slack_event(self, event: Dict[str, Any]):
        """Handle Slack event"""
        if event['type'] == 'message' and 'subtype' not in event:
            # Regular message
            message = Message(
                platform=Platform.SLACK,
                user_id=event['user'],
                username=event.get('user_name', event['user']),
                text=event['text'],
                channel_id=event['channel'],
                thread_id=event.get('thread_ts'),
                timestamp=event['ts']
            )
            
            await self.process_message(message)
    
    async def handle_discord_message(self, discord_message):
        """Handle Discord message"""
        if discord_message.author.bot:
            return
        
        message = Message(
            platform=Platform.DISCORD,
            user_id=str(discord_message.author.id),
            username=discord_message.author.name,
            text=discord_message.content,
            channel_id=str(discord_message.channel.id),
            thread_id=None,  # Discord threads handled differently
            timestamp=str(discord_message.created_at.timestamp())
        )
        
        await self.process_message(message)
    
    async def handle_telegram_update(self, update):
        """Handle Telegram update"""
        if not update.message:
            return
        
        tg_message = update.message
        
        message = Message(
            platform=Platform.TELEGRAM,
            user_id=str(tg_message.from_user.id),
            username=tg_message.from_user.username or tg_message.from_user.first_name,
            text=tg_message.text or "",
            channel_id=str(tg_message.chat.id),
            thread_id=None,
            timestamp=str(tg_message.date.timestamp())
        )
        
        await self.process_message(message)