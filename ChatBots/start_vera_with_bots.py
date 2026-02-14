#!/usr/bin/env python3
"""
Start Vera with messaging bots

Usage:
    python start_vera_with_bots.py --telegram
    python start_vera_with_bots.py --platforms telegram discord
"""

import argparse
from Vera.vera import Vera


def main():
    parser = argparse.ArgumentParser(description="Start Vera with messaging bots")
    parser.add_argument('--platforms', nargs='+', choices=['telegram', 'discord', 'slack'],
                        help='Platforms to enable')
    parser.add_argument('--telegram', action='store_true', help='Enable Telegram')
    parser.add_argument('--discord', action='store_true', help='Enable Discord')
    parser.add_argument('--slack', action='store_true', help='Enable Slack')
    parser.add_argument('--config', type=str, help='Bot config file')
    
    args = parser.parse_args()
    
    # Determine platforms
    platforms = args.platforms or []
    if args.telegram:
        platforms.append('telegram')
    if args.discord:
        platforms.append('discord')
    if args.slack:
        platforms.append('slack')
    
    # Initialize Vera (sync context - Playwright works!)
    print("Initializing Vera...")
    vera = Vera()
    
    print(f"\n✓ Vera initialized with {len(vera.playwright_tools)} Playwright tools")
    print(f"✓ Session: {vera.sess.id}")
    
    # Start bots using Vera
    vera.start_bots(platforms=platforms or None, config_file=args.config)


if __name__ == '__main__':
    main()