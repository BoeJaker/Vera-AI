#!/usr/bin/env python3
# chatbot_config_api.py - Chatbot Configuration Management API

"""
FastAPI backend for managing Vera's messaging platform configurations.
Supports Telegram, Discord, and Slack bot management.
"""

import asyncio
import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

# ============================================================
# Import Vera instances (mirroring session_history_api pattern)
# ============================================================

try:
    from Vera.ChatUI.api.session import vera_instances, sessions
except ImportError:
    # Fallback for standalone testing
    vera_instances = {}
    sessions = {}

router = APIRouter(prefix="/api/chatbots", tags=["chatbot-config"])

# ============================================================
# Models
# ============================================================

class TelegramConfig(BaseModel):
    enabled: bool = False
    token: Optional[str] = None
    allowed_users: List[int] = Field(default_factory=list)
    owner_ids: List[int] = Field(default_factory=list)
    rate_limit_seconds: int = 2
    max_message_length: int = 4000

class DiscordConfig(BaseModel):
    enabled: bool = False
    token: Optional[str] = None
    prefix: str = "!"
    allowed_channels: List[str] = Field(default_factory=list)
    respond_to_all: bool = False
    respond_to_bots: bool = False

class SlackConfig(BaseModel):
    enabled: bool = False
    bot_token: Optional[str] = None
    app_token: Optional[str] = None
    allowed_channels: List[str] = Field(default_factory=list)
    respond_to_all: bool = False

class BotSecurityConfig(BaseModel):
    owner_ids: List[int] = Field(default_factory=list)
    require_whitelist: bool = True

class ChatbotConfig(BaseModel):
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    security: BotSecurityConfig = Field(default_factory=BotSecurityConfig)
    background_thread: bool = True
    auto_start: bool = False

class PlatformStatus(BaseModel):
    platform: str
    enabled: bool
    running: bool
    connected: bool
    bot_username: Optional[str] = None
    registered_users: int = 0
    queued_messages: int = 0
    last_activity: Optional[str] = None
    error: Optional[str] = None

class BotActionRequest(BaseModel):
    platform: str
    action: str  # start, stop, restart, test

class TestNotificationRequest(BaseModel):
    platform: str
    message: str = "🔔 Test notification from Vera Bot Manager"
    user_id: Optional[int] = None

class UpdateConfigRequest(BaseModel):
    platform: str
    config: Dict[str, Any]

# ============================================================
# Helper: Get Vera instance
# ============================================================

def _get_vera():
    if not vera_instances:
        return None
    return next(iter(vera_instances.values()), None)

def _mask_token(token: Optional[str]) -> Optional[str]:
    """Mask sensitive token values for display."""
    if not token:
        return None
    if len(token) <= 8:
        return "****"
    return token[:4] + "****" + token[-4:]

def _get_bot_manager(vera):
    """Get the bot manager from a Vera instance."""
    return getattr(vera, 'bot_manager', None)

def _get_telegram_bot(vera):
    """Get the Telegram bot from a Vera instance."""
    return getattr(vera, 'telegram_bot', None)

# ============================================================
# Endpoints
# ============================================================

@router.get("/status", response_model=List[PlatformStatus])
async def get_all_platform_statuses():
    """Get runtime status for all configured platforms."""
    vera = _get_vera()
    statuses = []

    for platform in ["telegram", "discord", "slack"]:
        status = PlatformStatus(
            platform=platform,
            enabled=False,
            running=False,
            connected=False,
        )

        if vera:
            # Check vera config
            try:
                platform_cfg = getattr(vera.config.bots.platforms, platform, None)
                if platform_cfg:
                    status.enabled = platform_cfg.enabled
            except Exception:
                pass

            # Check runtime state
            bot_manager = _get_bot_manager(vera)
            if bot_manager and hasattr(bot_manager, 'bots'):
                bot = bot_manager.bots.get(platform)
                if bot:
                    status.running = True
                    status.connected = getattr(bot, 'running', False)

            # Telegram-specific runtime info
            if platform == "telegram":
                tg_bot = _get_telegram_bot(vera)
                if tg_bot:
                    status.running = True
                    status.connected = True
                    status.bot_username = getattr(tg_bot, 'bot_username', None)
                    status.registered_users = len(getattr(tg_bot, 'user_chat_ids', {}))
                    status.queued_messages = getattr(tg_bot, 'message_queue', None) and \
                                             tg_bot.message_queue.qsize() or 0

        statuses.append(status)

    return statuses


