import asyncio
import copy
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

sys.path.insert(0, "hcaptcha-click-solver")

from patchright.async_api import async_playwright
from core.api_service import CaptchaAPIService
from core.logger import log

from core.solver import HCaptchaSolver as _BaseSolver


class HCaptchaSolver(_BaseSolver):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_canvas_size: Optional[Tuple[float, float]] = None

    async def _collect_challenge_data(self) -> Optional[Dict[str, Any]]:
        payload = await super()._collect_challenge_data()
        self._original_canvas_size = None
        if not payload:
            return payload
        frame = self.challenge_frame
        if frame and payload.get("request_type") in ("Canvas", "Drag"):
            canvas = await self._find_primary_canvas(frame)
            if canvas:
                box = await canvas.bounding_box()
                if box:
                    self._original_canvas_size = (box["width"], box["height"])
                    log.debug(
                        "Stored original canvas size: %.1fx%.1f",
                        box["width"],
                        box["height"],
                    )
        return payload

    async def _apply_answers(
        self,
        frame,
        request_type: str,
        answers: Union[List[Any], Dict[str, Any]],
    ) -> bool:
        if self._original_canvas_size and request_type in ("Canvas", "Drag"):
            canvas = await self._find_primary_canvas(frame)
            if canvas:
                box = await canvas.bounding_box()
                if box:
                    orig_w, orig_h = self._original_canvas_size
                    cur_w, cur_h = box["width"], box["height"]
                    if abs(cur_w - orig_w) > 1 or abs(cur_h - orig_h) > 1:
                        sx = cur_w / orig_w
                        sy = cur_h / orig_h
                        log.info(
                            "Canvas resized: %.1fx%.1f -> %.1fx%.1f, "
                            "scaling coordinates by (%.3f, %.3f)",
                            orig_w, orig_h, cur_w, cur_h, sx, sy,
                        )
                        answers = self._scale_answers(answers, sx, sy)
            self._original_canvas_size = None
        return await super()._apply_answers(frame, request_type, answers)

    @staticmethod
    def _scale_point(pt, sx: float, sy: float):
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            scaled = list(pt)
            scaled[0] = float(scaled[0]) * sx
            scaled[1] = float(scaled[1]) * sy
            return scaled
        return pt

    @classmethod
    def _scale_action(cls, action, sx: float, sy: float):
        if not isinstance(action, dict):
            return action
        action = dict(action)
        for key in ("path",):
            if key in action and isinstance(action[key], (list, tuple)):
                action[key] = [cls._scale_point(p, sx, sy) for p in action[key]]
        for key in ("start", "end", "target"):
            if key in action and isinstance(action[key], (list, tuple)):
                action[key] = cls._scale_point(action[key], sx, sy)
        return action

    @classmethod
    def _scale_answers(cls, answers, sx: float, sy: float):
        if isinstance(answers, dict):
            answers = copy.copy(answers)
            for key in ("actions", "steps"):
                if key in answers and isinstance(answers[key], (list, tuple)):
                    answers[key] = [cls._scale_action(a, sx, sy) for a in answers[key]]
            if "answers" in answers and isinstance(answers["answers"], (list, tuple)):
                answers["answers"] = cls._scale_answers(answers["answers"], sx, sy)
            return answers
        if isinstance(answers, (list, tuple)):
            if answers and isinstance(answers[0], dict):
                return [cls._scale_action(a, sx, sy) for a in answers]
            return [cls._scale_point(p, sx, sy) for p in answers]
        return answers


API_KEY = os.getenv("API_KEY", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:7777")
if not API_KEY:
    sys.exit("ERROR: API_KEY environment variable is required")
ATTEMPT = 10
SCREENSHOT_DIR = Path("debug_screenshots")

step = 0


async def screenshot(page, name):
    global step
    step += 1
    path = SCREENSHOT_DIR / f"{step:02d}_{name}.png"
    await page.screenshot(path=str(path), full_page=True)
    print(f"[DEBUG] Screenshot {step:02d}: {name} -> {path.name}")


async def main():
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    for old in SCREENSHOT_DIR.glob("*.png"):
        old.unlink()

    async with async_playwright() as pw:
        print("[1] Launching browser...")
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()
        await screenshot(page, "browser_launched")

        print("[2] Navigating to hCaptcha test page...")
        await page.goto("https://shimuldn.github.io/hcaptcha/", wait_until="domcontentloaded")
        await asyncio.sleep(2)
        await screenshot(page, "page_loaded")

        print("[3] Checking for hCaptcha iframe...")
        checkbox_frame = None
        for frame in page.frames:
            if "#frame=checkbox" in (frame.url or ""):
                checkbox_frame = frame
                break
        if checkbox_frame:
            print(f"    Found checkbox frame: {checkbox_frame.url[:80]}")
        else:
            print("    WARNING: No checkbox frame found yet")
        await screenshot(page, "before_solver")

        print("[4] Creating solver with custom backend...")
        solver = HCaptchaSolver(page, API_KEY, attempt=ATTEMPT)
        solver.api_service = CaptchaAPIService(
            page.context.request,
            API_KEY,
            base_url=BACKEND_URL,
            poll_interval=2.0,
            max_wait_time=120.0,
        )

        original_handle_checkbox = solver._handle_checkbox
        original_handle_challenge = solver._handle_challenge_round
        original_apply_answers = solver._apply_answers

        async def debug_handle_checkbox():
            await screenshot(page, "before_checkbox_click")
            result = await original_handle_checkbox()
            await asyncio.sleep(1)
            await screenshot(page, "after_checkbox_click")
            return result

        async def debug_handle_challenge():
            await screenshot(page, "challenge_visible")
            frame = solver.challenge_frame
            if frame:
                question = await frame.evaluate(
                    "() => document.querySelector('.prompt-text')?.textContent?.trim() || 'unknown'"
                )
                print(f"    Challenge question: {question}")
            result = await original_handle_challenge()
            await screenshot(page, "after_challenge_round")
            return result

        async def debug_apply_answers(frame, request_type, answers):
            print(f"    Applying answers: type={request_type} answers={answers}")
            await screenshot(page, f"before_apply_{request_type.lower()}")
            result = await original_apply_answers(frame, request_type, answers)
            await asyncio.sleep(0.5)
            await screenshot(page, f"after_apply_{request_type.lower()}")
            return result

        solver._handle_checkbox = debug_handle_checkbox
        solver._handle_challenge_round = debug_handle_challenge
        solver._apply_answers = debug_apply_answers

        print("[5] Starting solver...")
        start_time = time.time()
        token = await solver.solve()
        end_time = time.time()
        elapsed = end_time - start_time

        await screenshot(page, "after_solve")

        if token:
            print(f"\n[SUCCESS] Captcha solved in {elapsed:.1f}s")
            print(f"    Token: {token[:50]}...")
            await screenshot(page, "success_final")
        else:
            print(f"\n[FAILED] Could not solve captcha after {elapsed:.1f}s")
            await screenshot(page, "failure_final")

        await asyncio.sleep(3)
        await screenshot(page, "final_state")
        await browser.close()

    print(f"\nScreenshots saved to: {SCREENSHOT_DIR}/")
    for f in sorted(SCREENSHOT_DIR.glob("*.png")):
        print(f"  {f.name}")


if __name__ == "__main__":
    asyncio.run(main())
