"""Verify rate limiter is wired into the FastAPI app."""
from slowapi.errors import RateLimitExceeded


def test_limiter_registered_on_app():
    from src.api.main import app
    assert hasattr(app.state, "limiter"), "app.state.limiter must be set"


def test_rate_limit_exception_handler_registered():
    from src.api.main import app
    assert RateLimitExceeded in app.exception_handlers, (
        "RateLimitExceeded handler must be registered so FastAPI returns 429"
    )
