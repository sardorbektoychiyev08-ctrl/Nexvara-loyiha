"""NEXVARA keeps serving the phone with its window closed; a second start shows the window."""

from __future__ import annotations

import threading

from nexvara.app import background


def test_second_start_shows_the_running_window():
    shown = threading.Event()
    first = background.claim_single_instance(shown.set, port=0)  # port 0: a free test port
    assert first is not None
    port = first.getsockname()[1]
    try:
        assert background.claim_single_instance(lambda: None, port=port) is None
        assert shown.wait(5)  # the first copy was asked to show its window
    finally:
        first.close()


def test_keep_running_only_with_phone_access():
    assert background.keep_running({"remote": {"enabled": True}})
    assert not background.keep_running({"remote": {"enabled": False}})
    assert not background.keep_running({})


def test_autostart_command_starts_in_background():
    from nexvara import pcpower

    assert pcpower._command().endswith("--background")
