"""
Tests for NodeLifecycleStateMachine.
"""

import pytest
from statemachine.exceptions import TransitionNotAllowed

from core_pkg.nodes_core import NodeLifecycleStateMachine
from core_pkg.systemconstants import NodeStates


def _fresh_sm() -> NodeLifecycleStateMachine:
    return NodeLifecycleStateMachine()


def test_initial_state_is_boot():
    sm = _fresh_sm()
    assert sm.current_state.value == NodeStates.BOOT.value


def test_happy_path_boot_to_idle():
    sm = _fresh_sm()
    sm.boot_complete()
    assert sm.current_state.value == NodeStates.NOT_INITIALIZED.value

    sm.start_initialization()
    assert sm.current_state.value == NodeStates.INITIALIZING.value

    sm.complete()
    assert sm.current_state.value == NodeStates.IDLE.value


def test_operation_cycle():
    sm = _fresh_sm()
    sm.boot_complete()
    sm.start_initialization()
    sm.complete()

    sm.start_operation()
    assert sm.current_state.value == NodeStates.BUSY.value
    sm.complete()
    assert sm.current_state.value == NodeStates.IDLE.value


def test_recoverable_error_can_retry_back_to_idle():
    sm = _fresh_sm()
    sm.boot_complete()
    sm.start_initialization()
    sm.complete()
    sm.start_operation()

    sm.fail_recoverable()
    assert sm.current_state.value == NodeStates.ERROR_RECOVERABLE.value

    sm.retry_from_recoverable()
    assert sm.current_state.value == NodeStates.IDLE.value


def test_non_recoverable_error_blocks_retry():
    sm = _fresh_sm()
    sm.boot_complete()
    sm.start_initialization()
    sm.complete()
    sm.start_operation()

    sm.fail_non_recoverable()
    assert sm.current_state.value == NodeStates.ERROR.value

    # The error state has no retry transition - only cleanup or shutdown should work.
    with pytest.raises(TransitionNotAllowed):
        sm.retry_from_recoverable()


def test_cannot_start_operation_before_initialization():
    sm = _fresh_sm()
    # Skipping init and trying to jump straight into work should fail loudly,
    # not silently move the node into busy.
    with pytest.raises(TransitionNotAllowed):
        sm.start_operation()


def test_shutdown_is_terminal():
    sm = _fresh_sm()
    sm.boot_complete()
    sm.shutdown()
    assert sm.current_state.value == NodeStates.SHUTTING_DOWN.value
    assert sm.current_state.final

    with pytest.raises(TransitionNotAllowed):
        sm.start_initialization()
