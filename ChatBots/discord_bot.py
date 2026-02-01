#!/usr/bin/env python3
# discord_bot.py - Discord Integration Runner

"""
Discord Bot for Vera
Connects Vera to Discord server.

SETUP:
1. Create Discord Application at discord.com/developers/applications
2. Add Bot and get Token
3. Enable MESSAGE CONTENT INTENT in Bot settings
4. Invite bot to server with permissions:
   - Read Messages/View Channels
   - Send Messages
   - Send Messages in Threads
   - Embed Links
   - Attach Files
   - Read Message History
5. Set DISCORD_BOT_TOKEN environment variable
"""

import asyncio
import os
from typing import Optional

import discord
from discord.ext import commands

from Vera.vera import Vera
from Vera.Logging.logging import LogContext
from vera_messaging import VeraMessaging, Message, Platform


class DiscordBot(commands.Bot):
    """Discord bot for Vera"""
    
    def __init__(self, vera_instance: Vera, config: dict):
        """
        Initialize Discord bot
        
        Args:
            vera_instance: Vera instance
            config: Discord configuration
        """
        # Setup intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        
        # Initialize bot
        super().__init__(
            command_prefix=config.get('prefix', '!'),
            intents=intents,
            help_command=None  # Custom help
        )
        
        self.vera = vera_instance
        self.logger = vera_instance.logger
        self.config = config
        
        # Messaging integration
        self.messaging = VeraMessaging(vera_instance, {'discord': config})
        
    async def setup_hook(self):
        """Setup hook called when bot starts"""
        # Initialize messaging
        await self.messaging.initialize()
        
        self.logger.success("✓ Discord bot initialized")
    
    async def on_ready(self):
        """Called when bot is ready"""
        self.logger.success(f"✓ Discord bot connected as {self.user} ({self.user.id})")
        self.logger.info(f"  Connected to {len(self.guilds)} server(s)")
        
        # Set status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="your questions"
            )
        )
    
    async def on_message(self, message: discord.Message):
        """Handle incoming messages"""
        # Ignore own messages
        if message.author == self.user:
            return
        
        # Ignore other bots (unless configured otherwise)
        if message.author.bot and not self.config.get('respond_to_bots', False):
            return
        
        # Check if bot is mentioned
        mentioned = self.user in message.mentions
        
        # Check if this is a DM
        is_dm = isinstance(message.channel, discord.DMChannel)
        
        # Check if message starts with prefix (command)
        is_command = message.content.startswith(self.command_prefix)
        
        # Process commands first
        if is_command:
            await self.process_commands(message)
            return
        
        # Only respond to DMs or mentions (unless configured otherwise)
        if not (is_dm or mentioned):
            if not self.config.get('respond_to_all', False):
                return
        
        # Clean mention from text
        text = message.content
        if mentioned:
            text = text.replace(f'<@{self.user.id}>', '').replace(f'<@!{self.user.id}>', '').strip()
        
        # Create message object
        vera_message = Message(
            platform=Platform.DISCORD,
            user_id=str(message.author.id),
            username=message.author.display_name,
            text=text,
            channel_id=str(message.channel.id),
            thread_id=str(message.id) if isinstance(message.channel, discord.Thread) else None,
            timestamp=str(message.created_at.timestamp())
        )
        
        # Process with messaging integration
        await self.messaging.process_message(vera_message)
    
    async def on_error(self, event, *args, **kwargs):
        """Handle errors"""
        self.logger.error(f"Discord error in {event}: {args}")
    
    async def close(self):
        """Cleanup on shutdown"""
        await self.messaging.shutdown()
        await super().close()


