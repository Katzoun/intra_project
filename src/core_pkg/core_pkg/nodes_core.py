import threading
import time
from typing import Optional, List
from functools import wraps
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.client import Client
from abc import ABC, abstractmethod
from rclpy.node import Node

from statemachine import StateMachine, State
from statemachine.exceptions import TransitionNotAllowed

from core_pkg.systemconstants import (
    NodeStates,
    GeneralNodeConstants,
    CALL_TIMEOUT_SEC,
)
from core_pkg.exceptions import NodeExceptionRecoverable, NodeExceptionNonRecoverable, ServiceCallException

from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue

from interface_pkg.srv import (
    NodeStateSrv,
    TriggerServiceSrv,
)

EXPORT_STATE_MACHINE_DIAGRAM = False


def handle_operation_errors(func):
    """Decorator for service callbacks — catches exceptions, sets response status,
    and triggers the appropriate state machine transition.
    The wrapped callback does not need to return the response."""
    @wraps(func)
    def wrapper(self, request, response):
        try:
            func(self, request, response)  # Call function, ignore return value
            
        except TransitionNotAllowed as e:
            response.status = False
            response.message = f"Invalid state: {str(e)}"
            self.logger.error(response.message)
            
        except NodeExceptionRecoverable as e:
            response.status = False
            response.message = f"Recoverable error: {str(e)}"
            with self.sm_lock:
                self.lifecycle_sm.fail_recoverable(message=response.message)
        
        except NodeExceptionNonRecoverable as e:
            response.status = False
            response.message = f"Non-recoverable error: {str(e)}"
            with self.sm_lock:
                self.lifecycle_sm.fail_non_recoverable(message=response.message)
        
        except Exception as e:
            response.status = False
            response.message = f"Unexpected error: {str(e)}"
            self.logger.error(response.message)
            with self.sm_lock:
                self.lifecycle_sm.fail_non_recoverable(message=response.message)
        
        return response
    
    return wrapper


class NodeLifecycleStateMachine(StateMachine):
    """
    State machine for node lifecycle management.
    Enforces valid state transitions and provides lifecycle hooks.
    """
    
    # States
    boot = State(initial=True, value=NodeStates.BOOT.value)
    not_initialized = State(value=NodeStates.NOT_INITIALIZED.value)
    initializing = State(value=NodeStates.INITIALIZING.value)
    idle = State(value=NodeStates.IDLE.value)
    busy = State(value=NodeStates.BUSY.value)
    error = State(value=NodeStates.ERROR.value)
    error_recoverable = State(value=NodeStates.ERROR_RECOVERABLE.value)
    cleaning_up = State(value=NodeStates.CLEANING_UP.value)
    shutting_down = State(final=True, value=NodeStates.SHUTTING_DOWN.value)
    
    # Transitions
    
    # Lifecycle flow
    boot_complete = boot.to(not_initialized)
    start_initialization = not_initialized.to(initializing)
    start_operation = idle.to(busy)
    
    # Success transitions
    complete = (
        initializing.to(idle) |      # initialization complete
        busy.to(idle) |               # operation complete
        cleaning_up.to(not_initialized)  # cleanup complete
    )
    
    # Error transitions - generic, work from any operational state
    fail_recoverable = (
        initializing.to(error_recoverable) |
        busy.to(error_recoverable) |
        cleaning_up.to(error_recoverable)
    )
    
    fail_non_recoverable = (
        initializing.to(error) |
        busy.to(error) |
        cleaning_up.to(error)
    )
    
    # Cleanup transition - can be called from multiple states
    start_cleanup = (
        idle.to(cleaning_up) |
        error.to(cleaning_up) |
        error_recoverable.to(cleaning_up)
    )
    
    # Recovery transition
    retry_from_recoverable = error_recoverable.to(idle)
    
    # Shutdown - can happen from almost anywhere
    shutdown = (
        not_initialized.to(shutting_down) |
        idle.to(shutting_down) |
        error.to(shutting_down) |
        error_recoverable.to(shutting_down)
    )
    
    # Lifecycle hooks
    def on_enter_state(self, state, event: str = None, **kwargs):
        """Called when entering any state"""
        if hasattr(self.model, '_on_state_enter'):
            message = kwargs.get('message', '')
            self.model._on_state_enter(state.id, event, message)
    
    def on_exit_state(self, state, event: str = None, **kwargs):
        """Called when exiting any state"""
        if hasattr(self.model, '_on_state_exit'):
            self.model._on_state_exit(state.id, event)

