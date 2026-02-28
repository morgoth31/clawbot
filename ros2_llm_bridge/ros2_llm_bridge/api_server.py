import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Any, Dict, List

import rclpy
from fastapi import Depends, FastAPI, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from rclpy.executors import MultiThreadedExecutor

from ros2_llm_bridge.action_handler import ActionHandler, ToolFormat
from ros2_llm_bridge.bridge_node import BridgeNode

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ros2_llm_bridge.api")

# ---------------------------------------------------------------------------
# Optional API-key authentication
# ---------------------------------------------------------------------------

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _verify_api_key(api_key: str = Security(_API_KEY_HEADER)) -> None:
    """Enforce X-API-Key when the API_KEY environment variable is set.

    If API_KEY is not configured the check is skipped, making auth opt-in for
    development. Set API_KEY=<secret> in the environment (or .env file) to
    require authentication on all endpoints.
    """
    required = os.getenv("API_KEY")
    if required and api_key != required:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key header.",
        )


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ToolExecutionRequest(BaseModel):
    """Payload for a tool-call request."""

    function: str
    arguments: Dict[str, Any] = {}


class CommandResponse(BaseModel):
    """Result returned after a tool is executed."""

    result: str


# ---------------------------------------------------------------------------
# ROS 2 lifecycle — managed via FastAPI lifespan
# ---------------------------------------------------------------------------


def _ros_spin_thread(executor: MultiThreadedExecutor) -> None:
    """Run the ROS 2 executor in a background thread."""
    logger.info("ROS 2 executor thread started.")
    executor.spin()
    logger.info("ROS 2 executor thread stopped.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise ROS 2 on startup and cleanly shut it down on exit."""
    logger.info("Initialising ROS 2…")
    rclpy.init()

    node = BridgeNode()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)

    thread = threading.Thread(
        target=_ros_spin_thread, args=(executor,), daemon=True
    )
    thread.start()

    # Store everything on app.state so endpoints can access it via DI.
    app.state.ros_node = node
    app.state.ros_executor = executor
    app.state.executor_thread = thread
    app.state.action_handler = ActionHandler(bridge_node=node)

    logger.info("ROS 2 ready.")
    yield  # application runs here

    logger.info("Shutting down ROS 2…")
    executor.shutdown()
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
    thread.join(timeout=2.0)
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ROS 2 LLM Bridge",
    description=(
        "HTTP API that exposes a ROS 2 robot's capabilities as LLM tool calls. "
        "Use GET /tools to discover available actions and their schemas, "
        "then POST /command to execute them."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


def _get_action_handler(request: Request) -> ActionHandler:
    """FastAPI dependency: return the shared ActionHandler or raise 503."""
    handler: ActionHandler | None = getattr(
        request.app.state, "action_handler", None
    )
    if handler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Action handler is not initialised yet.",
        )
    return handler


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get(
    "/tools",
    response_model=List[Dict[str, Any]],
    summary="List available tools",
    description=(
        "Returns the schema for every action the robot supports. "
        "Use `?format=openai` (default) for OpenAI function-calling format, "
        "`?format=anthropic` for Anthropic tool-use format, or "
        "`?format=raw` for the raw Pydantic JSON Schema."
    ),
    tags=["Tools"],
    dependencies=[Depends(_verify_api_key)],
)
async def get_tools(
    format: ToolFormat = "openai",
    handler: ActionHandler = Depends(_get_action_handler),
) -> List[Dict[str, Any]]:
    """Return all tool schemas in the requested LLM format."""
    return handler.get_tools_schema(format=format)


@app.post(
    "/command",
    response_model=CommandResponse,
    summary="Execute a tool",
    description=(
        "Execute a robot tool by name. The `function` field must match a tool "
        "name returned by GET /tools. Arguments are validated against the tool "
        "schema before execution."
    ),
    tags=["Command"],
    dependencies=[Depends(_verify_api_key)],
)
async def execute_command(
    request: ToolExecutionRequest,
    handler: ActionHandler = Depends(_get_action_handler),
) -> CommandResponse:
    """Dispatch a tool-call request to the robot."""
    timeout = handler.get_tool_timeout(request.function)

    try:
        result = await asyncio.wait_for(
            handler.execute_tool(request.function, request.arguments),
            timeout=timeout,
        )
        return CommandResponse(result=result)

    except asyncio.TimeoutError:
        logger.error(
            "Tool '%s' timed out after %.1f s", request.function, timeout
        )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=(
                f"Tool '{request.function}' did not complete within "
                f"{timeout:.0f} seconds."
            ),
        )
    except ValueError as exc:
        # Unknown tool name or invalid arguments — client error.
        logger.warning("Bad request for tool '%s': %s", request.function, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
    except Exception as exc:
        # ROS 2 or bridge failure — server/robot error.
        logger.error(
            "Error executing tool '%s': %s", request.function, exc
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Robot execution failed: {exc}",
        )


@app.get(
    "/health",
    summary="Health check",
    description="Returns 200 when the API and ROS 2 node are healthy.",
    tags=["Meta"],
)
async def health_check(request: Request) -> Dict[str, str]:
    """Liveness probe used by Docker and orchestration frameworks."""
    node = getattr(request.app.state, "ros_node", None)
    if node is None or not rclpy.ok():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ROS 2 node is not running.",
        )
    return {"status": "healthy"}
