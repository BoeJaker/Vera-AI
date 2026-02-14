"""
Boot and test the cognition system against a live Vera instance.

    python -m cognition
    python -m cognition --task "Analyse BTC volatility over 24h"
    python -m cognition --interactive
    python -m cognition --bg-only
    python -m cognition --config /path/to/vera_config.yaml

Requires a running Ollama instance pool and Neo4j (as configured in vera_config.yaml).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-30s] %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cognition.__main__")


def find_vera_root() -> Path:
    """Walk up from cwd looking for the directory containing Vera/."""
    cwd = Path.cwd()
    for d in [cwd, *cwd.parents]:
        if (d / "Vera").is_dir():
            return d
    return cwd


def ensure_import_path():
    """Make sure Vera is importable."""
    root = find_vera_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
        logger.info("Added %s to sys.path", root)


def create_vera(config_path: str = None):
    """Instantiate a real Vera instance."""
    ensure_import_path()
    from Vera.vera import Vera

    if config_path:
        vera = Vera(config_file=config_path)
    else:
        vera = Vera()

    return vera


def parse_args():
    p = argparse.ArgumentParser(
        description="Cognition system — Vera adapter test harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m cognition                                   # boot + one default task
  python -m cognition --task "Check disk usage"         # boot + run specific task
  python -m cognition --interactive                     # boot + REPL for tasks
  python -m cognition --bg-only --duration 300          # background loop only, 5 min
  python -m cognition --status                          # boot, print status, exit
  python -m cognition --config ~/vera_config.yaml       # custom config path
        """,
    )
    p.add_argument("--config", type=str, default=None,
                   help="Path to vera_config.yaml (default: auto-detect)")
    p.add_argument("--task", type=str, default=None,
                   help="Submit a task and watch it execute")
    p.add_argument("--priority", type=str, default="high",
                   choices=["critical", "high", "normal", "low", "idle"],
                   help="Priority for submitted task (default: high)")
    p.add_argument("--interactive", action="store_true",
                   help="Interactive REPL — submit tasks, answer questions, check status")
    p.add_argument("--bg-only", action="store_true",
                   help="Run background loop only, no tasks")
    p.add_argument("--duration", type=int, default=30,
                   help="How long to let the system run in seconds (default: 30)")
    p.add_argument("--status", action="store_true",
                   help="Print system status and exit")
    p.add_argument("--no-bg", action="store_true",
                   help="Disable background loop (focused tasks only)")
    p.add_argument("--workers", type=int, default=None,
                   help="Override max worker count")
    p.add_argument("--bg-interval", type=float, default=None,
                   help="Override background loop interval in seconds")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Debug-level logging")
    return p.parse_args()


async def print_status(manager):
    """Print a comprehensive status dump."""
    status = await manager.get_status()
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║           COGNITION SYSTEM STATUS                   ║")
    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  Running:        {status.get('running', False)}")
    print(f"║  Active Tasks:   {status.get('active_tasks', 0)}")

    sched = status.get("scheduler", {})
    print(f"║  Queue Depth:    {sched.get('queue_depth', '?')}")
    print(f"║  Active Workers: {sched.get('active_workers', '?')}/{sched.get('max_workers', '?')}")

    bg = status.get("background", {})
    if bg:
        print(f"║  BG Cycles:      {bg.get('cycles_completed', '?')}")
        print(f"║  BG Insights:    {bg.get('insights_generated', '?')}")

    print("║")

    # LLM stats
    if hasattr(manager.llm, "get_stats"):
        llm_stats = manager.llm.get_stats()
        if llm_stats:
            print("║  LLM Routing Stats:")
            for role, s in llm_stats.items():
                if role.startswith("_"):
                    continue
                print(f"║    {role:12s}: {s['calls']} calls, "
                      f"avg {s['avg_duration']:.2f}s, "
                      f"fail={s['failure_rate']:.0%}")

    # Pool health
    if hasattr(manager.llm, "get_pool_health"):
        pool = manager.llm.get_pool_health()
        if pool:
            print(f"║  Ollama Pool:    {pool.get('healthy', '?')}/{pool.get('total_instances', '?')} healthy")

    # Tool stats
    if hasattr(manager.tools, "get_stats"):
        tool_stats = manager.tools.get_stats()
        if tool_stats:
            print("║  Tool Stats:")
            for name, s in tool_stats.items():
                print(f"║    {name:16s}: {s['calls']} calls, "
                      f"{s['failures']} failures, "
                      f"avg {s['total_duration'] / max(s['calls'], 1):.2f}s")

    print("╚══════════════════════════════════════════════════════╝\n")


