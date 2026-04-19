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


import io
from PIL import Image as PILImage
from fastapi.testclient import TestClient


def _fake_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", (10, 10), color=(255, 0, 0)).save(buf, format="JPEG")
    return buf.getvalue()


def test_predict_is_rate_limited():
    """Verify the /predict endpoint has a rate limit decorator active.

    We test this by checking the endpoint function has been wrapped by slowapi
    (i.e. it has a __wrapped__ attribute), which confirms @limiter.limit was applied.
    """
    from src.api.routes.inference import predict
    assert hasattr(predict, "__wrapped__"), (
        "/predict must be decorated with @limiter.limit — it lacks __wrapped__"
    )


def test_stream_endpoints_are_rate_limited():
    from src.api.routes.stream import detect_video, live_webcam_frame
    assert hasattr(detect_video, "__wrapped__"), "/api/detect_video must be rate-limited"
    assert hasattr(live_webcam_frame, "__wrapped__"), "/api/live/webcam/frame must be rate-limited"
