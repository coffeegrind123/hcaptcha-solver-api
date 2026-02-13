import asyncio
import time

from config import API_KEY, SERVER_HOST, SERVER_PORT
from server import app, store, set_public_url, cleanup_human_move_cache
import discord_notifier


async def cleanup_loop():
    while True:
        await asyncio.sleep(60)
        await store.cleanup_expired()
        cleanup_human_move_cache()


async def main():
    start_time = time.time()

    print("=" * 60)
    print("hCaptcha Solver API - Starting...")
    print("=" * 60)

    if not API_KEY:
        print("[WARN] API_KEY is not set — all API requests will be rejected")

    public_url = f"http://{SERVER_HOST}:{SERVER_PORT}"
    set_public_url(public_url)

    runtime = int(time.time() - start_time)
    print(f"\n{'=' * 60}")
    print(f"Server Ready!")
    print(f"{'=' * 60}")
    print(f"\n  URL: {public_url}")
    print(f"  Startup: {runtime}s")
    print(f"\n{'=' * 60}\n")

    await discord_notifier.notify_startup(public_url, runtime)

    cleanup_task = asyncio.create_task(cleanup_loop())

    try:
        import uvicorn
        config = uvicorn.Config(app, host=SERVER_HOST, port=SERVER_PORT, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    except KeyboardInterrupt:
        print("\n[Shutdown] Ctrl+C received...")
    finally:
        cleanup_task.cancel()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