async def print_task_result(manager, task_id: str):
    """Print a task's final state."""
    task = await manager.get_task(task_id)
    if not task:
        print(f"  Task {task_id} not found in memory.")
        return

    status_icon = {
        "complete": "✅", "failed": "❌", "cancelled": "🚫",
        "execution": "⚙️ ", "planning": "📋", "scoping": "🔍",
        "blocked": "⏸️ ", "review": "🔎", "new": "🆕",
    }
    icon = status_icon.get(task.status.value, "❓")

    print(f"\n  {icon} Task: {task.goal}")
    print(f"     ID:       {task.id}")
    print(f"     Status:   {task.status.value}")
    print(f"     Priority: {task.priority.name}")
    print(f"     Steps:    {len(task.plan)} planned, {task.current_step_idx} executed")

    if task.error:
        print(f"     Error:    {task.error}")

    if task.progress_log:
        print(f"     Log ({len(task.progress_log)} entries):")
        for entry in task.progress_log[-10:]:
            ts = time.strftime("%H:%M:%S", time.localtime(entry.timestamp))
            print(f"       [{ts}] [{entry.level:5s}] {entry.message}")

    if task.artifacts.get("summary"):
        print(f"     Summary:  {task.artifacts['summary']}")

    if task.plan:
        print(f"     Plan:")
        for i, step in enumerate(task.plan):
            done = "✓" if step.completed else " "
            tool_info = f" [{step.tool}]" if step.tool else ""
            print(f"       [{done}] {i + 1}. {step.description}{tool_info}")


async def watch_task(manager, task_id: str, timeout: float = 60.0):
    """Poll a task until it reaches terminal state or timeout."""
    start = time.time()
    last_status = None

    while time.time() - start < timeout:
        task = await manager.get_task(task_id)
        if not task:
            await asyncio.sleep(1)
            continue

        if task.status.value != last_status:
            elapsed = time.time() - start
            step_info = ""
            if task.plan:
                step_info = f" [{task.current_step_idx}/{len(task.plan)}]"
            print(f"  [{elapsed:6.1f}s] {task.status.value}{step_info}")
            last_status = task.status.value

        if task.is_terminal():
            break

        await asyncio.sleep(0.5)

    await print_task_result(manager, task_id)


async def interactive_loop(manager):
    """REPL for submitting tasks and interacting with the cognition system."""
    from .models import TaskPriority

    print("\n  Cognition REPL — commands:")
    print("    task <description>     Submit a new task")
    print("    answer <qid> <text>    Answer a pending question")
    print("    status                 Print system status")
    print("    tasks                  List active tasks")
    print("    result <task_id>       Show task result")
    print("    tools                  List available tools")
    print("    quit / exit            Shut down")
    print()

    loop = asyncio.get_event_loop()

    while True:
        try:
            line = await loop.run_in_executor(None, lambda: input("cognition> ").strip())
        except (EOFError, KeyboardInterrupt):
            break

        if not line:
            continue

        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("quit", "exit", "q"):
            break

        elif cmd == "status":
            await print_status(manager)

        elif cmd == "task":
            if not arg:
                print("  Usage: task <description>")
                continue
            task = await manager.create_task(arg, priority=TaskPriority.HIGH)
            print(f"  Created: {task.id} — {task.goal}")
            print(f"  Watching... (Ctrl+C to stop watching)")
            try:
                await watch_task(manager, task.id, timeout=120)
            except KeyboardInterrupt:
                print("\n  Stopped watching (task continues in background)")

        elif cmd == "answer":
            sub = arg.split(maxsplit=1)
            if len(sub) < 2:
                print("  Usage: answer <question_id> <your answer>")
                continue
            qid, answer_text = sub
            await manager.answer_question(qid, answer_text)
            print(f"  Answered {qid}: {answer_text}")

        elif cmd == "tasks":
            active = await manager.memory.get_active_tasks()
            if not active:
                print("  No active tasks.")
            for t in active:
                step = f"[{t.current_step_idx}/{len(t.plan)}]" if t.plan else ""
                print(f"  {t.id}  {t.status.value:10s} {step:8s} {t.goal[:60]}")

        elif cmd == "result":
            if not arg:
                print("  Usage: result <task_id>")
                continue
            await print_task_result(manager, arg.strip())

        elif cmd == "tools":
            tool_list = await manager.tools.list_tools()
            print(f"  {len(tool_list)} tools: {', '.join(tool_list)}")

        else:
            print(f"  Unknown command: {cmd}")


