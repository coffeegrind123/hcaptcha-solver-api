import time
from typing import Optional

import aiohttp
from config import DISCORD_WEBHOOK

_last_task_notify = 0.0
NOTIFY_COOLDOWN = 10.0

_session: Optional[aiohttp.ClientSession] = None


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
    return _session


async def _post_webhook(message: dict):
    session = await _get_session()
    async with session.post(DISCORD_WEBHOOK, json=message) as resp:
        return resp.status


async def notify_new_task(task_id: str, request_type: str, question: str, solve_url: str):
    global _last_task_notify
    if not DISCORD_WEBHOOK:
        return
    now = time.time()
    if now - _last_task_notify < NOTIFY_COOLDOWN:
        print(f"[Discord] Skipping notification (cooldown {NOTIFY_COOLDOWN}s)")
        return
    _last_task_notify = now
    message = {
        "embeds": [
            {
                "title": "New Captcha Task",
                "color": 16750848,
                "fields": [
                    {"name": "Type", "value": request_type, "inline": True},
                    {"name": "Question", "value": question[:200], "inline": False},
                    {
                        "name": "Solve",
                        "value": f"[Click to solve]({solve_url})",
                        "inline": False,
                    },
                ],
                "footer": {"text": f"Task {task_id[:8]}"},
            }
        ]
    }
    try:
        status = await _post_webhook(message)
        if status == 204:
            print(f"[Discord] Task notification sent")
        else:
            print(f"[Discord] Notification failed: {status}")
    except Exception as e:
        print(f"[Discord] Error: {e}")


async def notify_startup(public_url: str, runtime_seconds: int = 0):
    if not DISCORD_WEBHOOK:
        return
    runtime_minutes = runtime_seconds // 60
    runtime_secs = runtime_seconds % 60
    message = {
        "embeds": [
            {
                "title": "hCaptcha Solver API - Ready!",
                "description": "The captcha solver API is now online.",
                "color": 5814783,
                "fields": [
                    {
                        "name": "Public URL",
                        "value": f"[{public_url}]({public_url})",
                        "inline": False,
                    },
                    {
                        "name": "Startup Time",
                        "value": f"{runtime_minutes}m {runtime_secs}s",
                        "inline": True,
                    },
                    {"name": "Status", "value": "Online", "inline": True},
                ],
                "footer": {"text": "Waiting for captcha tasks..."},
            }
        ]
    }
    try:
        status = await _post_webhook(message)
        if status == 204:
            print(f"[Discord] Startup notification sent")
        else:
            print(f"[Discord] Startup notification failed: {status}")
    except Exception as e:
        print(f"[Discord] Error: {e}")
