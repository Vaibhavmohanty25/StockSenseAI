import json
import logging
import traceback
from datetime import UTC, datetime
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """Emit allowlisted structured context, excluding payloads and credentials."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "run_id",
            "provider",
            "symbol",
            "exchange",
            "start",
            "end",
            "rows_received",
            "rows_inserted",
            "rows_updated",
            "rows_failed",
            "rows_normalized",
            "rows_rejected",
            "duration",
            "status",
            "error_type",
            "candidate_date",
            "report_source",
            "request_url",
            "final_url",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception_type"] = record.exc_info[0].__name__
            payload["frames"] = [
                {
                    "file": Path(frame.filename).name,
                    "line": frame.lineno,
                    "function": frame.name,
                }
                for frame in traceback.extract_tb(record.exc_info[2])
            ]
        return json.dumps(payload, default=str)
