import queue
import threading
import time

from .service import GameError


class CommandQueue:
    def __init__(self, service):
        self.service = service
        self.queue = queue.Queue(maxsize=128)
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def execute(self, token, request_id, action, params, compact=False):
        event = threading.Event()
        task = [token, request_id, action, params, event, None, compact]
        try:
            self.queue.put_nowait(task)
        except queue.Full:
            raise GameError("server_busy", "Serveur occupé, réessayez.", 503) from None
        if not event.wait(30):
            raise GameError("server_busy", "La réponse tarde ; l’action peut avoir été enregistrée. Vérifiez votre état.", 503)
        if isinstance(task[5], Exception):
            raise task[5]
        return task[5]

    def _run(self):
        while True:
            first = self.queue.get()
            if first is None:
                return
            tasks = [first]
            deadline = time.monotonic() + .002
            while len(tasks) < 32:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    tasks.append(self.queue.get(timeout=remaining))
                except queue.Empty:
                    break
            try:
                results = []
                with self.service._transaction():
                    for task in tasks:
                        try:
                            results.append(self.service.command(task[0], task[1], task[2], _compact=task[6], **task[3]))
                        except GameError as error:
                            results.append(error)
            except Exception as error:
                results = [error] * len(tasks)
            for task, result in zip(tasks, results):
                task[5] = result
                task[4].set()

    def close(self):
        self.queue.put(None)
        self.worker.join(timeout=5)
