# hCaptcha Solver API

<img width="865" height="919" alt="image" src="https://github.com/user-attachments/assets/00342f6f-bd8b-410c-b55b-7dbcfa575e31" />


A FastAPI backend that receives hCaptcha challenges, presents them to human solvers through a web interface, and returns solutions via API. Integrates with the [hcaptcha-click-solver](hcaptcha-click-solver/) library for browser automation.

## How It Works

1. A client submits a captcha task via `POST /createTask` with the challenge image and metadata.
2. The server stores the task and notifies connected solvers (via WebSocket and optionally Discord).
3. A human solver opens the task URL, views the challenge image, and submits their answer through the web UI.
4. The client polls `POST /getTaskResult` until the answer is ready.

Supported challenge types: **Grid** (select tiles), **Canvas** (click points), **Drag** (drag between points).

## Setup

```bash
pip install -r requirements.txt
```

Copy `.env.example` or create a `.env` file:

```
API_KEY=your-secret-key
SERVER_HOST=0.0.0.0
SERVER_PORT=7777
TASK_TIMEOUT=120
DISCORD_WEBHOOK=
```

## Running

```bash
python main.py
```

Or use the helper script:

```bash
./run.sh
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `API_KEY` | *(required)* | Secret key for authenticating API requests |
| `SERVER_HOST` | `0.0.0.0` | Host to bind the server to |
| `SERVER_PORT` | `7777` | Port to listen on |
| `TASK_TIMEOUT` | `120` | Seconds before an unsolved task expires |
| `DISCORD_WEBHOOK` | *(empty)* | Discord webhook URL for new-task notifications |

## API Endpoints

### `POST /createTask`

Create a new captcha task.

```json
{
  "clientKey": "your-api-key",
  "task": {
    "request_type": "Grid",
    "question": "Select the images containing a cat",
    "body": "<base64-encoded-image>",
    "examples": ["<base64-example-1>", "<base64-example-2>"]
  }
}
```

Response:

```json
{ "errorId": 0, "taskId": "uuid" }
```

### `POST /getTaskResult`

Poll for a task's result.

```json
{
  "clientKey": "your-api-key",
  "taskId": "uuid"
}
```

Response (processing):

```json
{ "errorId": 0, "status": "processing" }
```

Response (ready):

```json
{
  "errorId": 0,
  "status": "ready",
  "answers": [0, 3, 6],
  "spentTime": 12.5,
  "cost": 0
}
```

### `GET /solve/{task_id}`

Web UI page for a human solver to view and answer the challenge.

### `WebSocket /ws/solver`

Real-time notifications when new tasks are created.

## Project Structure

```
.
├── main.py              # Entry point — starts uvicorn server
├── server.py            # FastAPI app, routes, WebSocket handler
├── config.py            # Environment variable loading
├── task_store.py         # In-memory task storage with expiration
├── discord_notifier.py   # Optional Discord webhook notifications
├── actions_builder.py    # Converts answers to human-like action sequences
├── human_move.py         # Bezier curve path generation for mouse movement
├── example.py            # End-to-end example using hcaptcha-click-solver
├── static/solver.js      # Frontend solver UI logic
├── templates/
│   ├── solve.html        # Task solving page
│   └── dashboard.html    # Task dashboard (disabled)
├── hcaptcha-click-solver/ # Embedded hCaptcha solver library
│   ├── core/
│   │   ├── solver.py     # Main solver logic
│   │   ├── api_service.py # Multibot API wrapper
│   │   ├── motion.py     # Mouse movement simulation
│   │   └── logger.py     # Colored logging
│   └── README.md
├── requirements.txt
└── run.sh
```
