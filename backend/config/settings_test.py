"""Settings for the test suite: independent of the developer's local .env.

Throttle rates are the production defaults (tests assert on them) and the AI provider is never the
real Anthropic client, so a key in .env cannot make tests spend money.
"""

from .settings import *  # noqa: F401,F403
from .settings import REST_FRAMEWORK, THROTTLE_DEFAULTS

REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": dict(THROTTLE_DEFAULTS)}
AI_PROVIDER = "demo"
ANTHROPIC_API_KEY = ""
GEMINI_API_KEY = ""
