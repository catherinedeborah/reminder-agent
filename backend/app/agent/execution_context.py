import threading
from typing import List, Dict, Any

_thread_local = threading.local()

def init_context():
    """Initializes the thread-local execution context for the current run."""
    _thread_local.logs = []
    _thread_local.deliveries = []

def add_log(message: str):
    """Appends an execution log message."""
    if not hasattr(_thread_local, "logs"):
        _thread_local.logs = []
    _thread_local.logs.append(message)
    print(f"[Agent Log] {message}")

def add_delivery(channel: str, recipient: str, message: str):
    """Appends a delivery event."""
    if not hasattr(_thread_local, "deliveries"):
        _thread_local.deliveries = []
    _thread_local.deliveries.append({
        "channel": channel,
        "recipient": recipient,
        "message": message
    })
    add_log(f"Delivered notification to {recipient} via {channel}.")

def get_logs() -> List[str]:
    """Returns all log messages for the current thread."""
    return getattr(_thread_local, "logs", [])

def get_deliveries() -> List[Dict[str, Any]]:
    """Returns all deliveries made during the current thread."""
    return getattr(_thread_local, "deliveries", [])
