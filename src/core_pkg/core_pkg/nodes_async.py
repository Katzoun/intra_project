"""Async extension of INTRANode for the frontend node.
Wraps ROS2 service calls so they can be awaited from NiceGUI handlers."""

import asyncio
from typing import Any, Optional
from rclpy.client import Client
from core_pkg.exceptions import ServiceCallException
from core_pkg.nodes_core import INTRANode

from interface_pkg.srv import (
    NodeStateSrv,
    ScanAcquisitionSrv,
    RobotRequestSrv,
    TriggerServiceSrv,
)
from rcl_interfaces.srv import SetParameters, GetParameters 
from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue

from typing import List

class AsyncINTRANode(INTRANode):
    """INTRANode with async service call wrappers for NiceGUI handlers."""

    async def call_service_async(
        self, 
        client: Client, 
        request: Any,
        timeout_sec: float = 5.0
    ) -> Any:
        """Async wrapper for ROS2 service calls with timeout."""
        future = None
        try:
            future = client.call_async(request)
            
            # Non-blocking wait for response with timeout
            start_time = asyncio.get_event_loop().time()
            while not future.done():
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout_sec:
                    # Remove pending request from ROS2 client
                    client.remove_pending_request(future)
                    raise ServiceCallException(f"Service call timed out after {timeout_sec}s")
                await asyncio.sleep(0.01)
            
            return future.result()
            
        except Exception as e:
            # Remove pending request on any exception if it's still pending
            if future is not None and not future.done():
                client.remove_pending_request(future)
            self.logger.error(f"Service call failed for {client.srv_name}: {e}")
            raise ServiceCallException(f"Service call failed: {e}") from e

    async def get_node_state_async(self, node_state_client: Client, timeout_sec: float = 5.0) -> NodeStateSrv.Response:
        """Get node state asynchronously"""
        return await self.call_service_async(
            node_state_client,
            NodeStateSrv.Request(),
            timeout_sec=timeout_sec
        )

    async def get_node_parameters_async(self, node_parameters_client: Client, parameter_names: List[str], timeout_sec: float = 5.0) -> NodeStateSrv.Response:
        """Get node parameters asynchronously"""
        request = GetParameters.Request()
        request.names = parameter_names
        
        return await self.call_service_async(
            node_parameters_client,
            request,
            timeout_sec=timeout_sec
        )

    async def set_node_parameters_async(self, node_parameters_client: Client, parameters: List[Parameter], timeout_sec: float = 5.0) -> SetParameters.Response:
        """Set node parameters asynchronously"""
        request = SetParameters.Request()
        request.parameters = parameters
        
        return await self.call_service_async(
            node_parameters_client,
            request,
            timeout_sec=timeout_sec
        )
    
    async def apply_parameters_async(self, node_parameters_client: Client, timeout_sec: float = 5.0) -> TriggerServiceSrv.Response:
        """Apply node parameters asynchronously"""
        return await self.call_service_async(
            node_parameters_client,
            TriggerServiceSrv.Request(),
            timeout_sec=timeout_sec
        )
    
    async def cleanup_resources_async(self, node_parameters_client: Client, timeout_sec: float = 5.0) -> TriggerServiceSrv.Response:
        """Cleanup node resources asynchronously"""
        return await self.call_service_async(
            node_parameters_client,
            TriggerServiceSrv.Request(),
            timeout_sec=timeout_sec
        )

    async def initialize_node_async(self, node_parameters_client: Client, timeout_sec: float = 5.0) -> TriggerServiceSrv.Response:
        """Initialize node asynchronously"""
        return await self.call_service_async(
            node_parameters_client,
            TriggerServiceSrv.Request(),
            timeout_sec=timeout_sec
        )
    
    async def recover_from_error_async(self, node_parameters_client: Client, timeout_sec: float = 5.0) -> TriggerServiceSrv.Response:
        """Recover node from error asynchronously"""
        return await self.call_service_async(
            node_parameters_client,
            TriggerServiceSrv.Request(),
            timeout_sec=timeout_sec
        )
    