async def run(args):
    from .adapter_vera import build_cognition_from_vera
    from .models import TaskPriority
    from .manager import CognitionConfig
    from .loops.background import BackgroundConfig

    # ── Boot Vera ──
    print("\n══════════════════════════════════════════════════════")
    print("  COGNITION SYSTEM — LIVE VERA BACKEND")
    print("══════════════════════════════════════════════════════\n")

    logger.info("Instantiating Vera...")
    vera = create_vera(args.config)
    logger.info("Vera initialised")

    # ── Print what we found ──
    tiers = []
    for name in ("fast_llm", "intermediate_llm", "deep_llm",
                 "reasoning_llm", "coding_llm_llm", "tool_llm"):
        llm = getattr(vera, name, None)
        if llm:
            model = getattr(llm, "model", "?")
            tiers.append(f"{name.replace('_llm', '')}={model}")
    print(f"  LLM tiers:  {', '.join(tiers) or 'none detected'}")

    tools = getattr(vera, "tools", [])
    print(f"  Tools:      {[t.name for t in tools[:10]]}" +
          (f" (+{len(tools) - 10} more)" if len(tools) > 10 else ""))

    pool = getattr(vera, "ollama_manager", None)
    if pool and hasattr(pool, "pool"):
        print(f"  Pool:       {len(pool.pool.instances)} instances")

    has_neo4j = getattr(vera, "mem", None) is not None
    has_chroma = getattr(vera, "vectorstore", None) is not None
    print(f"  Memory:     Neo4j={'✓' if has_neo4j else '✗'}, "
          f"ChromaDB={'✓' if has_chroma else '✗'}")

    has_agents = getattr(vera, "agents", None) is not None
    print(f"  Agents:     {'✓' if has_agents else '✗'}")

    # ── Build config overrides ──
    config = None
    if args.workers or args.bg_interval or args.no_bg:
        config = CognitionConfig(
            max_workers=args.workers or 3,
            enable_background_loop=not args.no_bg,
        )
        if args.bg_interval:
            config.background = BackgroundConfig(
                cycle_interval_s=args.bg_interval,
                event_lookback_s=args.bg_interval * 5,
            )

    # ── Build cognition manager ──
    logger.info("Building CognitionManager from Vera...")
    manager = await build_cognition_from_vera(vera, config=config)
    await manager.start()
    logger.info("CognitionManager running")

    # ── Handle shutdown signals ──
    shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass  # Windows

    # ── Route to mode ──
    priority_map = {
        "critical": TaskPriority.CRITICAL,
        "high": TaskPriority.HIGH,
        "normal": TaskPriority.NORMAL,
        "low": TaskPriority.LOW,
        "idle": TaskPriority.IDLE,
    }

    try:
        if args.status:
            await print_status(manager)

        elif args.interactive:
            await interactive_loop(manager)

        elif args.bg_only:
            print(f"\n  Running background loop for {args.duration}s...")
            print("  (Ctrl+C to stop)\n")
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(), timeout=args.duration
                )
            except asyncio.TimeoutError:
                pass
            await print_status(manager)

        elif args.task:
            task = await manager.create_task(
                args.task,
                priority=priority_map[args.priority],
            )
            print(f"\n  Task submitted: {task.id}")
            print(f"  Goal: {task.goal}")
            print(f"  Priority: {task.priority.name}")
            print(f"\n  Watching execution...\n")
            await watch_task(manager, task.id, timeout=args.duration)
            await print_status(manager)

        else:
            # Default: submit a diagnostic task
            task = await manager.create_task(
                "Run a system health check — verify Ollama pool status, "
                "check memory stores, and report any anomalies",
                priority=TaskPriority.NORMAL,
            )
            print(f"\n  Default task submitted: {task.id}")
            print(f"  Watching for {args.duration}s...\n")
            await watch_task(manager, task.id, timeout=args.duration)
            await print_status(manager)

    except KeyboardInterrupt:
        logger.info("Interrupted")

    finally:
        logger.info("Shutting down...")
        await manager.shutdown()
        logger.info("Done.")


def main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("cognition").setLevel(logging.DEBUG)

    asyncio.run(run(args))


if __name__ == "__main__":
    main()