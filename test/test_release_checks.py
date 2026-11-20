import io
import json

import pytest

from scripts import verify_release_checks as gate


def checks():
    return [dict(id=index, name=name, app={"id": 15368},
                 status="completed", conclusion="success")
            for index, name in enumerate(gate.REQUIRED, 1)]


def test_exact_commit_requires_all_checks_from_github_actions():
    runs = checks()
    assert gate.check_state(runs) == ([], [])
    runs[-1]["app"]["id"] = 123
    assert gate.check_state(runs) == (["d1-worker"], [])
    runs[-1].update(app={"id": 15368}, status="in_progress")
    assert gate.check_state(runs) == (["d1-worker"], [])


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out", "skipped", "neutral", None])
def test_any_unsuccessful_required_check_prevents_release(conclusion):
    runs = checks()
    runs[0]["conclusion"] = conclusion
    with pytest.raises(RuntimeError, match="tests "):
        gate.wait_for_checks(lambda: runs, sleep=lambda _: pytest.fail("Should fail immediately"))


def test_rerun_must_finish_before_older_success_is_accepted():
    runs = checks()
    rerun = {**runs[0], "id": 100, "status": "queued", "conclusion": None}
    assert gate.check_state([rerun, *runs]) == (["tests (3.11)"], [])
    rerun.update(status="completed", conclusion="success")
    runs[0]["conclusion"] = "failure"
    assert gate.check_state([rerun, *runs]) == ([], [])


def test_waits_for_missing_checks_and_times_out_without_releasing():
    times = iter([0, 0, 16])
    with pytest.raises(RuntimeError, match="absents ou inacheves"):
        gate.wait_for_checks(lambda: [], timeout=15, clock=lambda: next(times), sleep=lambda _: None)
    batches = iter([[], checks()])
    gate.wait_for_checks(lambda: next(batches), sleep=lambda _: None)


def test_api_paginates_checks_and_uses_exact_sha(monkeypatch):
    urls = []

    def fetch(request, **kwargs):
        urls.append(request.full_url)
        assert request.get_header("Authorization") == "Bearer private"
        batch = [{"name": "unrelated"}] * 100 if len(urls) == 1 else checks()
        return io.BytesIO(json.dumps({"check_runs": batch}).encode())

    monkeypatch.setattr(gate, "urlopen", fetch)
    result = gate.fetch_checks("dasbap/jeux_RPG", "a" * 40, "private")
    assert len(result) == 109
    assert gate.check_state(result) == ([], [])
    assert all("/commits/" + "a" * 40 + "/check-runs?" in url for url in urls)
    assert urls[1].endswith("page=2")
