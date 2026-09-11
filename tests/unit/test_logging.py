import json
import logging
import sys

from apps.core.logging import JSONFormatter


def test_exception_logs_include_origin_without_sensitive_message():
    try:
        raise ValueError("secret-in-vendor-url")
    except ValueError:
        record = logging.LogRecord(
            "application",
            logging.ERROR,
            __file__,
            12,
            "request_failed",
            (),
            sys.exc_info(),
        )
    payload = json.loads(JSONFormatter().format(record))
    assert payload["exception_type"] == "ValueError"
    assert (
        payload["frames"][-1]["function"]
        == "test_exception_logs_include_origin_without_sensitive_message"
    )
    assert "secret-in-vendor-url" not in json.dumps(payload)
