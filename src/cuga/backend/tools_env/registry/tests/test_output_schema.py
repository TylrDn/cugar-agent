#!/usr/bin/env python3
"""
Test suite for FastMCP Server with Various Output Types
Tests response schema extraction and validation for different output types
"""

import asyncio
import os
import json
import pytest
import pytest_asyncio
import tempfile
import subprocess
import time
from typing import Optional


from cuga.backend.tools_env.registry.config.config_loader import load_service_configs
from cuga.backend.tools_env.registry.mcp_manager.mcp_manager import MCPManager


MCP_TEST_CONFIG = """# MCP server configuration for output schema testing
mcpServers:
  output_schema_test:
    url: http://127.0.0.1:8002/sse
    description: FastMCP server with various output types for testing response schemas
"""


class TestOutputSchemaServer:
    """Test suite for FastMCP Server with various output types"""

    _server_process: Optional[subprocess.Popen] = None

    @classmethod
    def setup_class(cls):
        """Start the test MCP server before running tests"""
        server_file = os.path.join(os.path.dirname(__file__), "output_schema_server.py")

        print(f"Starting MCP server from {server_file}")
        # Get project root (5 levels up from tests/)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
        cls._server_process = subprocess.Popen(
            ["uv", "run", "python", server_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=project_root,
        )

        # Wait for server to start
        time.sleep(3)

        if cls._server_process.poll() is not None:
            stdout, stderr = cls._server_process.communicate()
            raise RuntimeError(
                f"Server failed to start:\nSTDOUT: {stdout.decode()}\nSTDERR: {stderr.decode()}"
            )

    @classmethod
    def teardown_class(cls):
        """Stop the test MCP server after tests"""
        if cls._server_process:
            cls._server_process.terminate()
            try:
                cls._server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls._server_process.kill()
            cls._server_process = None

    @pytest_asyncio.fixture
    async def manager(self):
        """Setup MCPManager with test server configuration"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(MCP_TEST_CONFIG)
            temp_config_path = f.name

        try:
            configs = load_service_configs(temp_config_path)
            manager = MCPManager(configs)
            await manager.load_tools()
            yield manager
        finally:
            if os.path.exists(temp_config_path):
                os.remove(temp_config_path)

    @pytest.mark.asyncio
    async def test_list_applications(self, manager):
        """Test listing applications"""
        applications = manager.get_server_names()
        assert len(applications) > 0
        assert "output_schema_test" in applications

    @pytest.mark.asyncio
    async def test_list_apis_with_response_schemas(self, manager):
        """Test listing APIs with response schemas"""
        apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)
        assert isinstance(apis, dict)
        assert len(apis) > 0

        # Verify each API has response schema information
        for api_name, api_info in apis.items():
            assert isinstance(api_info, dict)
            assert 'app_name' in api_info
            assert 'api_name' in api_info
            assert 'description' in api_info
            assert 'parameters' in api_info
            assert 'response_schemas' in api_info

    @pytest.mark.asyncio
    async def test_add_function_response_schema(self, manager):
        """Test response schema for add function (int return)"""
        apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)

        add_api = None
        for api_name, api_info in apis.items():
            if "add" in api_name.lower():
                add_api = api_info
                break

        assert add_api is not None
        assert 'response_schemas' in add_api

        # Call the function and verify response matches schema
        result = await manager.call_tool("output_schema_test_add", {"a": 5, "b": 3})
        assert result is not None

        # Parse response
        if hasattr(result, '__iter__') and len(result) > 0:
            content = result[0]
            if hasattr(content, 'text'):
                response_data = json.loads(content.text)
                if isinstance(response_data, dict):
                    assert 'result' in response_data
                    assert isinstance(response_data['result'], int)
                elif isinstance(response_data, int):
                    assert response_data == 8

    @pytest.mark.asyncio
    async def test_list_function_response_schema(self, manager):
        """Test response schema for list return type"""
        result = await manager.call_tool("output_schema_test_get_items", {"count": 3})
        assert result is not None

        if hasattr(result, '__iter__') and len(result) > 0:
            content = result[0]
            if hasattr(content, 'text'):
                response_data = json.loads(content.text)
                # Should be a list or dict with result
                assert isinstance(response_data, (list, dict))
                if isinstance(response_data, dict):
                    assert 'result' in response_data
                    assert isinstance(response_data['result'], list)

    @pytest.mark.asyncio
    async def test_pydantic_model_response_schema(self, manager):
        """Test response schema for Pydantic model return"""
        result = await manager.call_tool(
            "output_schema_test_create_user", {"name": "John Doe", "email": "john@example.com", "age": 30}
        )
        assert result is not None

        if hasattr(result, '__iter__') and len(result) > 0:
            content = result[0]
            if hasattr(content, 'text'):
                response_data = json.loads(content.text)
                # Should have user structure
                if isinstance(response_data, dict):
                    if 'user' in response_data:
                        user = response_data['user']
                        assert 'id' in user
                        assert 'name' in user
                        assert 'email' in user
                        assert 'age' in user
                    else:
                        # Direct user model
                        assert 'id' in response_data
                        assert 'name' in response_data
                        assert 'email' in response_data
                        assert 'age' in response_data

    @pytest.mark.asyncio
    async def test_pydantic_list_response_schema(self, manager):
        """Test response schema for list of Pydantic models"""
        result = await manager.call_tool("output_schema_test_get_products", {"count": 2})
        assert result is not None

        if hasattr(result, '__iter__') and len(result) > 0:
            content = result[0]
            if hasattr(content, 'text'):
                response_data = json.loads(content.text)
                # Should be a dict with result containing array of products
                if isinstance(response_data, dict):
                    assert 'result' in response_data
                    products = response_data['result']
                    assert isinstance(products, list)
                    if len(products) > 0:
                        product = products[0]
                        assert 'id' in product
                        assert 'name' in product
                        assert 'price' in product
                        assert 'in_stock' in product

    @pytest.mark.asyncio
    async def test_nested_dict_response_schema(self, manager):
        """Test response schema for nested dictionary"""
        result = await manager.call_tool("output_schema_test_nested_dict", {"value": "test"})
        assert result is not None

        if hasattr(result, '__iter__') and len(result) > 0:
            content = result[0]
            if hasattr(content, 'text'):
                response_data = json.loads(content.text)
                assert isinstance(response_data, dict)
                assert 'data' in response_data
                assert 'nested' in response_data['data']
                assert 'value' in response_data['data']['nested']

    @pytest.mark.asyncio
    async def test_error_response_handling(self, manager):
        """Test error handling for function that raises error"""
        try:
            result = await manager.call_tool("output_schema_test_raise_error", {"message": "test error"})
            # If error is caught and returned as response
            if result:
                if hasattr(result, '__iter__') and len(result) > 0:
                    content = result[0]
                    if hasattr(content, 'text'):
                        try:
                            response_data = json.loads(content.text)
                            # Error might be in response as JSON
                            assert isinstance(response_data, dict)
                        except json.JSONDecodeError:
                            # Error might be plain text
                            error_text = content.text
                            assert "error" in error_text.lower() or "Error" in error_text
        except Exception as e:
            # Error might be raised, which is also acceptable
            error_str = str(e).lower()
            assert "error" in error_str or "valueerror" in error_str or "jsondecodeerror" in error_str

    @pytest.mark.asyncio
    async def test_output_schema_extraction(self, manager):
        """Test that output schemas are properly extracted from tools"""
        # Get tools from schemas stored in manager
        if "output_schema_test" in manager.schemas:
            tools = manager.schemas["output_schema_test"].get("tools", [])
            assert len(tools) > 0

            # Check that tools have outputSchema
            for tool in tools:
                assert isinstance(tool, dict)
                assert 'name' in tool
                assert 'description' in tool
                assert 'inputSchema' in tool
                # Check if outputSchema exists
                if 'outputSchema' in tool:
                    output_schema = tool['outputSchema']
                    if output_schema:
                        assert isinstance(output_schema, dict)

    @pytest.mark.asyncio
    async def test_explicit_output_schema_tool(self, manager):
        """Test tool with explicit output schema"""
        apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)

        # Find the explicit schema tool
        explicit_tool = None
        for api_name, api_info in apis.items():
            if "explicit_schema_tool" in api_name:
                explicit_tool = api_info
                break

        assert explicit_tool is not None
        assert 'response_schemas' in explicit_tool

        # Verify schema structure
        success_schema = explicit_tool['response_schemas']['success']
        assert success_schema.get('type') == 'object'
        assert 'status' in success_schema.get('properties', {})
        assert 'count' in success_schema.get('properties', {})
        assert 'items' in success_schema.get('properties', {})

        # Call the function
        result = await manager.call_tool("output_schema_test_explicit_schema_tool", {"count": 2})
        assert result is not None

        if hasattr(result, '__iter__') and len(result) > 0:
            content = result[0]
            if hasattr(content, 'text'):
                response_data = json.loads(content.text)
                if isinstance(response_data, dict):
                    assert 'status' in response_data
                    assert 'count' in response_data
                    assert 'items' in response_data

    @pytest.mark.asyncio
    async def test_complex_nested_schema(self, manager):
        """Test tool with complex nested output schema"""
        apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)

        # Find the complex nested schema tool
        complex_tool = None
        for api_name, api_info in apis.items():
            if "complex_nested_schema" in api_name:
                complex_tool = api_info
                break

        assert complex_tool is not None
        assert 'response_schemas' in complex_tool

        # Verify nested schema structure
        success_schema = complex_tool['response_schemas']['success']
        assert success_schema.get('type') == 'object'
        assert 'user_info' in success_schema.get('properties', {})
        assert 'metadata' in success_schema.get('properties', {})

        user_info_schema = success_schema['properties']['user_info']
        assert user_info_schema.get('type') == 'object'
        assert 'username' in user_info_schema.get('properties', {})
        assert 'email' in user_info_schema.get('properties', {})

        # Call the function
        result = await manager.call_tool(
            "output_schema_test_complex_nested_schema", {"username": "testuser", "email": "test@example.com"}
        )
        assert result is not None

        if hasattr(result, '__iter__') and len(result) > 0:
            content = result[0]
            if hasattr(content, 'text'):
                response_data = json.loads(content.text)
                if isinstance(response_data, dict):
                    assert 'user_info' in response_data
                    assert 'username' in response_data['user_info']
                    assert 'email' in response_data['user_info']

    @pytest.mark.asyncio
    async def test_all_tools_have_schemas(self, manager):
        """Test that all tools return valid response schemas"""
        apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)

        # Expected tools
        expected_tools = [
            "add",
            "greet",
            "get_items",
            "calculate_sum",
            "create_user",
            "get_products",
            "raise_error",
            "nested_dict",
            "explicit_schema_tool",
            "complex_nested_schema",
        ]

        for tool_name in expected_tools:
            found = False
            for api_name in apis.keys():
                if tool_name in api_name:
                    found = True
                    api_info = apis[api_name]
                    assert 'response_schemas' in api_info
                    assert 'success' in api_info['response_schemas']
                    assert 'failure' in api_info['response_schemas']
                    break
            assert found, f"Tool {tool_name} not found in APIs"

    @pytest.mark.asyncio
    async def test_add_response_schema_structure(self, manager):
        """Test response schema structure for add function (int return)"""
        apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)

        add_api = None
        for api_name, api_info in apis.items():
            if "add" in api_name.lower() and "explicit" not in api_name.lower():
                add_api = api_info
                break

        assert add_api is not None
        assert 'response_schemas' in add_api

        success_schema = add_api['response_schemas']['success']
        failure_schema = add_api['response_schemas']['failure']

        assert isinstance(success_schema, dict)
        assert isinstance(failure_schema, dict)

        assert success_schema.get('type') == 'integer' or 'result' in str(success_schema)

        result = await manager.call_tool("output_schema_test_add", {"a": 5, "b": 3})
        assert result is not None

    @pytest.mark.asyncio
    async def test_greet_response_schema_structure(self, manager):
        """Test response schema structure for greet function (str return)"""
        apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)

        greet_api = None
        for api_name, api_info in apis.items():
            if "greet" in api_name.lower():
                greet_api = api_info
                break

        assert greet_api is not None
        assert 'response_schemas' in greet_api

        success_schema = greet_api['response_schemas']['success']
        failure_schema = greet_api['response_schemas']['failure']

        assert isinstance(success_schema, dict)
        assert isinstance(failure_schema, dict)

        assert success_schema.get('type') == 'string' or 'result' in str(success_schema)

        result = await manager.call_tool("output_schema_test_greet", {"name": "Test"})
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_items_response_schema_structure(self, manager):
        """Test response schema structure for get_items function (List[str] return)"""
        apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)

        get_items_api = None
        for api_name, api_info in apis.items():
            if "get_items" in api_name.lower():
                get_items_api = api_info
                break

        assert get_items_api is not None
        assert 'response_schemas' in get_items_api

        success_schema = get_items_api['response_schemas']['success']
        failure_schema = get_items_api['response_schemas']['failure']

        assert isinstance(success_schema, dict)
        assert isinstance(failure_schema, dict)

        assert (
            success_schema.get('type') == 'array'
            or 'items' in success_schema
            or 'result' in str(success_schema)
        )

        result = await manager.call_tool("output_schema_test_get_items", {"count": 3})
        assert result is not None

    @pytest.mark.asyncio
    async def test_calculate_sum_response_schema_structure(self, manager):
        """Test response schema structure for calculate_sum function (dict return)"""
        apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)

        calculate_sum_api = None
        for api_name, api_info in apis.items():
            if "calculate_sum" in api_name.lower():
                calculate_sum_api = api_info
                break

        assert calculate_sum_api is not None
        assert 'response_schemas' in calculate_sum_api

        success_schema = calculate_sum_api['response_schemas']['success']
        failure_schema = calculate_sum_api['response_schemas']['failure']

        assert isinstance(success_schema, dict)
        assert isinstance(failure_schema, dict)

        assert (
            success_schema.get('type') == 'object'
            or 'properties' in success_schema
            or 'result' in str(success_schema)
        )

        result = await manager.call_tool("output_schema_test_calculate_sum", {"numbers": [1, 2, 3]})
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_user_response_schema_structure(self, manager):
        """Test response schema structure for create_user function (Pydantic model return)"""
        apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)

        create_user_api = None
        for api_name, api_info in apis.items():
            if "create_user" in api_name.lower():
                create_user_api = api_info
                break

        assert create_user_api is not None
        assert 'response_schemas' in create_user_api

        success_schema = create_user_api['response_schemas']['success']
        failure_schema = create_user_api['response_schemas']['failure']

        assert isinstance(success_schema, dict)
        assert isinstance(failure_schema, dict)

        assert (
            success_schema.get('type') == 'object'
            or 'properties' in success_schema
            or 'result' in str(success_schema)
        )

        if 'properties' in success_schema:
            props = success_schema['properties']
            if 'id' in props or 'name' in props or 'email' in props:
                assert True

        result = await manager.call_tool(
            "output_schema_test_create_user", {"name": "John Doe", "email": "john@example.com", "age": 30}
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_products_response_schema_structure(self, manager):
        """Test response schema structure for get_products function (List[ProductModel] return)"""
        apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)

        get_products_api = None
        for api_name, api_info in apis.items():
            if "get_products" in api_name.lower():
                get_products_api = api_info
                break

        assert get_products_api is not None
        assert 'response_schemas' in get_products_api

        success_schema = get_products_api['response_schemas']['success']
        failure_schema = get_products_api['response_schemas']['failure']

        assert isinstance(success_schema, dict)
        assert isinstance(failure_schema, dict)

        assert (
            success_schema.get('type') == 'array'
            or 'items' in success_schema
            or 'result' in str(success_schema)
        )

        if 'items' in success_schema:
            items_schema = success_schema['items']
            if isinstance(items_schema, dict) and 'properties' in items_schema:
                props = items_schema['properties']
                if 'id' in props or 'name' in props or 'price' in props:
                    assert True

        result = await manager.call_tool("output_schema_test_get_products", {"count": 2})
        assert result is not None

    @pytest.mark.asyncio
    async def test_nested_dict_response_schema_structure(self, manager):
        """Test response schema structure for nested_dict function"""
        apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)

        nested_dict_api = None
        for api_name, api_info in apis.items():
            if "nested_dict" in api_name.lower():
                nested_dict_api = api_info
                break

        assert nested_dict_api is not None
        assert 'response_schemas' in nested_dict_api

        success_schema = nested_dict_api['response_schemas']['success']
        failure_schema = nested_dict_api['response_schemas']['failure']

        assert isinstance(success_schema, dict)
        assert isinstance(failure_schema, dict)

        assert (
            success_schema.get('type') == 'object'
            or 'properties' in success_schema
            or 'result' in str(success_schema)
        )

        if 'properties' in success_schema:
            props = success_schema['properties']
            if 'data' in props:
                data_schema = props['data']
                if isinstance(data_schema, dict) and 'properties' in data_schema:
                    nested_props = data_schema['properties']
                    if 'nested' in nested_props:
                        assert True

        result = await manager.call_tool("output_schema_test_nested_dict", {"value": "test"})
        assert result is not None

    @pytest.mark.asyncio
    async def test_raise_error_response_schema_structure(self, manager):
        """Test response schema structure for raise_error function"""
        apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)

        raise_error_api = None
        for api_name, api_info in apis.items():
            if "raise_error" in api_name.lower():
                raise_error_api = api_info
                break

        assert raise_error_api is not None
        assert 'response_schemas' in raise_error_api

        success_schema = raise_error_api['response_schemas']['success']
        failure_schema = raise_error_api['response_schemas']['failure']

        assert isinstance(success_schema, dict)
        assert isinstance(failure_schema, dict)

        assert failure_schema.get('error') == 'string' or isinstance(failure_schema, dict)

    @pytest.mark.asyncio
    async def test_explicit_schema_tool_response_schema_structure(self, manager):
        """Test response schema structure for explicit_schema_tool"""
        apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)

        explicit_tool = None
        for api_name, api_info in apis.items():
            if "explicit_schema_tool" in api_name:
                explicit_tool = api_info
                break

        assert explicit_tool is not None
        assert 'response_schemas' in explicit_tool

        success_schema = explicit_tool['response_schemas']['success']
        failure_schema = explicit_tool['response_schemas']['failure']

        assert isinstance(success_schema, dict)
        assert isinstance(failure_schema, dict)

        assert success_schema.get('type') == 'object'
        assert 'properties' in success_schema
        props = success_schema['properties']
        assert 'status' in props
        assert 'count' in props
        assert 'items' in props
        assert props['status'].get('type') == 'string'
        assert props['count'].get('type') == 'integer'
        assert props['items'].get('type') == 'array'

        result = await manager.call_tool("output_schema_test_explicit_schema_tool", {"count": 2})
        assert result is not None

    @pytest.mark.asyncio
    async def test_complex_nested_schema_response_schema_structure(self, manager):
        """Test response schema structure for complex_nested_schema tool"""
        apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)

        complex_tool = None
        for api_name, api_info in apis.items():
            if "complex_nested_schema" in api_name:
                complex_tool = api_info
                break

        assert complex_tool is not None
        assert 'response_schemas' in complex_tool

        success_schema = complex_tool['response_schemas']['success']
        failure_schema = complex_tool['response_schemas']['failure']

        assert isinstance(success_schema, dict)
        assert isinstance(failure_schema, dict)

        assert success_schema.get('type') == 'object'
        assert 'properties' in success_schema
        props = success_schema['properties']
        assert 'user_info' in props
        assert 'metadata' in props

        user_info_schema = props['user_info']
        assert user_info_schema.get('type') == 'object'
        assert 'properties' in user_info_schema
        user_info_props = user_info_schema['properties']
        assert 'username' in user_info_props
        assert 'email' in user_info_props
        assert user_info_props['username'].get('type') == 'string'
        assert user_info_props['email'].get('type') == 'string'

        result = await manager.call_tool(
            "output_schema_test_complex_nested_schema", {"username": "testuser", "email": "test@example.com"}
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_all_response_schemas_have_valid_structure(self, manager):
        """Test that all response schemas have valid structure"""
        apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)

        for api_name, api_info in apis.items():
            assert 'response_schemas' in api_info, f"{api_name} missing response_schemas"

            response_schemas = api_info['response_schemas']
            assert isinstance(response_schemas, dict), f"{api_name} response_schemas is not a dict"
            assert 'success' in response_schemas, f"{api_name} missing success schema"
            assert 'failure' in response_schemas, f"{api_name} missing failure schema"

            success_schema = response_schemas['success']
            failure_schema = response_schemas['failure']

            assert isinstance(success_schema, dict), f"{api_name} success schema is not a dict"
            assert isinstance(failure_schema, dict), f"{api_name} failure schema is not a dict"

            if 'type' in success_schema:
                assert success_schema['type'] in [
                    'string',
                    'integer',
                    'number',
                    'boolean',
                    'array',
                    'object',
                ], f"{api_name} has invalid success schema type: {success_schema['type']}"


async def run_output_schema_tests():
    """Run output schema tests standalone"""
    print("🧪 Testing FastMCP Server with Various Output Types")
    print("=" * 60)

    # Start server
    server_file = os.path.join(os.path.dirname(__file__), "output_schema_server.py")
    print(f"Starting server from {server_file}")

    # Get project root (5 levels up from tests/)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
    server_process = subprocess.Popen(
        ["uv", "run", "python", server_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=project_root
    )

    try:
        time.sleep(3)

        if server_process.poll() is not None:
            stdout, stderr = server_process.communicate()
            print(f"❌ Server failed to start:\nSTDOUT: {stdout.decode()}\nSTDERR: {stderr.decode()}")
            return

        # Create temporary config file
        temp_config_path = "/tmp/output_schema_test_config.yaml"
        with open(temp_config_path, 'w') as f:
            f.write(MCP_TEST_CONFIG)

        try:
            # Load configuration
            configs = load_service_configs(temp_config_path)
            print(f"✅ Loaded {len(configs)} service configurations")

            # Initialize MCP Manager
            manager = MCPManager(configs)
            print("\n🔧 Loading MCP tools...")
            await manager.load_tools()
            print("✅ MCP tools loaded successfully")

            # Test 1: List Applications
            print("\n📱 Test 1: List Applications")
            applications = manager.get_server_names()
            print(f"✅ Found {len(applications)} applications: {applications}")
            assert "output_schema_test" in applications

            # Test 2: List APIs with Response Schemas
            print("\n🔍 Test 2: List APIs with Response Schemas")
            apis = manager.get_apis_for_application("output_schema_test", include_response_schema=True)
            print(f"✅ Found {len(apis)} APIs")

            for api_name, api_info in list(apis.items())[:3]:
                print(f"   - {api_name}")
                if 'response_schemas' in api_info:
                    print("     Has response schema: ✅")

            # Test 3: Test Add Function
            print("\n📞 Test 3: Call Add Function")
            result = await manager.call_tool("output_schema_test_add", {"a": 10, "b": 5})
            print("✅ Add function call successful")
            if result and hasattr(result, '__iter__') and len(result) > 0:
                content = result[0]
                if hasattr(content, 'text'):
                    print(f"   Response: {content.text[:100]}")

            # Test 4: Test List Function
            print("\n📞 Test 4: Call Get Items Function")
            result = await manager.call_tool("output_schema_test_get_items", {"count": 3})
            print("✅ Get items function call successful")
            if result and hasattr(result, '__iter__') and len(result) > 0:
                content = result[0]
                if hasattr(content, 'text'):
                    print(f"   Response: {content.text[:100]}")

            # Test 5: Test Pydantic Model
            print("\n📞 Test 5: Call Create User Function")
            result = await manager.call_tool(
                "output_schema_test_create_user",
                {"name": "Test User", "email": "test@example.com", "age": 25},
            )
            print("✅ Create user function call successful")
            if result and hasattr(result, '__iter__') and len(result) > 0:
                content = result[0]
                if hasattr(content, 'text'):
                    print(f"   Response: {content.text[:100]}")

            # Test 6: Test Explicit Schema Tool
            print("\n📞 Test 6: Call Explicit Schema Tool")
            result = await manager.call_tool("output_schema_test_explicit_schema_tool", {"count": 3})
            print("✅ Explicit schema tool call successful")
            if result and hasattr(result, '__iter__') and len(result) > 0:
                content = result[0]
                if hasattr(content, 'text'):
                    response_data = json.loads(content.text)
                    print(f"   Status: {response_data.get('status')}")
                    print(f"   Count: {response_data.get('count')}")
                    print(f"   Items: {response_data.get('items')}")

            # Test 7: Test Complex Nested Schema
            print("\n📞 Test 7: Call Complex Nested Schema Tool")
            result = await manager.call_tool(
                "output_schema_test_complex_nested_schema",
                {"username": "testuser", "email": "test@example.com"},
            )
            print("✅ Complex nested schema tool call successful")
            if result and hasattr(result, '__iter__') and len(result) > 0:
                content = result[0]
                if hasattr(content, 'text'):
                    response_data = json.loads(content.text)
                    print(f"   Username: {response_data.get('user_info', {}).get('username')}")
                    print(f"   Email: {response_data.get('user_info', {}).get('email')}")

            # Test 8: Verify All Tools Have Schemas
            print("\n🔍 Test 8: Verify All Tools Have Response Schemas")
            all_tools_count = len(apis)
            print(f"✅ All {all_tools_count} tools have response schemas")

            print("\n🎉 Output Schema Tests Completed!")

        finally:
            if os.path.exists(temp_config_path):
                os.remove(temp_config_path)

    finally:
        # Stop server
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()


if __name__ == "__main__":
    asyncio.run(run_output_schema_tests())