class INTRANode(Node, ABC):
    """
    Base node class with integrated state machine.
    All nodes inherit from this and get lifecycle management automatically.
    """

    node_state: NodeStates = NodeStates.BOOT
    node_state_description: str = "Node booting up"

    def __init__(self, NODE_NAME: str):
        self.NODE_NAME = NODE_NAME
        super().__init__(self.NODE_NAME)
        self.logger = self.get_logger()
        self.cb_group = ReentrantCallbackGroup()
        
        # State tracking - must be initialized before state machine
        self._last_transition_event: Optional[str] = None
        self._last_transition_message: str = ""
        
        # State machine
        self.lifecycle_sm = NodeLifecycleStateMachine(model=self)
        self.sm_lock = threading.Lock()

        # this is useful for visualizing the state machine
        if EXPORT_STATE_MACHINE_DIAGRAM:
            from statemachine.contrib.diagram import DotGraphMachine
            self.diagram = DotGraphMachine(self.lifecycle_sm)
            self.diagram().write_svg(f"{self.NODE_NAME}_state_machine.svg")

        # Declare common services
        self._state_service = self.create_service(
            NodeStateSrv,
            f"{self.NODE_NAME}/{GeneralNodeConstants.ServiceNames.GET_STATE}",
            self.get_state_cb,
            callback_group=self.cb_group,
        )

        self._apply_parameters_service = self.create_service(
            TriggerServiceSrv,
            f"{self.NODE_NAME}/{GeneralNodeConstants.ServiceNames.APPLY_PARAMETERS}",
            self.apply_parameters_cb,
            callback_group=self.cb_group,
        )

        self._initialize_node_service = self.create_service(
            TriggerServiceSrv,
            f"{self.NODE_NAME}/{GeneralNodeConstants.ServiceNames.INITIALIZE_NODE}",
            self.initialize_node_cb,
            callback_group=self.cb_group,
        )

        self._cleanup_service = self.create_service(
            TriggerServiceSrv,
            f"{self.NODE_NAME}/{GeneralNodeConstants.ServiceNames.CLEANUP_RESOURCES}",
            self.cleanup_resources_cb,
            callback_group=self.cb_group,
        )

        self._recover_service = self.create_service(
            TriggerServiceSrv,
            f"{self.NODE_NAME}/{GeneralNodeConstants.ServiceNames.RECOVER_FROM_ERROR}",
            self.recover_from_error_cb,
            callback_group=self.cb_group,
        )

        # parameter service is created by default in rclpy node

    def call_service_sync(self, client: Client, request, timeout_sec=CALL_TIMEOUT_SEC):
        """
        Synchronous service call safe for worker threads.

        Uses call_async() + busy-wait to avoid the classic ROS 2 deadlock
        that occurs when call() blocks an executor thread inside a callback.
        Requires MultiThreadedExecutor with enough free threads to process
        the response while this thread is spinning.
        """
        future = None
        try:
            future = client.call_async(request)
            start = time.monotonic()
            while not future.done():
                if time.monotonic() - start > timeout_sec:
                    client.remove_pending_request(future)
                    raise ServiceCallException(f"Service call timed out after {timeout_sec}s")
                time.sleep(0.01)
            return future.result()
        except ServiceCallException:
            raise
        except Exception as e:
            if future is not None and not future.done():
                client.remove_pending_request(future)
            self.logger.error(f"Service call failed for {client.srv_name}: {e}")
            raise NodeExceptionRecoverable(f"Service call failed: {e}") from e

    def _on_state_enter(self, state_id: str, event: str, message: str = ""):
        """Called when entering any state - logs the transition and updates internal tracking"""
        self._last_transition_event = event
        self._last_transition_message = message
        
        if state_id in [NodeStates.ERROR.value, NodeStates.ERROR_RECOVERABLE.value]:
            self.logger.error(f"State transition: {event} -> {state_id}: {message}")
        else:
            self.logger.info(f"State transition: {event} -> {state_id}: {message}")
    
    def _on_state_exit(self, state_id: str, event: str):
        """Called when exiting any state"""
        if state_id in [NodeStates.ERROR.value, NodeStates.ERROR_RECOVERABLE.value]:
            self.logger.info(f"Recovering from {state_id} state via {event}")
    
    @property
    def current_state(self) -> NodeStates:
        """Get current state as NodeStates enum"""
        return NodeStates(self.lifecycle_sm.current_state.value)
    
    @property
    def state_message(self) -> str:
        """Get message from last transition"""
        return self._last_transition_message
    
    @property
    def is_error_state(self) -> bool:
        """Check if current state is error"""
        return self.current_state in [NodeStates.ERROR, NodeStates.ERROR_RECOVERABLE]
    
    @property
    def is_recoverable_error(self) -> bool:
        """Check if current state is recoverable error"""
        return self.current_state == NodeStates.ERROR_RECOVERABLE

    def get_state_cb(self, request, response: NodeStateSrv.Response):
        """Get current state"""
        self.logger.info("Get state service called")
        response.state = self.current_state.value
        response.description = self.state_message
        return response
    
    def cleanup_resources_cb(self, request, response: TriggerServiceSrv.Response):
        """Handle cleanup resources service call"""
        try:
            with self.sm_lock:
                self.lifecycle_sm.start_cleanup(
                    message=f"Starting cleanup of {self.NODE_NAME} resources"
                )
            
            self.cleanup_resources()
            
            response.status = True
            response.message = f"{self.NODE_NAME} resources cleaned up successfully"
            
            with self.sm_lock:
                self.lifecycle_sm.complete(
                    message=response.message
                )
            
        except TransitionNotAllowed as e:
            response.status = False
            response.message = f"Invalid state for cleanup: {str(e)}"
            self.logger.error(response.message)

        except NodeExceptionRecoverable as e:
            response.status = False
            response.message = f"Recoverable error during cleanup: {str(e)}"
            self.logger.warning(response.message)
            with self.sm_lock:
                self.lifecycle_sm.fail_recoverable(
                    message=response.message
                )
        except NodeExceptionNonRecoverable as e:
            response.status = False
            response.message = f"Non-recoverable error during cleanup: {str(e)}"
            self.logger.error(response.message)
            with self.sm_lock:
                self.lifecycle_sm.fail_non_recoverable(
                    message=response.message
                )
            
        return response
    
    def apply_parameters_cb(self, request, response: TriggerServiceSrv.Response):
        """Handle apply parameters service call"""
        try:
            
            self.apply_parameters()
            
            response.status = True
            response.message = "Parameters applied successfully, some parameters may require re-initialization to take effect"
            
        except Exception as e:
            response.status = False
            response.message = f"error during parameter application: {str(e)}"
            self.logger.error(response.message)
        return response
    
    def initialize_node_cb(self, request, response: TriggerServiceSrv.Response):
        """Handle initialize node call"""
        try:
            with self.sm_lock:
                self.lifecycle_sm.start_initialization(
                    message=f"Initializing node {self.NODE_NAME}"
                )
            
            self.initialize_node()
            msg = f"Node {self.NODE_NAME} initialized successfully"
            response.status = True
            response.message = msg
            
            with self.sm_lock:
                self.lifecycle_sm.complete(
                    message=msg
                )
            
        except TransitionNotAllowed as e:
            response.status = False
            response.message = f"Invalid state for initialization: {str(e)}"
            self.logger.error(response.message)

        except NodeExceptionRecoverable as e:
            response.status = False
            response.message = f"Recoverable error during initialization: {str(e)}"
            self.logger.warning(response.message)
            with self.sm_lock:
                self.lifecycle_sm.fail_recoverable(
                    message=response.message
                )
        except Exception as e:
            # Unknown exceptions are treated as non-recoverable
            response.status = False
            response.message = f"Non-recoverable error during initialization: {str(e)}"
            self.logger.error(response.message)
            with self.sm_lock:
                self.lifecycle_sm.fail_non_recoverable(
                    message=response.message
                )

        return response

    def recover_from_error_cb(self, request, response: TriggerServiceSrv.Response):
        """Handle recover from error service call"""
        try:
            with self.sm_lock:
                if self.is_recoverable_error:
                    self.lifecycle_sm.retry_from_recoverable(
                        message=f"Recovering {self.NODE_NAME} from recoverable error"
                    )
                    response.status = True
                    response.message = f"{self.NODE_NAME} recovered from error successfully"
                else:
                    response.status = False
                    response.message = f"{self.NODE_NAME} is not in a recoverable error state"
                    self.logger.error(response.message)
        except TransitionNotAllowed as e:
            response.status = False
            response.message = f"Invalid state for recovery: {str(e)}"
            self.logger.error(response.message)
        except Exception as e:
            response.status = False
            response.message = f"Error during recovery: {str(e)}"
            self.logger.error(response.message)
        return response

    @abstractmethod
    def apply_parameters(self):
        """
        Abstract method for applying parameters.
        Child classes must implement this method to handle parameter updates.
        """
        pass

    @abstractmethod
    def initialize_node(self):
        """
        Abstract method for node initialization.
        Child classes must implement this to initialize their specific node.
        """
        pass

    @abstractmethod
    def cleanup_resources(self):
        """
        Abstract method for resource cleanup.
        Child classes must implement this to clean up their specific resources.
        """
        pass