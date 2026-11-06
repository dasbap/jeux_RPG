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
        payload = json.dumps(
            {"operation": operation, **fields}, separators=(",", ":")
        ).encode()
        if len(payload) > 2_000_000:
            raise D1StorageError("Lot D1 trop volumineux")
        request = urllib.request.Request(
            self.url,
            payload,
            {
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
                "User-Agent": "jeux-rpg-d1/1.0",
            },
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
                if (
                    isinstance(detail, dict)
                    and detail.get("error") == "stale_runtime_fence"
                ):
                    raise RuntimeError("Moteur remplacé") from error
            raise D1StorageError("Opération D1 refusée") from error
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise D1StorageError("Opération D1 indisponible") from error
        if not isinstance(result, dict):
            raise D1StorageError("Réponse D1 invalide")
        return result

    def load_snapshot(self, fence):
        return self._snapshot(self.request("load_snapshot", fence=fence))

    def read_snapshot(self):
        """Inspect durable state without taking over the running engine's fence."""
        return self._snapshot(self.request("read_snapshot"))

    def backup_snapshot(self):
        result = self.request("read_snapshot")
        data = self._snapshot(result)
        sequences = result.get("sequences")
        if not isinstance(sequences, list) or any(
            not isinstance(row, dict)
            or not isinstance(row.get("name"), str)
            or type(row.get("seq")) is not int
            or row["seq"] < 0
            for row in sequences
        ):
            raise D1StorageError("Séquences D1 invalides")
        return data, sequences

    def health(self):
        from .schema import available_migrations

        result = self.request("health")
        if (
            result.get("ok") is not True
            or result.get("version") != available_migrations()[-1][0]
            or result.get("fence_guards") != 2
        ):
            raise D1StorageError("Schéma D1 non prêt")
        return result

    @staticmethod
    def _snapshot(response):
        data = response.get("data")
        # A partial snapshot must never become the authoritative world state.
        from .realtime_store import TABLES

        if (
            not isinstance(data, dict)
            or set(data) != set(TABLES)
            or any(
                not isinstance(rows, list)
                or any(not isinstance(row, dict) for row in rows)
                for rows in data.values()
            )
        ):
            raise D1StorageError("Snapshot D1 invalide")
        return data

    def persist_checkpoint(self, fence, batch):
        changes = [
            {"table": table, "key": list(key), "row": row}
            for (table, key), row in batch.items()
            if not (table == "meta" and key == ("runtime_fence",))
        ]
        result = self.request("persist_checkpoint", fence=fence, changes=changes)
        if result.get("ok") is not True:
            raise D1StorageError("Sauvegarde D1 non confirmée")
