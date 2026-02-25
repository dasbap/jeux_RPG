from locust import HttpUser, between, task


class HomePageUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def load_homepage(self) -> None:
        self.client.get("/", name="GET /")
