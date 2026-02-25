from locust import HttpUser, between, task


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


class FormSubmissionUser(HttpUser):
    wait_time = between(2, 4)

    @task
    def submit_form_payload(self) -> None:
        with self.client.post(
            "/formulaire",
            params={"param1": "texte"},
            name="POST /formulaire",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201, 204, 400, 404, 405, 501):
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
