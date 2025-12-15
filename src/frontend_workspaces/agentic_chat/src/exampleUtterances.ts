export interface ExampleUtterance {
  text: string;
  reason: string;
}

export const exampleUtterances: ExampleUtterance[] = [
  {
    text: "From the list of emails in the file contacts.txt, please filter those who exist in the CRM application. For the filtered contacts, retrieve their name and their associated account name, and calculate their account's revenue percentile across all accounts. Finally, draft a an email based on email_template.md template summarizing the result and show it to me",
    reason: "Multi-step workflow: file reading, API filtering, data analysis, and content generation"
  },
  {
    text: "from contacts.txt show me which users belong to the crm system",
    reason: "Iterative task execution with dynamic followup planning"
  },
  {
    text: "./cuga_workspace/cuga_playbook.md",
    reason: "Driving agent behavior from playbooks: learn how CUGA uses tools and variables in this demo"
  },
  {
    text: "What is CUGA?",
    reason: "CUGA answers questions about itself from documentation"
  }
];

