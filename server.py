import asyncio
import hmac
import time
import uuid
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from pydantic import BaseModel

from config import API_KEY, TASK_TIMEOUT
from task_store import TaskStore
from human_move import generate_human_path
from actions_builder import build_actions_response
import discord_notifier

app = FastAPI()


def _check_key(client_key: str) -> bool:
    if not API_KEY:
        return False
    return hmac.compare_digest(client_key, API_KEY)

static_dir = Path("static")
template_dir = Path("templates")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(template_dir))

store = TaskStore(timeout=TASK_TIMEOUT)

solver_connections: list[WebSocket] = []

public_url: str = ""


def set_public_url(url: str):
    global public_url
    public_url = url


def get_solve_url(task_id: str) -> str:
    base = public_url or "http://localhost:7777"
    return f"{base}/solve/{task_id}"


class CreateTaskRequest(BaseModel):
    clientKey: str = ""
    type: str = ""
    task: Any = {}


class GetTaskResultRequest(BaseModel):
    clientKey: str = ""
    taskId: str = ""


@app.post("/createTask")
@app.post("/createTask/index.php")
async def create_task(req: CreateTaskRequest):
    if not _check_key(req.clientKey):
        return JSONResponse({"errorId": 1, "errorCode": "ERROR_WRONG_USER_KEY"})

    if req.type == "humanMove":
        return _handle_human_move(req)

    task_data = req.task if isinstance(req.task, dict) else {}
    request_type = task_data.get("request_type", "Grid")
    question = task_data.get("question", "")
    body = task_data.get("body", "")
    examples = task_data.get("examples", [])
    human_move = task_data.get("humanMove")

    task_id = await store.create_task(
        client_key=req.clientKey,
        request_type=request_type,
        question=question,
        body=body,
        examples=examples,
        human_move=human_move,
    )

    solve_url = get_solve_url(task_id)
    print(f"[API] Created task {task_id[:8]} type={request_type} question={question[:60]}")

    asyncio.create_task(discord_notifier.notify_new_task(task_id, request_type, question, solve_url))
    asyncio.create_task(notify_solvers(task_id, request_type, question))

    return JSONResponse({"errorId": 0, "taskId": task_id})


def _handle_human_move(req: CreateTaskRequest) -> JSONResponse:
    task_data = req.task
    points = []
    if isinstance(task_data, list):
        for segment in task_data:
            if isinstance(segment, dict):
                patch = segment.get("patch", [])
                points.extend(patch)
    elif isinstance(task_data, dict):
        patch = task_data.get("patch", [])
        points.extend(patch)

    if len(points) < 2:
        return JSONResponse({"errorId": 1, "errorCode": "ERROR_BAD_PARAMETERS"})

    answers = generate_human_path(points)
    task_id = str(uuid.uuid4())
    print(f"[API] humanMove {task_id[:8]}: {len(points)} waypoints -> {sum(len(a['path']) for a in answers)} path points")

    _human_move_cache[task_id] = {
        "_created": time.time(),
        "errorId": 0,
        "status": "ready",
        "answers": answers,
        "spentTime": 0,
        "cost": 0,
    }
    return JSONResponse({"errorId": 0, "taskId": task_id})


_human_move_cache: dict[str, dict] = {}


def cleanup_human_move_cache():
    now = time.time()
    stale = [k for k, v in _human_move_cache.items() if now - v.get("_created", 0) > 60]
    for k in stale:
        del _human_move_cache[k]
    if stale:
        print(f"[HumanMove] Cleaned up {len(stale)} stale cache entries")


@app.post("/getTaskResult")
@app.post("/getTaskResult/index.php")
async def get_task_result(req: GetTaskResultRequest):
    if not _check_key(req.clientKey):
        return JSONResponse({"errorId": 1, "errorCode": "ERROR_WRONG_USER_KEY"})

    if req.taskId in _human_move_cache:
        result = _human_move_cache.pop(req.taskId)
        result.pop("_created", None)
        return JSONResponse(result)

    task = await store.get_task(req.taskId)
    if not task:
        return JSONResponse({"errorId": 1, "errorCode": "WRONG_CAPTCHA_ID"})

    if task.status == "expired":
        return JSONResponse({"errorId": 1, "errorCode": "ERROR_CAPTCHA_UNSOLVABLE"})

    if task.status == "processing":
        return JSONResponse({"errorId": 0, "status": "processing"})

    spent = round(task.solved_at - task.created_at, 1) if task.solved_at else 0
    response_answers = task.answers
    if task.human_move or task.request_type in ("Canvas", "Drag"):
        response_answers = build_actions_response(task.request_type, task.answers, task.human_move, task.body)
        if isinstance(response_answers, dict):
            action_count = len(response_answers.get("actions", []))
            print(f"[API] Task {req.taskId[:8]} type={task.request_type} actions={action_count} humanMove={'yes' if task.human_move else 'no'}")
    return JSONResponse({
        "errorId": 0,
        "status": "ready",
        "answers": response_answers,
        "spentTime": spent,
        "cost": 0,
    })


# @app.get("/", response_class=HTMLResponse)
# async def dashboard(request: Request):
#     pending = await store.get_pending_tasks()
#     return templates.TemplateResponse("dashboard.html", {
#         "request": request,
#         "tasks": pending,
#         "get_solve_url": get_solve_url,
#     })

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return HTMLResponse(status_code=404)


@app.get("/solve/{task_id}", response_class=HTMLResponse)
async def solve_page(request: Request, task_id: str):
    task = await store.get_task(task_id)
    if not task:
        return HTMLResponse("<h1>Task not found</h1>", status_code=404)
    if task.status != "processing":
        return HTMLResponse(f"<h1>Task already {task.status}</h1>", status_code=410)
    return templates.TemplateResponse("solve.html", {
        "request": request,
        "task": task,
    })


@app.post("/solve/{task_id}/submit")
async def submit_solution(task_id: str, request: Request):
    body = await request.json()
    answers = body.get("answers", [])
    if not answers:
        return JSONResponse({"error": "No answers provided"}, status_code=400)

    ok = await store.submit_answer(task_id, answers)
    if not ok:
        return JSONResponse({"error": "Task not found or already resolved"}, status_code=410)

    print(f"[Solve] Task {task_id[:8]} solved with {len(answers)} answer(s): {answers}")
    return JSONResponse({"ok": True})


@app.websocket("/ws/solver")
async def solver_ws(websocket: WebSocket):
    await websocket.accept()
    solver_connections.append(websocket)
    print(f"[WS] Solver connected. Total: {len(solver_connections)}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in solver_connections:
            solver_connections.remove(websocket)
        print(f"[WS] Solver disconnected. Total: {len(solver_connections)}")


async def notify_solvers(task_id: str, request_type: str, question: str):
    msg = {
        "type": "new_task",
        "task_id": task_id,
        "request_type": request_type,
        "question": question,
        "solve_url": get_solve_url(task_id),
    }
    disconnected = []
    for ws in solver_connections:
        try:
            await ws.send_json(msg)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in solver_connections:
            solver_connections.remove(ws)
