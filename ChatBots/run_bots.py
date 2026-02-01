#!/usr/bin/env python3
# run_messaging_bots.py - Unified Bot Launcher

"""
Unified Bot Launcher for Vera
Runs Slack, Discord, and/or Telegram bots simultaneously.

USAGE:
    python run_messaging_bots.py --platforms slack discord telegram
    python run_messaging_bots.py --config config.yaml
    python run_messaging_bots.py --slack  # Run only Slack
"""

import asyncio
import argparse
import os
import sys
import yaml
import signal
from typing import Dict, Any, List, Optional

from Vera.vera import Vera


class BotManager:
    """Manages multiple messaging platform bots"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize bot manager
        
        Args:
            config: Configuration for all platforms
        """
        self.config = config
        self.bots = {}
        self.vera = None
        self.running = False
        
    async def initialize_vera(self):
        """Initialize Vera instance"""
        print("🚀 Initializing Vera...")
        self.vera = Vera()
        print("✓ Vera initialized\n")
    
    async def start_slack(self):
        """Start Slack bot"""
        if 'slack' not in self.config or not self.config['slack'].get('enabled', False):
            return
        
        print("Starting Slack bot...")
        
        try:
            from slack_bot import SlackBot
            
            bot = SlackBot(self.vera, self.config['slack'])
            self.bots['slack'] = bot
            
            # Run in background task
            asyncio.create_task(bot.start())
            print("✓ Slack bot started\n")
            
        except ImportError:
            print("❌ slack_sdk not installed. Install with: pip install slack_sdk")
        except Exception as e:
            print(f"❌ Failed to start Slack bot: {e}\n")
    
    async def start_discord(self):
        """Start Discord bot"""
        if 'discord' not in self.config or not self.config['discord'].get('enabled', False):
            return
        
        print("Starting Discord bot...")
        
        try:
            from discord_bot import DiscordBot, setup_commands
            
            bot = DiscordBot(self.vera, self.config['discord'])
            setup_commands(bot)
            self.bots['discord'] = bot
            
            # Run in background task
            asyncio.create_task(bot.start(self.config['discord']['bot_token']))
            print("✓ Discord bot started\n")
            
        except ImportError:
            print("❌ discord.py not installed. Install with: pip install discord.py")
        except Exception as e:
            print(f"❌ Failed to start Discord bot: {e}\n")
    
    async def start_telegram(self):
        """Start Telegram bot"""
        if 'telegram' not in self.config or not self.config['telegram'].get('enabled', False):
            return
        
        print("Starting Telegram bot...")
        
        try:
            from telegram_bot import TelegramBot
            
            bot = TelegramBot(self.vera, self.config['telegram'])
            self.bots['telegram'] = bot
            
            # Run in background task
            asyncio.create_task(bot.start())
            print("✓ Telegram bot started\n")
            
        except ImportError:
            print("❌ python-telegram-bot not installed. Install with: pip install python-telegram-bot")
        except Exception as e:
            print(f"❌ Failed to start Telegram bot: {e}\n")
    
    async def start_all(self):
        """Start all enabled bots"""
        await self.initialize_vera()
        
        # Start each platform
        await self.start_slack()
        await self.start_discord()
        await self.start_telegram()
        
        if not self.bots:
            print("❌ No bots were started. Check your configuration.")
            return False
        
        self.running = True
        
        print(f"✓ Started {len(self.bots)} bot(s): {', '.join(self.bots.keys())}")
        print("\nBots are running. Press Ctrl+C to stop.\n")
        
        return True
    
    async def stop_all(self):
        """Stop all running bots"""
        print("\n🛑 Shutting down bots...")
        
        self.running = False
        
        for platform, bot in self.bots.items():
            try:
                print(f"  Stopping {platform}...")
                
                if hasattr(bot, 'shutdown'):
                    await bot.shutdown()
                elif hasattr(bot, 'close'):
                    await bot.close()
                    
            except Exception as e:
                print(f"  Error stopping {platform}: {e}")
        
        print("✓ All bots stopped")
    
    async def run(self):
        """Run the bot manager"""
        if not await self.start_all():
            return
        
        # Keep running until interrupted
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await self.stop_all()


def load_config_from_file(filepath: str) -> Dict[str, Any]:
    """Load configuration from YAML file"""
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)


