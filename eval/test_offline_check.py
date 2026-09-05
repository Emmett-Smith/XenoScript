import socket

import pytest

from eval.offline_check import NetworkCallDetected, run_offline_task_and_assert_no_network


def test_offline_task_run_makes_zero_outbound_connections():
    run_offline_task_and_assert_no_network()  # raises on any non-loopback connect


def test_guard_actually_detects_a_violation():
    """Proves the guard isn't a no-op: a deliberate non-loopback connect
    attempt during the guarded window must raise."""
    from eval.offline_check import _guarded_connect

    real_connect = socket.socket.connect
    guarded = _guarded_connect(real_connect)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkCallDetected):
            guarded(s, ("8.8.8.8", 53))
    finally:
        s.close()
