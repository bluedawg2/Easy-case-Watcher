"""Pydantic schema for the AI-generated ChangeSummary structured output.

The NOT_LEGAL_ADVICE_LABEL is a server-side constant — it is NOT a model output
field.  The AI summarizes only the diff content; the disclaimer is attached by
the pipeline (run_summarize) as a server-side annotation on the Change row.
"""

from pydantic import BaseModel, Field

NOT_LEGAL_ADVICE_LABEL = "Informational summary — not legal advice."


class ChangeSummary(BaseModel):
    headline: str = Field(description="One-line headline summarizing the rule change.")
    what_changed: str = Field(
        description="What specifically changed in the rule text (1-3 sentences)."
    )
    where: str = Field(
        description="Which rule, rule number, or form is affected (1-3 sentences)."
    )
    to_whom: str = Field(
        description="Which parties or practitioners this change applies to (1-3 sentences)."
    )
    for_what_cases: str = Field(
        description="Which case types or proceedings this change affects (1-3 sentences)."
    )
