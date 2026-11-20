"""Wait for successful GitHub Actions checks on the exact production commit."""

import json
import os
import re
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

REQUIRED = (
    "tests (3.11)",
    "tests (3.12)",
    "tests (3.13)",
    "builder",
    "ui",
    "lint",
    "package",
    "benchmark",
    "d1-worker",
)


def check_state(checks):
    latest = {}
    for check in checks:
        name = check.get("name")
        if name not in REQUIRED or check.get("app", {}).get("id") != 15368:
            continue
        if name not in latest or check["id"] > latest[name]["id"]:
            latest[name] = check
    pending, failed = [], []
    for name in REQUIRED:
        check = latest.get(name)
        if not check or check.get("status") != "completed":
            pending.append(name)
        elif check.get("conclusion") != "success":
            failed.append(name)
    return pending, failed


def fetch_checks(repository, sha, token):
    checks = []
    for page in range(1, 11):
        url = (
            f"https://api.github.com/repos/{repository}/commits/{sha}/check-runs"
            f"?filter=latest&per_page=100&page={page}"
        )
        request = Request(
            url,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urlopen(request, timeout=30) as response:
            batch = json.load(response)["check_runs"]
        checks.extend(batch)
        if len(batch) < 100:
            return checks
    raise RuntimeError("Trop de controles sur le commit ; publication refusee.")


def wait_for_checks(fetch, timeout=960, clock=time.monotonic, sleep=time.sleep):
    deadline = clock() + timeout
    while True:
        pending, failed = check_state(fetch())
        if failed:
            raise RuntimeError(
                "Controles CI en echec ; publication refusee : " + ", ".join(failed)
            )
        if not pending:
            print("Tous les controles CI du commit exact sont valides.")
            return
        if clock() >= deadline:
            raise RuntimeError(
                "Controles CI absents ou inacheves : " + ", ".join(pending)
            )
        print("Attente des controles CI : " + ", ".join(pending), flush=True)
        sleep(15)


def main():
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("GITHUB_SHA", "")
    token = os.environ.get("GH_TOKEN", "")
    if not (
        re.fullmatch(r"[\w.-]+/[\w.-]+", repository)
        and re.fullmatch(r"[0-9a-f]{40}", sha)
        and token
    ):
        print("Configuration du controle CI absente ou invalide.")
        return 1
    try:
        wait_for_checks(lambda: fetch_checks(repository, sha, token))
    except (URLError, ValueError, KeyError):
        print("Lecture des controles GitHub impossible ; publication refusee.")
        return 1
    except RuntimeError as error:
        print(str(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
