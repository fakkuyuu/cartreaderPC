"""SD browser-specific 2M negotiation and progress; ROM profiles are unchanged."""
import time


def browser_transfer_allowed(store, entry, length, total):
    request = store.host_state.get("browser_request")
    if not request or request.get("action") != "C" or not entry or not entry.get("write"):
        return False
    return (8192 <= length <= 128 * 1024**2 and length % 512 == 0
            and 0 <= total - length < 512
            and entry["path"] == store.path(request["path"].encode("utf-8")))


def browser_progress(log, total):
    last = 0.0

    def report(done):
        nonlocal last
        now = time.monotonic()
        if done == total or now - last >= 1.0:
            log(f"[SD Progress]\t{done}\t{total}\n")
            last = now
    return report
