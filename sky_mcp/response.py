from __future__ import annotations

from typing import Any, Dict, Optional

ALLOWED_ERROR_TYPES = {
    "missing_env",
    "file_not_found",
    "invalid_input",
    "permission_denied",
    "file_too_large",
    "mp_api_error",
    "upstream_timeout",
    "upstream_rate_limited",
    "runtime_error",
}


def _envelope(
    ok: bool,
    data: Any,
    error: Optional[Dict[str, Any]],
    meta: Optional[Dict[str, Any]],
    provenance: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "ok": ok,
        "data": data,
        "error": error,
        "meta": meta or {},
        "provenance": provenance or {},
    }


def validate_envelope(resp: Dict[str, Any], strict: bool = False) -> Dict[str, Any]:
    try:
        assert isinstance(resp, dict), "Envelope must be a dict."
        assert "ok" in resp, "Envelope missing ok."
        assert "data" in resp, "Envelope missing data."
        assert "error" in resp, "Envelope missing error."
        assert "meta" in resp, "Envelope missing meta."
        assert "provenance" in resp, "Envelope missing provenance."
        assert isinstance(resp["meta"], dict), "meta must be dict."
        assert isinstance(resp["provenance"], dict), "provenance must be dict."
        if resp["ok"] is True:
            assert resp["error"] is None, "ok True requires error=None."
        else:
            assert resp["data"] is None, "ok False requires data=None."
            assert isinstance(resp["error"], dict), "error must be dict."
            for key in ("type", "message", "details"):
                assert key in resp["error"], f"error missing {key}."
            err_type = resp["error"]["type"]
            assert err_type in ALLOWED_ERROR_TYPES, f"Invalid error.type: {err_type}"
        return resp
    except AssertionError as exc:
        if strict:
            raise
        return _envelope(
            False,
            None,
            {
                "type": "runtime_error",
                "message": "Envelope validation failed.",
                "details": str(exc),
            },
            meta={},
            provenance={},
        )


def make_ok(
    data: Any,
    meta: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    resp = _envelope(True, data, None, meta, provenance)
    return validate_envelope(resp, strict=False)


def make_err(
    error_type: str,
    message: str,
    details: Any = None,
    meta: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    resp = _envelope(
        False,
        None,
        {"type": error_type, "message": message, "details": details},
        meta,
        provenance,
    )
    return validate_envelope(resp, strict=False)
