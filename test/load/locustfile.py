from locust import HttpUser, between, task
import json


class ProjectPagesUser(HttpUser):
    wait_time = between(1, 2)

    @task(5)
    def load_homepage(self) -> None:
        self.client.get("/", name="GET /")

    @task(3)
    def load_readme(self) -> None:
        self.client.get("/README.md", name="GET /README.md")

    @task(2)
    def load_requirements(self) -> None:
        self.client.get("/requirements.txt", name="GET /requirements.txt")

    @task(2)
    def load_tests_dir(self) -> None:
        self.client.get("/test/", name="GET /test/")

    @task(2)
    def load_docs_index(self) -> None:
        self.client.get("/__doc__/README.md", name="GET /__doc__/README.md")

    @task(1)
    def load_docs_tree(self) -> None:
        self.client.get("/__doc__/TREE.md", name="GET /__doc__/TREE.md")


class ApiUser(HttpUser):
    wait_time = between(1, 2)

    @task(3)
    def bot_status(self):
        self.client.get("/api/bot/status", name="GET /api/bot/status")

    @task(1)
    def bot_start(self):
        # endpoint may return 400 if control unavailable
        with self.client.post("/api/bot/start", name="POST /api/bot/start", catch_response=True) as r:
            if r.status_code in (200, 201, 202, 400, 500):
                r.success()
            else:
                r.failure(f"Unexpected status code: {r.status_code}")

    @task(1)
    def bot_stop(self):
        with self.client.post("/api/bot/stop", name="POST /api/bot/stop", catch_response=True) as r:
            if r.status_code in (200, 201, 202, 400, 500):
                r.success()
            else:
                r.failure(f"Unexpected status code: {r.status_code}")

    # bot_restart removed: avoid restart endpoints during load tests

    # server_restart removed: calling /api/server/restart during a load test
    # would restart the application and cause transient failures. If you
    # need to test restart behavior, run a separate, dedicated scenario.

    @task(2)
    def map_status(self):
        # Map endpoints expect local requests; test against localhost
        self.client.get("/api/map_builder/status", name="GET /api/map_builder/status")

    @task(1)
    def map_builder_ui(self):
        self.client.get("/map-builder", name="GET /map-builder")

    @task(1)
    def logs_page(self):
        self.client.get("/logs", name="GET /logs")

    @task(1)
    def logs_raw(self):
        self.client.get("/logs/raw?lines=100", name="GET /logs/raw")

    @task(1)
    def map_get_example(self):
        # request an example map file if present
        self.client.get("/api/map_builder/maps/map_1770132575.json", name="GET /api/map_builder/maps/<file>")

    @task(1)
    def map_list(self):
        self.client.get("/api/map_builder/maps", name="GET /api/map_builder/maps")

    @task(1)
    def map_publish(self):
        payload = {"name": "test-map", "data": {"cells": []}}
        with self.client.post(
            "/api/map_builder/publish",
            json=payload,
            name="POST /api/map_builder/publish",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 201, 400, 403, 500):
                r.success()
            else:
                r.failure(f"Unexpected status code: {r.status_code}")
