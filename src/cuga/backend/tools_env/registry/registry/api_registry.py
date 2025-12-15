import json
import traceback
from typing import Dict, List, Any
from fastapi import HTTPException
from cuga.backend.tools_env.registry.mcp_manager.mcp_manager import MCPManager
from cuga.backend.tools_env.registry.registry.authentication.appworld_auth_manager import (
    AppWorldAuthManager,
)
from loguru import logger

from cuga.backend.tools_env.registry.utils.types import AppDefinition


class ApiRegistry:
    """
    Internal class to manage API and Application information,
    interacting with the mcp manager
    """

    def __init__(self, client: MCPManager):
        logger.info("ApiRegistry: Initializing.")
        self.mcp_client = client
        self.auth_manager = None

    async def start_servers(self):
        """Start servers and load tools"""
        await self.mcp_client.load_tools()
        logger.info("ApiRegistry: Servers started successfully.")

    async def show_applications(self) -> List[AppDefinition]:
        """Lists application names and their descriptions."""
        logger.debug("ApiRegistry: show_applications() called.")
        apps = self.mcp_client.get_apps()
        return [AppDefinition(name=p.name, url=p.url, description=p.description) for p in apps]

    async def show_apis_for_app(self, app_name: str, include_response_schema: bool = False) -> List[Dict]:
        """Lists API definitions of a specific app."""
        logger.debug(f"ApiRegistry: show_apis_for_app(app_name='{app_name}') called.")
        try:
            return self.mcp_client.get_apis_for_application(app_name, include_response_schema)
        except KeyError:
            logger.error(
                f"Application '{app_name}' not found in registry. Available apps: {[app.name for app in self.mcp_client.get_apps()]}"
            )
            raise HTTPException(status_code=404, detail=f"Application '{app_name}' not found in registry")
        except Exception as e:
            logger.error(f"Error getting APIs for app '{app_name}': {type(e).__name__}: {e}")
            raise

    async def show_all_apis(self, include_response_schema) -> List[Dict[str, str]]:
        """Gets all API definitions."""
        logger.debug("ApiRegistry: show_all_apis() called.")
        return self.mcp_client.get_all_apis(include_response_schema)

    async def auth_apps(self, apps: List[str]):
        """Gets all API definitions."""
        logger.debug("auth_apps: auth_apps called.")
        if not self.auth_manager:
            self.auth_manager = AppWorldAuthManager()
        for app in apps:
            self.auth_manager.get_access_token(app)

    async def call_function(
        self, app_name: str, function_name: str, arguments: Dict[str, Any], auth_config=None
    ) -> Dict[str, Any]:
        """Calls a function via the mcp_client."""
        headers = {}
        logger.debug(auth_config)
        if auth_config:
            if auth_config.type == 'oauth2':
                if not self.auth_manager:
                    self.auth_manager = AppWorldAuthManager()

                access_token = self.auth_manager.get_access_token(app_name)
                if access_token:
                    headers = {"Authorization": "Bearer " + access_token}
            elif auth_config.value:
                headers = {f"{auth_config.type}": f"{auth_config.value}"}

        logger.debug(
            f"ApiRegistry: call_function(function_name='{function_name}', arguments={arguments}, headers={headers}) called."
        )
        try:
            # Delegate the call to the client
            args = arguments['params'] if 'params' in arguments else arguments
            if self.auth_manager:
                headers["_tokens"] = json.dumps(self.auth_manager.get_stored_tokens())
            result = await self.mcp_client.call_tool(
                tool_name=function_name,
                args=args,
                headers=headers,
            )
            logger.debug("Response:", result)
            return result
        except Exception as e:
            # In a real scenario, you might catch specific client exceptions
            logger.error(traceback.format_exc())

            logger.error(f"Error calling MCP function '{function_name}': {e}")

            # Return structured error response instead of raising HTTPException
            return {
                "status": "exception",
                "status_code": 500,
                "message": f"Error executing function '{function_name}': {str(e)}",
                "error_type": type(e).__name__,
                "function_name": function_name,
            }
