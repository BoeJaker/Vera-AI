#!/usr/bin/env python3
# slack_bot.py - Slack Integration Runner

"""
Slack Bot for Vera
Connects Vera to Slack workspace using Socket Mode.

SETUP:
1. Create Slack App at api.slack.com/apps
2. Enable Socket Mode and get App Token (xapp-...)
3. Add Bot Token Scopes: chat:write, channels:history, groups:history, im:history
4. Install app to workspace and get Bot Token (xoxb-...)
5. Configure in config file or environment variables
"""

import asyncio
import os
from typing import Optional

from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest

from Vera.vera import Vera
from Vera.Logging.logging import LogContext
from vera_messaging import VeraMessaging, Message, Platform


class SlackBot:
    """Slack bot runner for Vera"""
    
    def __init__(self, vera_instance: Vera, config: dict):
        """
        Initialize Slack bot
        
        Args:
            vera_instance: Vera instance
            config: Slack configuration
        """
        self.vera = vera_instance
        self.logger = vera_instance.logger
        self.config = config
        
        # Slack clients
        self.web_client = WebClient(token=config['bot_token'])
        self.socket_client = SocketModeClient(
            app_token=config['app_token'],
            web_client=self.web_client
        )
        
        # Messaging integration
        self.messaging = VeraMessaging(vera_instance, {'slack': config})
        
        # Bot info
        self.bot_user_id = None
        
    async def start(self):
        """Start the Slack bot"""
        try:
            # Initialize messaging
            await self.messaging.initialize()
            
            # Get bot info
            auth_response = self.web_client.auth_test()
            self.bot_user_id = auth_response['user_id']
            
            self.logger.success(
                f"✓ Slack bot connected as {auth_response['user']} (@{auth_response['user_id']})"
            )
            
            # Register event handlers
            self.socket_client.socket_mode_request_listeners.append(self._handle_event)
            
            # Start Socket Mode connection
            await self.socket_client.connect()
            
            self.logger.info("🚀 Slack bot is running (Socket Mode)")
            
            # Keep running
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Shutting down Slack bot...")
            await self.shutdown()
        except Exception as e:
            self.logger.error(f"Slack bot error: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown Slack bot"""
        await self.messaging.shutdown()
        await self.socket_client.close()
        self.logger.info("Slack bot stopped")
    
    async def _handle_event(self, client: SocketModeClient, req: SocketModeRequest):
        """Handle incoming Slack events"""
        # Acknowledge the request
        response = SocketModeResponse(envelope_id=req.envelope_id)
        await client.send_socket_mode_response(response)
        
        # Process event
        if req.type == "events_api":
            event = req.payload.get("event", {})
            
            # Ignore bot messages
            if event.get("bot_id"):
                return
            
            # Handle message events
            if event.get("type") == "message":
                await self._handle_message(event)
    
    async def _handle_message(self, event: dict):
        """Handle message event"""
        # Skip if no text
        if 'text' not in event:
            return
        
        # Skip if message is from this bot
        if event.get('user') == self.bot_user_id:
            return
        
        # Check if bot is mentioned
        mentioned = f"<@{self.bot_user_id}>" in event['text']
        
        # Clean mention from text
        text = event['text'].replace(f"<@{self.bot_user_id}>", "").strip()
        
        # Get user info
        try:
            user_info = self.web_client.users_info(user=event['user'])
            username = user_info['user']['real_name'] or user_info['user']['name']
        except:
            username = event.get('user', 'unknown')
        
        # Determine if this is a DM
        channel_type = event.get('channel_type', '')
        is_dm = channel_type == 'im'
        
        # Only respond to DMs or mentions (unless configured otherwise)
        if not (is_dm or mentioned):
            if not self.config.get('respond_to_all', False):
                return
        
        # Create message object
        message = Message(
            platform=Platform.SLACK,
            user_id=event['user'],
            username=username,
            text=text,
            channel_id=event['channel'],
            thread_id=event.get('thread_ts'),
            timestamp=event.get('ts')
        )
        
        # Process with messaging integration
        await self.messaging.process_message(message)


async def main():
    """Main entry point"""
    # Load configuration
    config = {
        'bot_token': os.getenv('SLACK_BOT_TOKEN'),
        'app_token': os.getenv('SLACK_APP_TOKEN'),
        'enabled': True,
        'respond_to_all': os.getenv('SLACK_RESPOND_ALL', 'false').lower() == 'true'
    }
    
    # Validate configuration
    if not config['bot_token'] or not config['app_token']:
        print("❌ Error: SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set")
        print("\nSetup instructions:")
        print("1. Create Slack App: https://api.slack.com/apps")
        print("2. Enable Socket Mode and get App Token (xapp-...)")
        print("3. Add Bot Token Scopes: chat:write, channels:history, groups:history, im:history")
        print("4. Install to workspace and get Bot Token (xoxb-...)")
        print("\nSet environment variables:")
        print("  export SLACK_BOT_TOKEN=xoxb-...")
        print("  export SLACK_APP_TOKEN=xapp-...")
        return
    
    # Initialize Vera
    print("Initializing Vera...")
    vera = Vera()
    
    # Start Slack bot
    bot = SlackBot(vera, config)
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())