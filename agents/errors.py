"""Typed errors shared by the tailoring and review agents."""

from __future__ import annotations


class MalformedModelOutputError(RuntimeError):
    """The model returned a structurally-valid tool call whose fields failed
    schema validation.

    Distinct from an API/auth/rate-limit failure: the request succeeded, but
    the payload did not match the expected resume/review schema. Surfaced to
    the user as a "try again" message rather than a generic "Unexpected error".
    """
