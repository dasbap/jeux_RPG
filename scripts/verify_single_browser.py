"""Check the real browser before and after an engine restart, on fictitious D1 only."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import dotenv_values

from scripts.deploy_oracle_test import LOCAL_ENV, ROOT
from scripts.verify_single_preview import cleanup, engine, seed, validate_environment


async def browser(origin, password, playwright, screenshot):
    environment = {
        **os.environ,
        "PLAYWRIGHT_BROWSERS_PATH": str(ROOT / ".data/browser-binaries"),
    }
    process = await asyncio.create_subprocess_exec(
        "node",
        str(ROOT / "scripts/verify_single_browser.cjs"),
        str(playwright),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=environment,
    )
    output, error = await process.communicate(
        json.dumps(
            {"origin": origin, "password": password, "screenshot": str(screenshot)}
        ).encode()
    )
    if process.returncode:
        raise RuntimeError(error.decode(errors="replace"))
    return json.loads(output)


async def verify(environment, playwright):
    validate_environment(environment)
    clients, password = await asyncio.to_thread(seed, environment, 1, 0)
    accounts = {fixture["account"] for fixture in clients}
    report = {}
    try:
        for phase in ("before_restart", "after_restart"):
            async with engine(environment) as (coordinator, origin):
                report[phase] = await browser(
                    origin,
                    password,
                    playwright,
                    ROOT / f".data/oracle-test/browser-{phase}.png",
                )
                await coordinator.flush()
                assert (
                    not coordinator.store.pending
                    and not coordinator.store.last_save_error
                )
        return report
    finally:
        await asyncio.to_thread(cleanup, environment, accounts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=LOCAL_ENV)
    parser.add_argument("--playwright-module", type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(
        verify(dict(dotenv_values(args.env_file)), args.playwright_module)
    )
    (ROOT / ".data/oracle-test/browser-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
