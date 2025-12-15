import json
import os
from contextlib import asynccontextmanager
from json import JSONDecodeError
from fastapi import FastAPI, HTTPException
from pathlib import Path
from mcp.types import TextContent
from pydantic import BaseModel  # Import BaseModel for request body
from typing import Dict, Any, List, Optional  # Add Any for flexible args/return
from fastapi.responses import JSONResponse
from cuga.config import PACKAGE_ROOT
from cuga.backend.activity_tracker.tracker import ActivityTracker, Step
from cuga.backend.tools_env.registry.config.config_loader import load_service_configs
from cuga.backend.tools_env.registry.mcp_manager.mcp_manager import MCPManager
from cuga.backend.tools_env.registry.registry.api_registry import ApiRegistry
from loguru import logger
from cuga.config import settings

tracker = ActivityTracker()


# --- Pydantic Models ---
class FunctionCallRequest(BaseModel):
    """Request body model for calling a function."""

    app_name: str  # name of the app to call
    function_name: str  # The name of the function to call
    args: Dict[str, Any]  # Arguments for the function


class FunctionCallOnboardRequest(BaseModel):
    """Request body model for calling a function."""

    app_name: str  # name of the app to call
    schemas: List[dict]  # The name of the function to call


# Default configuration file
DEFAULT_MCP_SERVERS_FILE = os.path.join(
    PACKAGE_ROOT, "backend", "tools_env", "registry", "config", "mcp_servers.yaml"
)


# Function to get configuration filename
def get_config_filename():
    resolved_path = Path(os.environ.get("MCP_SERVERS_FILE", DEFAULT_MCP_SERVERS_FILE)).resolve()
    logger.info(f"MCP_SERVERS_FILE: {resolved_path}")
    if not resolved_path.exists():
        raise FileNotFoundError(f"MCP servers configuration file not found: {resolved_path}")
    return resolved_path


@asynccontextmanager
async def lifespan(app: FastAPI):
    global mcp_manager, registry
    config_file = get_config_filename()
    print(f"Using configuration file: {config_file}")
    services = load_service_configs(config_file)
    mcp_manager = MCPManager(config=services)
    registry = ApiRegistry(client=mcp_manager)
    await registry.start_servers()
    yield


# --- FastAPI Server Setup ---
app = FastAPI(
    title="API Registry",
    description="A FastAPI server to register and query API/Application metadata",
    version="0.1.1",  # Incremented version
    lifespan=lifespan,
)


# --- API Endpoints ---


# -- Application Endpoints --
@app.get("/applications", tags=["Applications"])
async def list_applications():
    global registry
    """
    Retrieve a list of all registered applications and their descriptions.
    """
    return await registry.show_applications()


# -- API Endpoints --
@app.get("/applications/{app_name}/apis", tags=["APIs"])
async def list_application_apis(app_name: str, include_response_schema: bool = False):
    global registry
    """
    Retrieve the list of API definitions for a specific application.
    """
    try:
        return await registry.show_apis_for_app(app_name, include_response_schema)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in list_application_apis for '{app_name}': {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {type(e).__name__}: {str(e)}")


@app.get("/apis", tags=["APIs"])
async def list_all_apis(include_response_schema: bool = False):
    global registry
    """
    Retrieve a list of all API definitions across all registered applications.
    """
    return await registry.show_all_apis(include_response_schema)


class AuthAppsRequest(BaseModel):
    apps: List[str]


@app.post("/api/authenticate_apps", tags=["APIs"])
async def authenticate_apps(request: AuthAppsRequest):
    """
    auth_apps
    """
    return await registry.auth_apps(request.apps)


@app.post("/functions/onboard", tags=["Functions"])
async def onboard_function(request: FunctionCallOnboardRequest):
    global registry, mcp_manager
    mcp_manager.schemas[request.app_name] = request.schemas
    return {"status": f"Loaded successfully {len(request.schemas)} tools"}


# --- ENDPOINT for Calling Functions ---
@app.post("/functions/call", tags=["Functions"])
async def call_mcp_function(request: FunctionCallRequest, trajectory_path: Optional[str] = None):
    global registry, mcp_manager

    """
    Calls a named function via the underlying MCP client, passing provided arguments.

    - **name**: The exact name of the function to execute.
    - **args**: A dictionary containing the arguments required by the function.
    """
    print(f"Received request to call function: {request.function_name} with args: {request.args}")
    try:
        global mcp_manager
        apis = await registry.show_apis_for_app(request.app_name)
        api_info = apis.get(request.function_name, {})
        is_secure = api_info.get("secure", False)
        logger.debug(f"is_secure: {is_secure}")
        if trajectory_path:
            settings.update({"ADVANCED_FEATURES": {"TRACKER_ENABLED": True}}, merge=True)
            tracker.collect_step_external(
                Step(name="api_call", data=request.model_dump_json()), full_path=trajectory_path
            )
        result: TextContent = await registry.call_function(
            app_name=request.app_name,
            function_name=request.function_name,
            arguments=request.args,
            auth_config=mcp_manager.auth_config.get(request.app_name) if is_secure else None,
        )
        if isinstance(result, dict):
            tracker.collect_step_external(
                Step(name="api_response", data=json.dumps(result)), full_path=trajectory_path
            )
            return JSONResponse(status_code=result.get("status_code", 500), content=result)
        else:
            result_json = None
            logger.debug(result)
            if result and result[0]:
                result_json = result[0].text
                try:
                    result_json = json.loads(result[0].text)
                except JSONDecodeError:
                    pass
            if result[0].text == "[]":
                result_json = []
            final_response = result_json
        logger.debug(f"Final response: {final_response}")
        tracker.collect_step_external(
            Step(
                name="api_response",
                data=json.dumps(final_response) if not isinstance(final_response, str) else final_response,
            ),
            full_path=trajectory_path,
        )
        return final_response
    except HTTPException as e:
        logger.error(e)

        # Re-raise HTTPExceptions directly (e.g., 404 from registry if app not found, or 500 if client fails)
        raise e
    except Exception as e:
        # Catch any other unexpected errors during the process
        logger.error(e)
        print(f"Unexpected error in call_mcp_function endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error processing function call.")


@app.get("/api/reset")
async def reset():
    registry.auth_manager = None


@app.get("/functions/get_schema/{call_name}", tags=["Functions"])
async def get_mcp_function_schema(request: FunctionCallRequest):
    """
    Calls a named function via the underlying MCP client, passing provided arguments.

    - **name**: The exact name of the function to execute.
    - **args**: A dictionary containing the arguments required by the function.
    """
    pass


# -- Root Endpoint --
@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Welcome to the API Registry. See /docs for API documentation."}


#
# # --- Setup command line argument parser ---
# def parse_arguments():
#     parser = argparse.ArgumentParser(description="API Registry server")
#     parser.add_argument("--config",
#                         default=DEFAULT_MCP_SERVERS_FILE,
#                         help=f"MCP servers configuration JSON file (default: {DEFAULT_MCP_SERVERS_FILE})")
#     return parser.parse_args()


# --- Main Execution Block ---
if __name__ == "__main__":
    import uvicorn

    # args = parse_arguments()
    # # Set environment variable for the lifespan function to use
    # os.environ["MCP_SERVERS_FILE"] = args.config

    # print(f"Starting API Registry server with config: {args.config}...")

    uvicorn.run(app, host="127.0.0.1", port=settings.server_ports.registry)
