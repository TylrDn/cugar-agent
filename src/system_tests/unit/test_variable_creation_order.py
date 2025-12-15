"""
System test for variable creation order validation.

Tests that variables are created and stored in the correct order
when multiple variables are created in sequence during code execution.
"""

import pytest
from cuga.backend.cuga_graph.nodes.cuga_lite.cuga_agent_base import eval_with_tools_async
from cuga.backend.cuga_graph.state.agent_state import AgentState


@pytest.mark.asyncio
class TestVariableCreationOrder:
    async def test_variable_creation_order_preserved(self):
        """
        Test that variables created in sequence maintain their creation order.

        This test validates that when multiple variables are created in code,
        they are stored and displayed in the order they were created, not by
        timestamp (which can be unreliable for variables created in the same millisecond).
        """
        # Create a sample AgentState
        state = AgentState(
            input="test task",
            url="",
        )

        # Code that creates multiple variables in sequence
        # Order: var1, var2, var3, var4
        code = """var1 = "first"
var2 = ["second", "item"]
var3 = {"third": "value"}
var4 = var1 + " -> " + str(var2)
print(f"Created: {var1}, {var2}, {var3}, {var4}")
"""

        # Empty locals dict
        _locals = {}

        # Execute the code
        output, new_vars = await eval_with_tools_async(
            code=code,
            _locals=_locals,
            state=state,
            thread_id=None,
            apps_list=None,
        )

        # Verify all variables were created
        expected_vars = ["var1", "var2", "var3", "var4"]
        for var_name in expected_vars:
            assert var_name in new_vars, f"{var_name} should be in new_vars"
            assert state.variables_manager.get_variable(var_name) is not None, (
                f"{var_name} should be in variables_manager"
            )

        # Validate creation order in new_vars dictionary
        new_var_names = list(new_vars.keys())
        assert new_var_names == expected_vars, f"Expected order {expected_vars}, got {new_var_names}"

        # Validate creation order in variables_manager
        all_var_names = state.variables_manager.get_variable_names()
        indices = {var: all_var_names.index(var) for var in expected_vars}

        # Verify each variable comes before the next one
        for i in range(len(expected_vars) - 1):
            current_var = expected_vars[i]
            next_var = expected_vars[i + 1]
            assert indices[current_var] < indices[next_var], (
                f"{current_var} (index {indices[current_var]}) should come before {next_var} (index {indices[next_var]})"
            )

        # Validate order in summary (should match creation order)
        summary = state.variables_manager.get_variables_summary()
        positions = {var: summary.find(f"## {var}") for var in expected_vars}

        # Verify each variable appears before the next one in summary
        for i in range(len(expected_vars) - 1):
            current_var = expected_vars[i]
            next_var = expected_vars[i + 1]
            assert positions[current_var] < positions[next_var], (
                f"{current_var} should appear before {next_var} in summary"
            )

    async def test_variable_creation_order_with_existing_vars(self):
        """
        Test that new variables maintain creation order even when existing variables are present.
        """
        # Create a sample AgentState
        state = AgentState(
            input="test task",
            url="",
        )

        # Add existing variables
        state.variables_manager.add_variable("existing1", name="existing_var1")
        state.variables_manager.add_variable("existing2", name="existing_var2")

        # Code that creates new variables in sequence
        code = """new_var1 = "first_new"
new_var2 = ["second_new"]
new_var3 = new_var1 + " -> " + str(new_var2)
print(new_var3)
"""

        # Pass existing variables in locals
        _locals = {"existing_var1": "existing1", "existing_var2": "existing2"}

        # Execute the code
        output, new_vars = await eval_with_tools_async(
            code=code,
            _locals=_locals,
            state=state,
            thread_id=None,
            apps_list=None,
        )

        # Verify new variables were created
        expected_new_vars = ["new_var1", "new_var2", "new_var3"]
        for var_name in expected_new_vars:
            assert var_name in new_vars, f"{var_name} should be in new_vars"

        # Validate creation order in new_vars
        new_var_names = list(new_vars.keys())
        assert new_var_names == expected_new_vars, f"Expected order {expected_new_vars}, got {new_var_names}"

        # Validate that new variables are added after existing ones
        all_var_names = state.variables_manager.get_variable_names()
        existing_indices = {
            "existing_var1": all_var_names.index("existing_var1"),
            "existing_var2": all_var_names.index("existing_var2"),
        }
        new_indices = {var: all_var_names.index(var) for var in expected_new_vars}

        # All new variables should come after existing ones
        for existing_var, existing_idx in existing_indices.items():
            for new_var, new_idx in new_indices.items():
                assert new_idx > existing_idx, (
                    f"New variable {new_var} (index {new_idx}) should come after existing {existing_var} (index {existing_idx})"
                )

        # Validate order among new variables themselves
        for i in range(len(expected_new_vars) - 1):
            current_var = expected_new_vars[i]
            next_var = expected_new_vars[i + 1]
            assert new_indices[current_var] < new_indices[next_var], (
                f"{current_var} should come before {next_var}"
            )

    async def test_variable_creation_order_multiple_sequential_creations(self):
        """
        Test that variables created in multiple sequential code executions
        maintain their relative creation order.
        """
        # Create a sample AgentState
        state = AgentState(
            input="test task",
            url="",
        )

        # First code execution: creates var1 and var2
        code1 = """var1 = "first"
var2 = "second"
print("Created var1 and var2")
"""

        _locals1 = {}

        output1, new_vars1 = await eval_with_tools_async(
            code=code1,
            _locals=_locals1,
            state=state,
            thread_id=None,
            apps_list=None,
        )

        # Second code execution: creates var3 and var4
        code2 = """var3 = "third"
var4 = "fourth"
print("Created var3 and var4")
"""

        _locals2 = {}

        output2, new_vars2 = await eval_with_tools_async(
            code=code2,
            _locals=_locals2,
            state=state,
            thread_id=None,
            apps_list=None,
        )

        # Verify all variables exist
        all_vars = state.variables_manager.get_variable_names()
        assert "var1" in all_vars
        assert "var2" in all_vars
        assert "var3" in all_vars
        assert "var4" in all_vars

        # Validate order: var1, var2 should come before var3, var4
        var1_idx = all_vars.index("var1")
        var2_idx = all_vars.index("var2")
        var3_idx = all_vars.index("var3")
        var4_idx = all_vars.index("var4")

        assert var1_idx < var2_idx < var3_idx < var4_idx, (
            f"Expected order: var1 ({var1_idx}) < var2 ({var2_idx}) < var3 ({var3_idx}) < var4 ({var4_idx})"
        )

        # Validate order in summary
        summary = state.variables_manager.get_variables_summary()
        var1_pos = summary.find("## var1")
        var2_pos = summary.find("## var2")
        var3_pos = summary.find("## var3")
        var4_pos = summary.find("## var4")

        assert var1_pos < var2_pos < var3_pos < var4_pos, (
            "Variables should appear in order: var1, var2, var3, var4"
        )

    async def test_results_is_last_variable_with_missing_dependencies(self):
        """
        Test that validates 'results' is the last variable in the summary when code
        uses missing variables and functions (with dummy implementations).

        This test validates:
        1. 'results' should be the LAST variable in the summary (final output)
        2. Missing variable 'contacts_content' is provided in _locals
        3. Missing functions are provided as dummy implementations in _locals
        4. Variables appearing in the last print statement are moved to the end
        """
        # Create a sample AgentState
        state = AgentState(
            input="test task",
            url="",
        )

        # Dummy async function implementations
        async def dummy_crm_get_contacts_contacts_get(email: str):
            """Dummy function for crm_get_contacts_contacts_get."""
            return {"items": [{"first_name": "John", "last_name": "Doe", "account_id": 123}]}

        async def dummy_crm_get_account_accounts_account_id_get(account_id: int):
            """Dummy function for crm_get_account_accounts_account_id_get."""
            return {"id": account_id, "name": "Test Account"}

        # Code that creates variables in sequence, with 'results' as the last one
        code = """import json

# Parse the email list from the provided variable
email_lines = contacts_content.get("result", "").splitlines()
emails = [email.strip() for email in email_lines if email.strip()]

results = []

for email in emails:
    # Query contacts by email
    contact_response = await crm_get_contacts_contacts_get(email=email)
    contact_items = contact_response.get("items", [])
    
    if contact_items:
        contact = contact_items[0]  # assume first match is the desired one
        contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
        account_id = contact.get("account_id")
        
        # Retrieve associated account details if account_id is present
        if account_id is not None:
            account = await crm_get_account_accounts_account_id_get(account_id=account_id)
        else:
            account = None
        
        results.append({
            "email": email,
            "contact_name": contact_name,
            "account": account
        })
    else:
        # No contact found for this email
        results.append({
            "email": email,
            "contact_name": None,
            "account": None,
            "note": "Contact not found"
        })

# Print the aggregated results
print(json.dumps(results, indent=2))
"""

        # Provide missing variable and functions in _locals
        _locals = {
            "contacts_content": {"result": "test@example.com\nanother@example.com"},
            "crm_get_contacts_contacts_get": dummy_crm_get_contacts_contacts_get,
            "crm_get_account_accounts_account_id_get": dummy_crm_get_account_accounts_account_id_get,
        }

        # Execute the code
        output, new_vars = await eval_with_tools_async(
            code=code,
            _locals=_locals,
            state=state,
            thread_id=None,
            apps_list=None,
        )

        # Key variables that should be created (excluding loop variables)
        key_vars = ["email_lines", "emails", "results"]

        # Verify all key variables were created
        for var_name in key_vars:
            assert var_name in new_vars, f"{var_name} should be in new_vars"
            assert state.variables_manager.get_variable(var_name) is not None, (
                f"{var_name} should be in variables_manager"
            )

        # Validate creation order in new_vars dictionary
        new_var_names = list(new_vars.keys())

        # Verify key variables exist and 'results' is the last key variable
        key_var_indices = {var: new_var_names.index(var) for var in key_vars if var in new_var_names}

        # Validate that 'results' comes after 'email_lines' and 'emails'
        assert key_var_indices["email_lines"] < key_var_indices["emails"], (
            "'email_lines' should come before 'emails'"
        )
        assert key_var_indices["emails"] < key_var_indices["results"], "'emails' should come before 'results'"

        # Validate that 'results' is the last meaningful variable (may have loop vars after, but results should be last key var)
        # Find the last key variable in the list
        last_key_var_idx = max(key_var_indices.values())
        last_key_var = [var for var, idx in key_var_indices.items() if idx == last_key_var_idx][0]
        assert last_key_var == "results", f"'results' should be the last key variable, but got {last_key_var}"

        # Validate creation order in variables_manager
        all_var_names = state.variables_manager.get_variable_names()
        key_var_indices_in_manager = {var: all_var_names.index(var) for var in key_vars}

        # Verify each key variable comes before the next one
        assert key_var_indices_in_manager["email_lines"] < key_var_indices_in_manager["emails"], (
            "'email_lines' should come before 'emails' in variables_manager"
        )
        assert key_var_indices_in_manager["emails"] < key_var_indices_in_manager["results"], (
            "'emails' should come before 'results' in variables_manager"
        )

        # Validate order in summary (should match creation order)
        summary = state.variables_manager.get_variables_summary()
        key_var_positions = {var: summary.find(f"## {var}") for var in key_vars}

        # Get all variable names from summary to find the last one
        import re

        all_vars_in_summary = re.findall(r'## (\w+)', summary)

        # Verify each key variable appears before the next one in summary
        assert key_var_positions["email_lines"] < key_var_positions["emails"], (
            "'email_lines' should appear before 'emails' in summary"
        )
        assert key_var_positions["emails"] < key_var_positions["results"], (
            "'emails' should appear before 'results' in summary"
        )

        # CRITICAL: Verify 'results' is the LAST variable in the summary
        # This validates that 'results' (the final output) appears after all other variables
        # including loop variables like 'email', 'contact_response', etc.
        assert all_vars_in_summary[-1] == "results", (
            f"'results' should be the LAST variable in summary, but got '{all_vars_in_summary[-1]}'. "
            f"All variables in order: {all_vars_in_summary}"
        )

        # Also verify 'results' appears after all other key variables in summary
        results_pos = key_var_positions["results"]
        for var in ["email_lines", "emails"]:
            assert key_var_positions[var] < results_pos, f"{var} should appear before 'results' in summary"
