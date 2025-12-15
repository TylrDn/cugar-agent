import asyncio
import unittest
import uuid

from system_tests.e2e.base_crm_test import BaseCRMTestServerStream
from system_tests.e2e.digital_sales_test_helpers import DigitalSalesTestHelpers


class TestCRMHF_Examples(BaseCRMTestServerStream):
    """
    Test class for CRM example utterances from frontend.
    Tests 4 different use cases with mode="hf" (no-email and read-only).
    """

    mode = "hf"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helpers = DigitalSalesTestHelpers()
        self.thread_id = None

    async def asyncSetUp(self):
        """Set up test environment and generate thread ID."""
        await super().asyncSetUp()
        self.thread_id = str(uuid.uuid4())
        print(f"\n=== Test thread ID: {self.thread_id} ===")

    async def test_filter_contacts_and_calculate_revenue_percentile(self):
        """
        Test use case 1: Filter contacts from contacts.txt, retrieve account details,
        calculate revenue percentile, and draft email from template.
        """
        print(f"Running test with thread ID: {self.thread_id}")

        query = """From the list of emails in the file contacts.txt, please filter those who exist in the CRM application. For the filtered contacts, retrieve their name and their associated account name, and calculate their account's revenue percentile across all accounts. Finally, draft a an email based on email_template.md template summarizing the result and show it to me"""

        all_events = await self.run_task(query, thread_id=self.thread_id)

        self._assert_answer_event(
            all_events,
            expected_keywords=[
                "sarah",
                "dorothy",
                "ruth",
                "Account Performance Update - Q1 2026",
                "sharon",
            ],
        )

        print("\n--- Sleeping for 10 seconds to allow traces to save ---")
        await asyncio.sleep(10)
        print("--- Sleep complete ---")

    async def test_show_users_in_crm_system(self):
        """
        Test use case 2: Show which users from contacts.txt belong to the CRM system.
        """
        print(f"Running test with thread ID: {self.thread_id}")

        query = "from contacts.txt show me which users belong to the crm system"

        all_events = await self.run_task(query, thread_id=self.thread_id)

        self._assert_answer_event(
            all_events,
            expected_keywords=[
                "sarah",
                "dorothy",
                "ruth",
                "sharon",
            ],
        )

        print("\n--- Sleeping for 10 seconds to allow traces to save ---")
        await asyncio.sleep(10)
        print("--- Sleep complete ---")

    async def test_what_is_cuga(self):
        """
        Test use case 3: Knowledge retrieval about CUGA from workspace documentation.
        """
        print(f"Running test with thread ID: {self.thread_id}")

        query = "What is CUGA?"

        all_events = await self.run_task(query, thread_id=self.thread_id)

        self._assert_answer_event(
            all_events,
            expected_keywords=["cuga", "configurable", "generalist", "agent"],
        )

        print("\n--- Sleeping for 10 seconds to allow traces to save ---")
        await asyncio.sleep(10)
        print("--- Sleep complete ---")

    async def test_playbook_execution(self):
        """
        Test use case 4: Automated playbook execution from markdown instructions.
        """
        print(f"Running test with thread ID: {self.thread_id}")

        query = "./cuga_workspace/cuga_playbook.md"

        all_events = await self.run_task(query, thread_id=self.thread_id)

        self._assert_answer_event(
            all_events,
            expected_keywords=["start tour", "middle pane", "right pane"],
        )

        print("\n--- Sleeping for 10 seconds to allow traces to save ---")
        await asyncio.sleep(10)
        print("--- Sleep complete ---")


if __name__ == "__main__":
    unittest.main()
