from pathlib import Path


PROMPT_PATH = Path("automation/weekly_earnings_options_prompt.md")
RUNBOOK_PATH = Path("docs/automation/weekly-earnings-options.md")


def test_weekly_prompt_invokes_the_options_cli_and_never_places_orders():
    prompt = PROMPT_PATH.read_text()

    assert "python -m earnings_export analyze-next-week-options" in prompt
    assert "eligible candidates" in prompt
    assert "data limitations" in prompt
    assert "research rationale" in prompt
    assert "No eligible candidate was found" in prompt
    assert "Do not submit or simulate an order" in prompt


def test_runbook_documents_the_scheduled_research_only_workflow():
    runbook = RUNBOOK_PATH.read_text()

    assert "0 10 * * 5" in runbook
    assert "America/New_York" in runbook
    assert "ALPHAVANTAGE_API_KEY" in runbook
    assert "python -m earnings_export analyze-next-week-options" in runbook
    assert "exports/earnings-options/<YYYY-MM-DD>/earnings_options_research.md" in runbook
    assert "exports/earnings-options/<YYYY-MM-DD>/earnings_options_order_intents.json" in runbook
    assert "exports/earnings-options/<YYYY-MM-DD>/option_chain_snapshots.json" in runbook
    assert "Do not submit or simulate an order" in runbook
    assert "disable" in runbook.lower()
