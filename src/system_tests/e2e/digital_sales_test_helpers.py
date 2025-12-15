"""
Common test methods for digital sales test cases.
"""


class DigitalSalesTestHelpers:
    """
    Helper class containing common test methods for digital sales tests.
    """

    async def test_get_top_account_by_revenue_stream(self, test_instance, mode_suffix):
        """
        Test getting the top account by revenue from my accounts.
        Ground Truth: The top account by revenue should be Andromeda Inc.
        """
        query = "get top account by revenue from my accounts only"
        all_events = await test_instance.run_task(query)
        test_instance._assert_answer_event(all_events, expected_keywords=["Andromeda"])

    async def test_list_my_accounts(self, test_instance, mode_suffix):
        """
        Test listing all my accounts and how many are there.
        Ground Truth: There should be 50 accounts.
        """
        query = "list all my accounts, how many are there?"
        all_events = await test_instance.run_task(query)
        if mode_suffix == "fast":
            # Since we are using the fast mode, final answer returns also variables
            test_instance._assert_answer_event(
                all_events,
                expected_keywords=[
                    "50",
                ],
            )
        test_instance._assert_answer_event(all_events, expected_keywords=["50"])

    async def test_find_vp_sales_active_high_value_accounts(self, test_instance, mode_suffix):
        """
        Test finding Vice President of Sales in Active, Tech Transformation Accounts.
        Ground Truth: The final list of contacts should contain Fiona Garcia, Ethan Martinez, Helen Wilson, and Helen Garcia.
        """
        query = "Get the names of 'Vice President of Sales' contacts for Tech Transformation campaign."
        all_events = await test_instance.run_task(query)
        test_instance._assert_answer_event(
            all_events, expected_keywords=["Fiona Garcia", "Ethan Martinez", "Helen Wilson", "Helen Garcia"]
        )

    async def test_crm_contacts_followup(self, test_instance, mode_suffix):
        """
        Test CRM contacts query with follow-up questions.
        Ground Truth:
        - First query: List users from contacts.txt that belong to CRM system
        - Second query (followup): Show details of first one - should return Sarah Bell and her email sarah.bell@gammadeltainc.partners.org
        - Third query (followup): How many employees work at her account's company - should return 4,260 or 4260 employees

        Uses a single thread ID across all queries to maintain conversation context.
        """
        import uuid

        # Generate a unique thread ID for this test session
        thread_id = str(uuid.uuid4())
        print(f"\n=== Starting CRM contacts followup test with thread ID: {thread_id} ===")

        # First query
        query = "from contacts.txt show me which users belong to the crm system"
        all_events = await test_instance.run_task(query, thread_id=thread_id)
        test_instance._assert_answer_event(all_events)

        # First followup - using same thread ID
        followup_query = "show me details of first one"
        all_followup_events = await test_instance.run_task(followup_query, thread_id=thread_id)
        test_instance._assert_answer_event(
            all_followup_events, expected_keywords=["Sarah", "sarah.bell@gammadeltainc.partners.org"]
        )

        # Second followup - using same thread ID
        second_followup_query = "how many employee's work at her account's company?"
        all_second_followup_events = await test_instance.run_task(second_followup_query, thread_id=thread_id)
        answer_event = next((e for e in all_second_followup_events if e.get("event") == "Answer"), None)
        test_instance.assertIsNotNone(answer_event, "The 'Answer' event was not found in the stream.")
        answer_str = str(answer_event.get("data", "")).lower()
        has_employee_count = "4,260" in answer_str or "4260" in answer_str
        test_instance.assertTrue(
            has_employee_count, f"Answer does not contain employee count '4,260' or '4260'. Got: {answer_str}"
        )
