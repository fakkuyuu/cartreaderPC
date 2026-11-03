"""User-facing connection-state decisions, separate from serial transport.

Never classify PermissionError or missing COM ports as 'port busy': powering
off a reader can produce the same Windows errors.
"""


class ConnectionFeedback:
    """Deduplicate retry notices while retaining changing diagnostic details."""

    # These messages are emitted by our own Storage/serve code and identify a
    # host-side write failure. Arbitrary OS/driver exception text is ambiguous.
    _ACTIONABLE_ERRORS = frozenset((
        "fatal host file error; transfer stopped",
        "streamed host file write failed; transfer stopped",
    ))

    def __init__(self):
        self.status = None
        self.last_error = None

    def connected(self):
        """Allow a new waiting notice and diagnostics after recovery."""
        self.status = None
        self.last_error = None

    def failure(self, exc):
        """Return (private status event or None, detail line or None).

        The caller sends status events to the GUI parser, not the visible log;
        the raw exception is shown only when detailed logging is enabled.
        """
        identity = (type(exc).__name__, str(exc))
        detail = None
        if identity != self.last_error:
            detail = f"[Connection detail] {identity[0]}: {identity[1]}\n"
            self.last_error = identity

        wanted = ("ACTION_REQUIRED" if str(exc) in self._ACTIONABLE_ERRORS
                  else "WAIT")
        event = None
        if wanted == "ACTION_REQUIRED" and self.status != "ACTION_REQUIRED":
            self.status = wanted
            event = "[RECONNECT] ACTION_REQUIRED\n"
        elif wanted == "WAIT" and self.status is None:
            self.status = wanted
            event = "[RECONNECT] WAIT\n"
        # Do not downgrade a known, actionable failure to orange just because
        # the automatic retry subsequently raises an ambiguous serial error.
        return event, detail
