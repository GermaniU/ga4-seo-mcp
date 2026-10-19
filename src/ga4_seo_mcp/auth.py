"""Google credentials with explicit scopes."""

from __future__ import annotations

import google.auth


def credentials(*scopes: str):
    """ADC (user login or GOOGLE_APPLICATION_CREDENTIALS service account) with these scopes.

    Service accounts are scoped to exactly what is asked. User credentials keep the scopes that
    were consented at `gcloud auth application-default login` time.
    """
    creds, _ = google.auth.default(scopes=list(scopes))
    return creds