def setup_commands(bot: DiscordBot):
    """Setup bot commands"""
    
    @bot.command(name='help')
    async def help_command(ctx):
        """Show help message"""
        embed = discord.Embed(
            title="Vera AI Assistant",
            description="I'm Vera, an AI assistant powered by multiple LLMs.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="💬 Chat",
            value="Just mention me or DM me to chat!",
            inline=False
        )
        
        embed.add_field(
            name="🔧 Commands",
            value=f"`{bot.command_prefix}help` - Show this message\n"
                  f"`{bot.command_prefix}status` - Check bot status\n"
                  f"`{bot.command_prefix}models` - List available models",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @bot.command(name='status')
    async def status_command(ctx):
        """Check bot status"""
        embed = discord.Embed(
            title="Bot Status",
            color=discord.Color.green()
        )
        
        # Get Vera status
        models_info = ""
        if hasattr(bot.vera, 'selected_models'):
            models = bot.vera.selected_models
            models_info = f"Fast: `{models.fast_llm}`\n"
            models_info += f"Deep: `{models.deep_llm}`\n"
            if hasattr(models, 'reasoning_llm'):
                models_info += f"Reasoning: `{models.reasoning_llm}`"
        
        embed.add_field(name="🤖 Models", value=models_info or "N/A", inline=False)
        
        # Check orchestrator
        orchestrator_status = "✓ Running" if hasattr(bot.vera, 'orchestrator') and bot.vera.orchestrator.running else "✗ Offline"
        embed.add_field(name="⚙️ Orchestrator", value=orchestrator_status, inline=True)
        
        # Check toolchain
        toolchain_status = "✓ Available" if hasattr(bot.vera, 'toolchain') else "✗ Not loaded"
        embed.add_field(name="🛠️ Toolchain", value=toolchain_status, inline=True)
        
        await ctx.send(embed=embed)
    
    @bot.command(name='models')
    async def models_command(ctx):
        """List available models"""
        if not hasattr(bot.vera, 'selected_models'):
            await ctx.send("❌ Model information not available")
            return
        
        models = bot.vera.selected_models
        
        embed = discord.Embed(
            title="Available Models",
            description="Vera uses multiple models for different tasks",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="⚡ Fast", value=f"`{models.fast_llm}`", inline=False)
        embed.add_field(name="🧠 Deep", value=f"`{models.deep_llm}`", inline=False)
        
        if hasattr(models, 'intermediate_llm'):
            embed.add_field(name="📊 Intermediate", value=f"`{models.intermediate_llm}`", inline=False)
        
        if hasattr(models, 'reasoning_llm'):
            embed.add_field(name="🎯 Reasoning", value=f"`{models.reasoning_llm}`", inline=False)
        
        await ctx.send(embed=embed)
    
    @bot.command(name='clear')
    async def clear_command(ctx):
        """Clear conversation history"""
        # Clear session for this user
        session_key = f"discord:{ctx.author.id}:{ctx.channel.id}"
        
        if session_key in bot.messaging.sessions:
            del bot.messaging.sessions[session_key]
            await ctx.send("✓ Conversation history cleared!")
        else:
            await ctx.send("No active conversation to clear.")


async def main():
    """Main entry point"""
    # Load configuration
    config = {
        'bot_token': os.getenv('DISCORD_BOT_TOKEN'),
        'enabled': True,
        'prefix': os.getenv('DISCORD_PREFIX', '!'),
        'respond_to_all': os.getenv('DISCORD_RESPOND_ALL', 'false').lower() == 'true',
        'respond_to_bots': os.getenv('DISCORD_RESPOND_BOTS', 'false').lower() == 'true'
    }
    
    # Validate configuration
    if not config['bot_token']:
        print("❌ Error: DISCORD_BOT_TOKEN must be set")
        print("\nSetup instructions:")
        print("1. Create Discord Application: https://discord.com/developers/applications")
        print("2. Add Bot and copy Token")
        print("3. Enable MESSAGE CONTENT INTENT in Bot settings")
        print("4. Invite bot with required permissions")
        print("\nSet environment variable:")
        print("  export DISCORD_BOT_TOKEN=your_token_here")
        return
    
    # Initialize Vera
    print("Initializing Vera...")
    vera = Vera()
    
    # Create and setup bot
    bot = DiscordBot(vera, config)
    setup_commands(bot)
    
    # Start bot
    try:
        await bot.start(config['bot_token'])
    except KeyboardInterrupt:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())