@router.get("/config", response_model=ChatbotConfig)
async def get_chatbot_config():
    """Get current chatbot configuration (tokens masked)."""
    vera = _get_vera()

    if not vera:
        return ChatbotConfig()

    try:
        bots_cfg = vera.config.bots
        security_cfg = bots_cfg.security if hasattr(bots_cfg, 'security') else None

        def get_platform(name):
            return getattr(bots_cfg.platforms, name, None) if hasattr(bots_cfg, 'platforms') else None

        tg = get_platform('telegram')
        dc = get_platform('discord')
        sl = get_platform('slack')

        return ChatbotConfig(
            telegram=TelegramConfig(
                enabled=tg.enabled if tg else False,
                token=_mask_token(tg.token if tg else None),
                allowed_users=tg.allowed_users if tg and hasattr(tg, 'allowed_users') else [],
                owner_ids=security_cfg.owner_ids if security_cfg and hasattr(security_cfg, 'owner_ids') else [],
            ),
            discord=DiscordConfig(
                enabled=dc.enabled if dc else False,
                token=_mask_token(dc.token if dc else None),
                prefix=dc.prefix if dc and hasattr(dc, 'prefix') else "!",
                allowed_channels=dc.allowed_channels if dc and hasattr(dc, 'allowed_channels') else [],
            ),
            slack=SlackConfig(
                enabled=sl.enabled if sl else False,
                bot_token=_mask_token(sl.bot_token if sl and hasattr(sl, 'bot_token') else None),
                app_token=_mask_token(sl.app_token if sl and hasattr(sl, 'app_token') else None),
                allowed_channels=sl.allowed_channels if sl and hasattr(sl, 'allowed_channels') else [],
            ),
            security=BotSecurityConfig(
                owner_ids=security_cfg.owner_ids if security_cfg and hasattr(security_cfg, 'owner_ids') else [],
            ),
            background_thread=bots_cfg.background_thread if hasattr(bots_cfg, 'background_thread') else True,
            auto_start=bots_cfg.auto_start if hasattr(bots_cfg, 'auto_start') else False,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read config: {e}")


@router.post("/config/update")
async def update_platform_config(request: UpdateConfigRequest):
    """
    Update configuration for a specific platform.
    NOTE: Token updates require restart to take effect.
    Real token values (not masked) are only accepted if they don't contain '****'.
    """
    vera = _get_vera()
    if not vera:
        raise HTTPException(status_code=404, detail="No active Vera instance")

    platform = request.platform.lower()
    if platform not in ("telegram", "discord", "slack", "security"):
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    try:
        platform_cfg = getattr(vera.config.bots.platforms, platform, None) \
                       if platform != "security" else getattr(vera.config.bots, 'security', None)

        if not platform_cfg:
            raise HTTPException(status_code=404, detail=f"Platform config not found: {platform}")

        changed = []
        for key, value in request.config.items():
            # Skip masked tokens
            if isinstance(value, str) and '****' in value:
                continue

            if hasattr(platform_cfg, key):
                old_val = getattr(platform_cfg, key, None)
                setattr(platform_cfg, key, value)
                changed.append(f"{key}: {old_val} → {value if 'token' not in key.lower() else '****'}")

        return {
            "status": "updated",
            "platform": platform,
            "changes": changed,
            "restart_required": any('token' in c.lower() for c in changed),
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/action")
async def perform_bot_action(request: BotActionRequest, background_tasks: BackgroundTasks):
    """Start, stop, or restart a bot platform."""
    vera = _get_vera()
    if not vera:
        raise HTTPException(status_code=404, detail="No active Vera instance")

    platform = request.platform.lower()
    action = request.action.lower()

    if action not in ("start", "stop", "restart", "test"):
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    try:
        if action == "start" or action == "restart":
            if action == "restart":
                # Stop first
                await _stop_platform(vera, platform)
                await asyncio.sleep(1)

            background_tasks.add_task(_start_platform, vera, platform)

            return {
                "status": "starting",
                "platform": platform,
                "action": action,
                "timestamp": datetime.utcnow().isoformat()
            }

        elif action == "stop":
            await _stop_platform(vera, platform)
            return {
                "status": "stopped",
                "platform": platform,
                "action": action,
                "timestamp": datetime.utcnow().isoformat()
            }

        elif action == "test":
            # Run a quick connectivity test
            result = await _test_platform(vera, platform)
            return {
                "status": "tested",
                "platform": platform,
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _start_platform(vera, platform: str):
    """Background task: start a specific platform bot."""
    try:
        vera.start_bots(platforms=[platform])
    except Exception as e:
        print(f"[BotManager] Error starting {platform}: {e}")


async def _stop_platform(vera, platform: str):
    """Stop a specific platform bot."""
    try:
        bot_manager = _get_bot_manager(vera)
        if bot_manager and hasattr(bot_manager, 'bots'):
            bot = bot_manager.bots.get(platform)
            if bot:
                if hasattr(bot, 'shutdown'):
                    await bot.shutdown()
                elif hasattr(bot, 'close'):
                    await bot.close()
                bot_manager.bots.pop(platform, None)

        # Telegram-specific
        if platform == "telegram":
            tg_bot = getattr(vera, 'telegram_bot', None)
            if tg_bot and hasattr(tg_bot, 'shutdown'):
                await tg_bot.shutdown()
                vera.telegram_bot = None

    except Exception as e:
        print(f"[BotManager] Error stopping {platform}: {e}")


async def _test_platform(vera, platform: str) -> Dict[str, Any]:
    """Test platform connectivity."""
    result = {"platform": platform, "success": False, "message": ""}

    try:
        if platform == "telegram":
            tg_bot = _get_telegram_bot(vera)
            if tg_bot and hasattr(tg_bot, 'app'):
                bot_info = await tg_bot.app.bot.get_me()
                result["success"] = True
                result["message"] = f"Connected as @{bot_info.username}"
                result["bot_id"] = bot_info.id
            else:
                result["message"] = "Telegram bot not running"

        elif platform == "discord":
            bot_manager = _get_bot_manager(vera)
            bot = bot_manager.bots.get("discord") if bot_manager else None
            if bot and hasattr(bot, 'user') and bot.user:
                result["success"] = True
                result["message"] = f"Connected as {bot.user.name}"
            else:
                result["message"] = "Discord bot not running"

        elif platform == "slack":
            bot_manager = _get_bot_manager(vera)
            bot = bot_manager.bots.get("slack") if bot_manager else None
            if bot and hasattr(bot, 'web_client'):
                auth = bot.web_client.auth_test()
                result["success"] = True
                result["message"] = f"Connected as {auth.get('user', 'unknown')}"
            else:
                result["message"] = "Slack bot not running"

    except Exception as e:
        result["message"] = str(e)

    return result


@router.post("/notify")
async def send_test_notification(request: TestNotificationRequest):
    """Send a test notification via the specified platform."""
    vera = _get_vera()
    if not vera:
        raise HTTPException(status_code=404, detail="No active Vera instance")

    platform = request.platform.lower()

    try:
        if platform == "telegram":
            tg_bot = _get_telegram_bot(vera)
            if not tg_bot:
                raise HTTPException(status_code=400, detail="Telegram bot not running")

            if request.user_id:
                success = await tg_bot.send_to_user(request.user_id, request.message)
            else:
                count = await tg_bot.send_to_owners(request.message)
                success = count > 0

            return {
                "status": "sent" if success else "failed",
                "platform": platform,
                "timestamp": datetime.utcnow().isoformat()
            }

        else:
            raise HTTPException(status_code=400, detail=f"Test notifications not supported for {platform}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/telegram/users")
async def get_telegram_registered_users():
    """Get list of registered Telegram users (IDs and chat IDs)."""
    vera = _get_vera()
    if not vera:
        return {"users": []}

    tg_bot = _get_telegram_bot(vera)
    if not tg_bot:
        return {"users": []}

    user_chat_ids = getattr(tg_bot, 'user_chat_ids', {})

    # Determine owner/admin status
    try:
        from Vera.ChatBots.telegram_bot import SecurityConfig
        owners = SecurityConfig.OWNERS
        admins = SecurityConfig.ADMINS
    except Exception:
        owners = set()
        admins = set()

    users = []
    for user_id, chat_id in user_chat_ids.items():
        role = "owner" if user_id in owners else ("admin" if user_id in admins else "user")
        users.append({
            "user_id": user_id,
            "chat_id": chat_id,
            "role": role
        })

    return {"users": users, "total": len(users)}


@router.get("/logs/recent")
async def get_recent_bot_logs(platform: Optional[str] = None, limit: int = 50):
    """
    Get recent bot activity logs.
    Reads from Vera's unified logging system if available.
    """
    vera = _get_vera()
    if not vera:
        return {"logs": [], "total": 0}

    # Try to read from log file
    logs = []
    try:
        log_file = getattr(vera.config.logging, 'file', None)
        if log_file and os.path.exists(log_file):
            with open(log_file, 'r') as f:
                lines = f.readlines()[-500:]  # Last 500 lines

            bot_keywords = {
                "telegram": ["telegram", "tg_bot", "TelegramBot"],
                "discord": ["discord", "DiscordBot"],
                "slack": ["slack", "SlackBot"],
            }

            filter_keywords = bot_keywords.get(platform, sum(bot_keywords.values(), [])) \
                              if platform else sum(bot_keywords.values(), [])

            for line in reversed(lines):
                if any(kw.lower() in line.lower() for kw in filter_keywords):
                    logs.append({
                        "raw": line.strip(),
                        "timestamp": _extract_log_timestamp(line),
                        "level": _extract_log_level(line),
                        "platform": _detect_platform_from_log(line)
                    })
                    if len(logs) >= limit:
                        break

    except Exception as e:
        print(f"Error reading logs: {e}")

    return {"logs": logs, "total": len(logs)}


def _extract_log_timestamp(line: str) -> Optional[str]:
    match = re.search(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', line)
    return match.group(0) if match else None


def _extract_log_level(line: str) -> str:
    for level in ["ERROR", "WARNING", "INFO", "DEBUG", "SUCCESS"]:
        if level in line.upper():
            return level
    return "INFO"


def _detect_platform_from_log(line: str) -> str:
    line_lower = line.lower()
    if "telegram" in line_lower:
        return "telegram"
    if "discord" in line_lower:
        return "discord"
    if "slack" in line_lower:
        return "slack"
    return "general"


@router.get("/stats/summary")
async def get_chatbot_stats():
    """Aggregate statistics across all bot platforms."""
    vera = _get_vera()

    stats = {
        "total_platforms": 3,
        "active_platforms": 0,
        "total_registered_users": 0,
        "total_messages_sent": 0,
        "uptime_seconds": None,
        "platforms": {}
    }

    if vera:
        # Telegram stats
        tg_bot = _get_telegram_bot(vera)
        if tg_bot:
            registered = len(getattr(tg_bot, 'user_chat_ids', {}))
            queued = tg_bot.message_queue.qsize() if hasattr(tg_bot, 'message_queue') else 0
            stats["platforms"]["telegram"] = {
                "running": True,
                "registered_users": registered,
                "queued_messages": queued,
                "bot_username": getattr(tg_bot, 'bot_username', None)
            }
            stats["active_platforms"] += 1
            stats["total_registered_users"] += registered
        else:
            stats["platforms"]["telegram"] = {"running": False}

        # Discord / Slack stubs
        for platform in ("discord", "slack"):
            bot_manager = _get_bot_manager(vera)
            bot = bot_manager.bots.get(platform) if bot_manager and hasattr(bot_manager, 'bots') else None
            if bot and getattr(bot, 'running', False):
                stats["platforms"][platform] = {"running": True}
                stats["active_platforms"] += 1
            else:
                stats["platforms"][platform] = {"running": False}

    return stats