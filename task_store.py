import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Task:
    task_id: str
    client_key: str
    request_type: str
    question: str
    body: str
    examples: list = field(default_factory=list)
    human_move: Optional[list] = None
    status: str = "processing"
    answers: Optional[list] = None
    created_at: float = field(default_factory=time.time)
    solved_at: Optional[float] = None


class TaskStore:
    def __init__(self, timeout: int = 120):
        self.tasks: dict[str, Task] = {}
        self.timeout = timeout
        self._lock = asyncio.Lock()

    async def create_task(
        self,
        client_key: str,
        request_type: str,
        question: str,
        body: str,
        examples: list | None = None,
        human_move: list | None = None,
    ) -> str:
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            client_key=client_key,
            request_type=request_type,
            question=question,
            body=body,
            examples=examples or [],
            human_move=human_move,
        )
        async with self._lock:
            self.tasks[task_id] = task
        return task_id

    async def get_task(self, task_id: str) -> Optional[Task]:
        async with self._lock:
            task = self.tasks.get(task_id)
            if task and task.status == "processing":
                if time.time() - task.created_at > self.timeout:
                    task.status = "expired"
            return task

    async def submit_answer(self, task_id: str, answers: list) -> bool:
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task or task.status != "processing":
                return False
            if time.time() - task.created_at > self.timeout:
                task.status = "expired"
                return False
            task.answers = answers
            task.status = "ready"
            task.solved_at = time.time()
            return True

    async def get_pending_tasks(self) -> list[Task]:
        now = time.time()
        pending = []
        async with self._lock:
            for task in self.tasks.values():
                if task.status == "processing":
                    if now - task.created_at > self.timeout:
                        task.status = "expired"
                    else:
                        pending.append(task)
        return pending

    async def cleanup_expired(self):
        now = time.time()
        async with self._lock:
            expired_ids = [
                tid
                for tid, t in self.tasks.items()
                if now - t.created_at > self.timeout * 3
            ]
            for tid in expired_ids:
                del self.tasks[tid]
            if expired_ids:
                print(f"[TaskStore] Cleaned up {len(expired_ids)} old tasks")
