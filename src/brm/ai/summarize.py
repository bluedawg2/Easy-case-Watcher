"""AI summarization wrapper for bankruptcy rule change diffs.

Calls the Anthropic Messages API with structured output (output_format=ChangeSummary)
to produce a typed ChangeSummary from a unified diff of rule text.

Design notes:
- Uses client.messages.parse() with output_format= (GA path — no betas= header).
- Parsed result accessed via response.parsed_output.
- SUMMARY_MODEL is exported so run_summarize can record it on the Change row.
- SYSTEM_PROMPT guardrails: no speculation, no advice, 1-3 sentences per field.
"""

import anthropic

from brm.config import settings
from brm.schemas.summary import ChangeSummary

SUMMARY_MODEL = "claude-opus-4-7"

SYSTEM_PROMPT = (
    "You are a legal research assistant summarizing bankruptcy rule amendments. "
    "Summarize ONLY what the diff explicitly states. "
    "Do NOT speculate about practical impact beyond the explicit rule text. "
    "Do NOT phrase any output as advice or recommendation. "
    "Be concise: 1-3 sentences per field."
)


def summarize(diff_text: str) -> ChangeSummary:
    """Call the Anthropic API and return a structured ChangeSummary.

    Args:
        diff_text: Verbatim diff text from a rule snapshot comparison.

    Returns:
        A ChangeSummary with all five structured fields populated by the model.

    Raises:
        anthropic.APIError: On API communication failures.
        anthropic.BadRequestError: If the model rejects the input.
    """
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    user_message = (
        "Below is a verbatim diff of a Federal Rules of Bankruptcy Procedure rulemaking entry. "
        "Summarize it using the structured fields.\n\n"
        "--- DIFF START ---\n"
        f"{diff_text}\n"
        "--- DIFF END ---"
    )
    response = client.messages.parse(
        model=SUMMARY_MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        output_format=ChangeSummary,
    )
    return response.parsed_output
