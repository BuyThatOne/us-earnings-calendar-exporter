import re
from pathlib import Path


PROMPT_PATH = Path("automation/weekly_earnings_options_prompt.md")
RUNBOOK_PATH = Path("docs/automation/weekly-earnings-options.md")
LOCAL_CREDENTIALS_PATH = Path("docs/automation/local-credentials.md")
PROJECT_ROOT = "/Users/yongningzhang/Documents/earnings"


def _normalized(text: str) -> str:
    return " ".join(text.lower().split())


def _assert_no_credential_assignment(text: str) -> None:
    # Permit mentions of the variable, but never document a value assignment.
    assignment = re.compile(r"(?im)\b(?:export\s+)?ALPHAVANTAGE_API_KEY\s*[:=]")
    assert not assignment.search(text), "documentation must not contain an API key assignment"


def test_weekly_prompt_invokes_the_options_cli_and_never_places_orders():
    prompt = PROMPT_PATH.read_text()
    normalized_prompt = _normalized(prompt)

    assert "PYTHONPATH=src python3 -m earnings_export analyze-next-week-options" in prompt
    assert "eligible candidates" in prompt
    assert "data limitations" in prompt
    assert "research rationale" in prompt
    assert "No eligible candidate was found" in prompt
    assert "Do not submit or simulate an order" in prompt
    assert "research only" in normalized_prompt
    assert re.search(r"do not (?:submit|place|simulate).*?(?:order|trade)", normalized_prompt)
    _assert_no_credential_assignment(prompt)


def test_runbook_documents_the_scheduled_research_only_workflow():
    runbook = RUNBOOK_PATH.read_text()
    normalized_runbook = _normalized(runbook)

    assert "0 10 * * 5" in runbook
    assert "America/New_York" in runbook
    assert "ALPHAVANTAGE_API_KEY" in runbook
    assert "PYTHONPATH=src python3 -m earnings_export analyze-next-week-options" in runbook
    assert "exports/earnings-options/<YYYY-MM-DD>/earnings_options_research.md" in runbook
    assert "exports/earnings-options/<YYYY-MM-DD>/earnings_options_order_intents.json" in runbook
    assert "exports/earnings-options/<YYYY-MM-DD>/option_chain_snapshots.json" in runbook
    assert "Do not submit or simulate an order" in runbook
    assert "automation/weekly_earnings_options_prompt.md" in runbook
    assert "versioned prompt" in normalized_runbook
    assert f"working_directory: {PROJECT_ROOT}" in runbook
    assert "environment configuration" in normalized_runbook
    assert re.search(
        r"alphavantage_api_key.{0,160}(?:environment|env)"
        r"|(?:environment|env).{0,160}alphavantage_api_key",
        normalized_runbook,
    )
    _assert_no_credential_assignment(runbook)
    assert "candidate array is empty" in normalized_runbook
    assert "no eligible candidate was found" in normalized_runbook
    assert re.search(r"do not (?:submit|place|simulate).*?(?:order|trade)", normalized_runbook)
    assert "command exits nonzero" in normalized_runbook
    assert "expected artifact is missing" in normalized_runbook
    assert "report the failure" in normalized_runbook
    assert "do not fabricate a summary" in normalized_runbook
    assert "disable or delete the project-level cron schedule" in normalized_runbook
    assert "leave the versioned prompt and this runbook in place" in normalized_runbook
    assert "re-enable it only after restoring" in normalized_runbook


def test_local_credentials_doc_covers_secure_setup_contract():
    documentation = LOCAL_CREDENTIALS_PATH.read_text()
    normalized_documentation = _normalized(documentation)

    assert "~/.config/earnings-options-research/credentials.env" in documentation
    assert "PYTHONPATH=src python3 -m earnings_export init-local-credentials" in documentation
    assert "prints only the file path" in normalized_documentation
    assert "does not accept a key argument" in normalized_documentation
    assert "does not accept extra arguments" in normalized_documentation
    assert "write key material" in normalized_documentation
    assert "owner-only mode `0600`" in documentation
    assert "owner-only mode `0700`" in documentation
    assert "open the file in a local text editor" in normalized_documentation
    assert "alphavantage_api_key" in normalized_documentation
    assert re.search(
        r"environment.{0,120}preference to the file"
        r"|preference to the file.{0,120}environment",
        normalized_documentation,
    )
    assert "weekly local codex task uses the same loader" in normalized_documentation
    for prohibited_location in (
        "shell command",
        "shell history",
        "this repository",
        "logs",
        "prompts",
        "generated artifacts",
    ):
        assert prohibited_location in normalized_documentation
    assert "rejects a file readable by group or others" in normalized_documentation
    assert "non-posix" in normalized_documentation
    assert "refuses to read any existing credentials path" in normalized_documentation
    assert "refuses to modify one" in normalized_documentation
    assert "genuinely absent empty file with an exclusive create" in normalized_documentation
    assert "cannot be loaded by this application on non-posix systems" in normalized_documentation
    _assert_no_credential_assignment(documentation)
