import json
import sqlite3
import urllib.error
import urllib.request


class D1StorageError(sqlite3.OperationalError):
    pass


class D1Client:
    def __init__(self, environment):
        self.url = environment["RPG_D1_WORKER_URL"]
        self.token = environment["RPG_D1_SERVICE_TOKEN"]
        if not self.url.startswith("https://") or len(self.token) < 32:
            raise ValueError("Configuration D1 invalide")

    def request(self, operation, **fields):
        payload = json.dumps({"operation": operation, **fields}, separators=(",", ":")).encode()
        if len(payload) > 2_000_000:
            raise D1StorageError("Lot D1 trop volumineux")
        request = urllib.request.Request(
            self.url, payload,
            {"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read(16_000_000))
        except urllib.error.HTTPError as error:
            if error.code == 409:
                try:
                    detail = json.loads(error.read(4096))
                except ValueError:
                    detail = {}
                if detail.get("error") == "stale_runtime_fence":
                    raise RuntimeError("Moteur remplacé") from error
            raise D1StorageError("Opération D1 refusée") from error
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise D1StorageError("Opération D1 indisponible") from error
        if not isinstance(result, dict):
            raise D1StorageError("Réponse D1 invalide")
        return result

    def load_snapshot(self, fence):
        response = self.request("load_snapshot", fence=fence)
        if not isinstance(response.get("data"), dict):
            raise D1StorageError("Snapshot D1 invalide")
        return response["data"]

    def persist_checkpoint(self, fence, batch):
        changes = [
            {"table": table, "key": list(key), "row": row}
            for (table, key), row in batch.items()
        ]
        result = self.request("persist_checkpoint", fence=fence, changes=changes)
        if result.get("ok") is not True:
            raise D1StorageError("Sauvegarde D1 non confirmée")
