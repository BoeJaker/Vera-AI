# #!/usr/bin/env python3
# """
# Start Vera with messaging bots

# Usage:
#     python start_vera_with_bots.py --telegram
#     python start_vera_with_bots.py --platforms telegram discord
# """

# import argparse
# from Vera.vera import Vera


# def main():
#     parser = argparse.ArgumentParser(description="Start Vera with messaging bots")
#     parser.add_argument('--platforms', nargs='+', choices=['telegram', 'discord', 'slack'],
#                         help='Platforms to enable')
#     parser.add_argument('--telegram', action='store_true', help='Enable Telegram')
#     parser.add_argument('--discord', action='store_true', help='Enable Discord')
#     parser.add_argument('--slack', action='store_true', help='Enable Slack')
#     parser.add_argument('--config', type=str, help='Bot config file')
    
#     args = parser.parse_args()
    
#     # Determine platforms
#     platforms = args.platforms or []
#     if args.telegram:
#         platforms.append('telegram')
#     if args.discord:
#         platforms.append('discord')
#     if args.slack:
#         platforms.append('slack')
    
#     # Initialize Vera (sync context - Playwright works!)
#     print("Initializing Vera...")
#     vera = Vera()
    
#     print(f"\n✓ Vera initialized with {len(vera.playwright_tools)} Playwright tools")
#     print(f"✓ Session: {vera.sess.id}")
    
#     # Start bots using Vera
#     vera.start_bots(platforms=platforms or None, config_file=args.config)


# if __name__ == '__main__':
#     main()

#!/usr/bin/env python3
"""
Start Vera with messaging bots

Now reads configuration from vera_config.yaml by default.

Usage:
    # Use config file settings
    python start_vera_with_bots.py
    
    # Override specific platforms
    python start_vera_with_bots.py --telegram
    python start_vera_with_bots.py --platforms telegram discord
    
    # Use custom config file
    python start_vera_with_bots.py --config custom_bot_config.json
    
    # Disable auto-start and start manually
    python start_vera_with_bots.py --no-auto-start
"""

import argparse
import os
from Vera.vera import Vera


def main():
    parser = argparse.ArgumentParser(description="Start Vera with messaging bots")
    
    parser.add_argument('--platforms', nargs='+', 
                        choices=['telegram', 'discord', 'slack'],
                        help='Override platforms from config')
    
    parser.add_argument('--telegram', action='store_true', 
                        help='Enable Telegram (overrides config)')
    parser.add_argument('--discord', action='store_true', 
                        help='Enable Discord (overrides config)')
    parser.add_argument('--slack', action='store_true', 
                        help='Enable Slack (overrides config)')
    
    parser.add_argument('--config', type=str, 
                        help='Bot config file (overrides vera_config.yaml)')
    
    parser.add_argument('--vera-config', type=str, 
                        default='Configuration/vera_config.yaml',
                        help='Vera configuration file (default: Configuration/vera_config.yaml)')
    
    parser.add_argument('--no-auto-start', action='store_true',
                        help='Disable auto-start (start bots manually)')
    
    parser.add_argument('--interactive', action='store_true',
                        help='Start interactive CLI after bots')
    
    args = parser.parse_args()
    
    # Determine platform overrides
    platforms = args.platforms or []
    if args.telegram:
        platforms.append('telegram')
    if args.discord:
        platforms.append('discord')
    if args.slack:
        platforms.append('slack')
    
    # Initialize Vera
    print("Initializing Vera...")
    print(f"Using config: {args.vera_config}")
    
    vera = Vera(config_file=args.vera_config)
    
    print(f"\n✓ Vera initialized")
    print(f"  Session: {vera.sess.id}")
    print(f"  Tools: {len(vera.tools)}")
    print(f"  Playwright tools: {len(vera.playwright_tools)}")
    
    # Check bot configuration
    if hasattr(vera.config, 'bots'):
        print(f"\nBot Configuration:")
        print(f"  Enabled: {vera.config.bots.enabled}")
        print(f"  Auto-start: {vera.config.bots.auto_start}")
        
        if vera.config.bots.enabled:
            enabled_platforms = []
            for platform in ['telegram', 'discord', 'slack']:
                platform_cfg = getattr(vera.config.bots.platforms, platform, None)
                if platform_cfg and platform_cfg.enabled:
                    enabled_platforms.append(platform)
            
            if enabled_platforms:
                print(f"  Platforms: {', '.join(enabled_platforms)}")
            else:
                print("  ⚠️  No platforms enabled in config")
    
    # Start bots
    if args.no_auto_start:
        print("\n⚠️  Auto-start disabled - call vera.start_bots() manually")
    
    elif platforms:
        # Platform override
        print(f"\nStarting bots (override): {', '.join(platforms)}")
        vera.start_bots(platforms=platforms, config_file=args.config)
    
    elif args.config:
        # Custom config file
        print(f"\nStarting bots from config: {args.config}")
        vera.start_bots(config_file=args.config)
    
    elif hasattr(vera, 'bot_manager') and vera.bot_manager:
        # Already started via auto-start
        print("\n✓ Bots auto-started from vera_config.yaml")
        print(f"  Telegram bot available: {vera.telegram_bot is not None}")
    
    else:
        # Check if bots are configured but not started
        if hasattr(vera.config, 'bots') and vera.config.bots.enabled:
            if not vera.config.bots.auto_start:
                print("\n⚠️  Bots configured but auto_start=false")
                print("Starting bots manually...")
                vera.start_bots()
        else:
            print("\n⚠️  Bots not configured in vera_config.yaml")
            print("\nTo enable:")
            print("  1. Add bot configuration to Configuration/vera_config.yaml")
            print("  2. Set bots.enabled: true")
            print("  3. Configure platform tokens")
            print("\nOr use --config to specify bot config file")
            return
    
    # Interactive mode
    if args.interactive:
        print("\n" + "="*60)
        print("Vera Interactive CLI - Bots running in background")
        print("="*60)
        print("\nCommands:")
        print("  /exit     - Exit")
        print("  /stats    - Show stats")
        print("  /bots     - Bot status")
        print("  <query>   - Send to Vera")
        print()
        
        while True:
            try:
                user_query = input("🔵 Query: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nShutting down...")
                break
            
            if user_query.lower() in ["/exit", "exit", "quit"]:
                break
            
            if user_query.lower() == "/stats":
                vera.logger.print_stats()
                continue
            
            if user_query.lower() == "/bots":
                if vera.bot_manager:
                    print(f"Bot manager: Active")
                    print(f"Telegram bot: {'Yes' if vera.telegram_bot else 'No'}")
                else:
                    print("No bots running")
                continue
            
            if not user_query:
                continue
            
            # Process query
            result = ""
            for chunk in vera.async_run(user_query):
                result += str(chunk)
            print()
    
    else:
        # Just keep main thread alive
        print("\n✓ Bots running")
        print("  Press Ctrl+C to stop\n")
        
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nShutting down...")


if __name__ == '__main__':
    main()