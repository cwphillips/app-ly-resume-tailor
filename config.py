"""Single source of truth for the Claude model and its list pricing.

Both agents call the model named here, and the cost estimator in ``app.py``
uses the price constants. Changing the model or its pricing means editing this
file only. When these values change, keep the model/pricing wording in
``README.md`` in sync.
"""

from __future__ import annotations

# Claude model used by the tailoring and review agents.
MODEL_ID = "claude-sonnet-4-6"

# Human-readable name for UI/status text.
MODEL_DISPLAY_NAME = "Claude Sonnet 4.6"

# List pricing, in USD per million tokens.
INPUT_PRICE_PER_M = 3.0
OUTPUT_PRICE_PER_M = 15.0
