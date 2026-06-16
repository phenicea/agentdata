"""Web — human-facing surface (landing page).

A minimal, sober HTML landing for humans who hit the root URL: it says what the
service does and links to the machine-readable artifacts (docs, OpenAPI, pricing,
llms.txt). Agents read ``llms.txt`` / OpenAPI; this page is for a person who lands
on the deployment in a browser and needs to orient quickly.

The router is exported here; the integrator mounts it on the FastAPI app
(``app.include_router(landing_router)``). This package does not touch ``app.py``.
"""

from .landing import router as landing_router

__all__ = ["landing_router"]