def load_config_from_env() -> Dict[str, Any]:
    """Load configuration from environment variables"""
    config = {}
    
    # Slack
    if os.getenv('SLACK_BOT_TOKEN') and os.getenv('SLACK_APP_TOKEN'):
        config['slack'] = {
            'enabled': True,
            'bot_token': os.getenv('SLACK_BOT_TOKEN'),
            'app_token': os.getenv('SLACK_APP_TOKEN'),
            'respond_to_all': os.getenv('SLACK_RESPOND_ALL', 'false').lower() == 'true'
        }
    
    # Discord
    if os.getenv('DISCORD_BOT_TOKEN'):
        config['discord'] = {
            'enabled': True,
            'bot_token': os.getenv('DISCORD_BOT_TOKEN'),
            'prefix': os.getenv('DISCORD_PREFIX', '!'),
            'respond_to_all': os.getenv('DISCORD_RESPOND_ALL', 'false').lower() == 'true'
        }
    
    # Telegram
    if os.getenv('TELEGRAM_BOT_TOKEN'):
        config['telegram'] = {
            'enabled': True,
            'bot_token': os.getenv('TELEGRAM_BOT_TOKEN')
        }
    
    return config


def create_sample_config(filepath: str):
    """Create a sample configuration file"""
    sample = {
        'slack': {
            'enabled': False,
            'bot_token': 'xoxb-your-bot-token',
            'app_token': 'xapp-your-app-token',
            'respond_to_all': False
        },
        'discord': {
            'enabled': False,
            'bot_token': 'your-discord-bot-token',
            'prefix': '!',
            'respond_to_all': False
        },
        'telegram': {
            'enabled': False,
            'bot_token': 'your-telegram-bot-token'
        }
    }
    
    with open(filepath, 'w') as f:
        yaml.dump(sample, f, default_flow_style=False)
    
    print(f"✓ Sample configuration created: {filepath}")
    print("\nEdit this file with your bot tokens and set 'enabled: true' for each platform.")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run Vera messaging bots for Slack, Discord, and/or Telegram"
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to YAML configuration file'
    )
    
    parser.add_argument(
        '--platforms',
        nargs='+',
        choices=['slack', 'discord', 'telegram'],
        help='Specific platforms to enable (overrides config)'
    )
    
    parser.add_argument('--slack', action='store_true', help='Enable Slack only')
    parser.add_argument('--discord', action='store_true', help='Enable Discord only')
    parser.add_argument('--telegram', action='store_true', help='Enable Telegram only')
    
    parser.add_argument(
        '--create-config',
        type=str,
        metavar='FILE',
        help='Create sample configuration file and exit'
    )
    
    args = parser.parse_args()
    
    # Create sample config if requested
    if args.create_config:
        create_sample_config(args.create_config)
        return
    
    # Load configuration
    config = {}
    
    if args.config:
        print(f"Loading configuration from {args.config}...")
        config = load_config_from_file(args.config)
    else:
        print("Loading configuration from environment variables...")
        config = load_config_from_env()
    
    # Override with command line flags
    if args.platforms:
        for platform in config:
            config[platform]['enabled'] = platform in args.platforms
    
    if args.slack:
        if 'slack' in config:
            config['slack']['enabled'] = True
    
    if args.discord:
        if 'discord' in config:
            config['discord']['enabled'] = True
    
    if args.telegram:
        if 'telegram' in config:
            config['telegram']['enabled'] = True
    
    # Validate configuration
    enabled_platforms = [p for p, cfg in config.items() if cfg.get('enabled', False)]
    
    if not enabled_platforms:
        print("❌ No platforms enabled!")
        print("\nOptions:")
        print("  1. Set environment variables (SLACK_BOT_TOKEN, etc.)")
        print("  2. Create config file: python run_messaging_bots.py --create-config config.yaml")
        print("  3. Use command line flags: python run_messaging_bots.py --slack --discord")
        return
    
    # Create and run bot manager
    manager = BotManager(config)
    
    # Setup signal handlers
    loop = asyncio.get_event_loop()
    
    def signal_handler(sig):
        print(f"\n\nReceived signal {sig}")
        asyncio.create_task(manager.stop_all())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))
    
    # Run
    await manager.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✓ Shutdown complete")