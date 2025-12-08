"""
Combined Tool Provider

Provides tools from both runtime tracker tools and registry.
First checks tracker for runtime tools, then falls back to registry.
"""

from typing import List, Dict, Optional, Any
import aiohttp

from loguru import logger
from langchain_core.tools import StructuredTool

from cuga.backend.activity_tracker.tracker import ActivityTracker
from cuga.backend.tools_env.registry.utils.api_utils import get_apps, get_registry_base_url
from cuga.backend.tools_env.registry.utils.types import AppDefinition
from cuga.backend.cuga_graph.nodes.cuga_lite.tool_provider_interface import (
    ToolProviderInterface,
)
from cuga.backend.cuga_graph.nodes.cuga_lite.tool_registry_provider import (
    create_tool_from_api_dict,
)
from cuga.config import settings


def create_tool_from_tracker(tool_name: str, tool_def: Dict[str, Any], app_name: str) -> StructuredTool:
    """Create a StructuredTool that uses tracker.invoke_tool instead of API calls.

    Args:
        tool_name: Name of the tool
        tool_def: Tool definition dict from tracker
        app_name: Name of the app/server

    Returns:
        StructuredTool instance that calls tracker.invoke_tool
    """
    from pydantic import create_model, Field

    description = tool_def.get('description', '')
    parameters = tool_def.get('parameters', {})

    # Convert OpenAPI parameter format to JSON schema format if needed
    if isinstance(parameters, list):
        # Use the same conversion function from tool_registry_provider
        def _convert_openapi_params_to_json_schema(params):
            properties = {}
            required = []
            for param in params:
                name = param.get('name', '')
                param_type = param.get('schema', {}).get('type', 'string')
                param_desc = param.get('description', '')
                properties[name] = {'type': param_type, 'description': param_desc}

                # Handle constraints
                constraints = param.get('constraints', [])
                if constraints:
                    properties[name]['constraints'] = constraints

                if param.get('required', False):
                    required.append(name)
            return {'properties': properties, 'required': required}

        parameters = _convert_openapi_params_to_json_schema(parameters)

    field_definitions = {}
    param_constraints = {}
    if isinstance(parameters, dict):
        if 'properties' in parameters:
            props = parameters['properties']
            required = parameters.get('required', [])
            for param_name, param_schema in props.items():
                param_type = param_schema.get('type', 'string')
                param_desc = param_schema.get('description', '')

                # Handle type that might be a list (e.g., ['string', 'null'])
                if isinstance(param_type, list):
                    # Take the first non-null type, or default to 'string'
                    param_type = next((t for t in param_type if t != 'null'), 'string')

                type_mapping = {
                    'string': str,
                    'integer': int,
                    'number': float,
                    'boolean': bool,
                    'array': list,
                    'object': dict,
                }
                python_type = type_mapping.get(param_type, str)

                # Store constraints for later use in prompt
                constraints = param_schema.get('constraints', [])
                if constraints:
                    param_constraints[param_name] = constraints

                if param_name in required:
                    field_definitions[param_name] = (python_type, Field(..., description=param_desc))
                else:
                    default_val = param_schema.get('default', None)
                    # Make sure default values are hashable if needed
                    if isinstance(default_val, list):
                        default_val = None  # Skip unhashable defaults
                    field_definitions[param_name] = (
                        python_type,
                        Field(default=default_val, description=param_desc),
                    )

    if field_definitions:
        InputModel = create_model(f"{tool_name}Input", **field_definitions)
    else:
        InputModel = create_model(f"{tool_name}Input")

    async def tool_func(*args, **kwargs):
        try:
            # Combine positional and keyword arguments
            all_kwargs = {}
            param_names = list(field_definitions.keys()) if field_definitions else []

            # Map positional arguments to parameter names
            for i, arg in enumerate(args):
                if i < len(param_names):
                    all_kwargs[param_names[i]] = arg
                else:
                    # If more positional args than expected, add them as extra
                    all_kwargs[f"arg{i}"] = arg

            # Add keyword arguments
            all_kwargs.update(kwargs)

            # Use tracker.invoke_tool instead of call_api
            result = await tracker.invoke_tool(app_name, tool_name, all_kwargs)
            return result
        except Exception as e:
            error_msg = f"Error calling {tool_name} via tracker: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

    tool_func.__name__ = tool_name
    tool_func.__doc__ = description

    tool = StructuredTool.from_function(
        func=tool_func, name=tool_name, description=description, args_schema=InputModel
    )

    tool.func = tool_func

    if not hasattr(tool.func, '_param_constraints'):
        tool.func._param_constraints = param_constraints

    return tool


tracker = ActivityTracker()


class CombinedToolProvider(ToolProviderInterface):
    """
    Tool provider that combines runtime tools from tracker and registry tools.

    First checks tracker for runtime tools, then tries registry with try/catch.
    """

    def __init__(self, app_names: Optional[List[str]] = None):
        """
        Initialize the combined tool provider.

        Args:
            app_names: Optional list of specific app names to load. If None, loads all.
        """
        self.app_names = app_names
        self.apps: List[AppDefinition] = []
        self.tools_cache: Dict[str, List[StructuredTool]] = {}
        self.initialized = False

    async def initialize(self):
        """Load apps from tracker and registry."""
        logger.info("Initializing CombinedToolProvider...")

        tracker_apps = []
        if hasattr(tracker, 'apps') and tracker.apps:
            tracker_apps = tracker.apps

        registry_apps = []
        if settings.advanced_features.registry:
            try:
                registry_apps = await get_apps()
            except Exception as e:
                logger.warning(f"Failed to get apps from registry: {e}")

        all_apps = tracker_apps + registry_apps

        if not all_apps:
            logger.warning("No apps found in tracker or registry")
            self.apps = []
        else:
            if self.app_names:
                filtered_apps = [app for app in all_apps if app.name in self.app_names]
                if not filtered_apps:
                    logger.warning(f"None of the requested apps found: {self.app_names}")
                self.apps = [
                    AppDefinition(
                        name=app.name,
                        url=app.url,
                        description=getattr(app, 'description', None),
                        type=getattr(app, 'type', 'api'),
                    )
                    for app in filtered_apps
                ]
            else:
                self.apps = [
                    AppDefinition(
                        name=app.name,
                        url=app.url,
                        description=getattr(app, 'description', None),
                        type=getattr(app, 'type', 'api'),
                    )
                    for app in all_apps
                ]

        logger.info(f"Found {len(self.apps)} apps: {[app.name for app in self.apps]}")
        self.initialized = True

    async def get_apps(self) -> List[AppDefinition]:
        """Get list of available applications."""
        if not self.initialized:
            await self.initialize()
        return self.apps

    async def get_tools(self, app_name: str) -> List[StructuredTool]:
        """
        Get tools for a specific application.

        First checks tracker for runtime tools, then tries registry.

        Args:
            app_name: Name of the application

        Returns:
            List of LangChain StructuredTool objects
        """
        if not self.initialized:
            await self.initialize()

        if app_name in self.tools_cache:
            return self.tools_cache[app_name]

        all_tools = []

        try:
            logger.debug(f"Checking tracker for runtime tools: {app_name}")
            tracker_tools_dict = tracker.get_tools_by_server(app_name)

            if not settings.advanced_features.registry:
                logger.debug("Registry is not enabled, using tracker tools only")
                if tracker_tools_dict:
                    tools = []
                    for tool_name, tool_def in tracker_tools_dict.items():
                        try:
                            tool = create_tool_from_tracker(tool_name, tool_def, app_name)
                            tools.append(tool)
                        except Exception as e:
                            logger.warning(f"Failed to create tool {tool_name} from tracker: {e}")
                            continue
                    self.tools_cache[app_name] = tools
                    return tools
                return []

            if tracker_tools_dict:
                for tool_name, tool_def in tracker_tools_dict.items():
                    try:
                        tool = create_tool_from_api_dict(tool_name, tool_def, app_name)
                        all_tools.append(tool)
                    except Exception as e:
                        logger.warning(f"Failed to create tool {tool_name} from tracker: {e}")
                        continue
        except Exception as e:
            logger.warning(f"Error getting tools from tracker for {app_name}: {e}")

        if settings.advanced_features.registry:
            try:
                logger.debug(f"Getting tools from registry for: {app_name}")
                registry_base = get_registry_base_url()
                url = f'{registry_base}/applications/{app_name}/apis?include_response_schema=true'
                headers = {'accept': 'application/json'}

                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            api_dicts = await response.json()
                            if api_dicts:
                                for tool_name, tool_def in api_dicts.items():
                                    if any(tool.name == tool_name for tool in all_tools):
                                        continue
                                    try:
                                        tool = create_tool_from_api_dict(tool_name, tool_def, app_name)
                                        all_tools.append(tool)
                                        logger.debug(f"  ✓ {tool_name}")
                                    except Exception as e:
                                        logger.warning(f"  ✗ Failed to create tool {tool_name}: {e}")
                                        continue
                        else:
                            error_text = await response.text()
                            logger.warning(
                                f"Registry request failed with status {response.status}: {error_text}"
                            )
            except Exception as e:
                logger.warning(f"Error getting tools from registry for {app_name}: {e}")

        self.tools_cache[app_name] = all_tools
        logger.info(f"Loaded {len(all_tools)} tools for '{app_name}'")
        return all_tools

    async def get_all_tools(self) -> List[StructuredTool]:
        """Get all available tools from all applications."""
        if not self.initialized:
            await self.initialize()

        all_tools = []
        for app in self.apps:
            tools = await self.get_tools(app.name)
            all_tools.extend(tools)

        logger.info(f"Loaded {len(all_tools)} total tools from {len(self.apps)} apps")
        return all_tools
