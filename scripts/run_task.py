# scripts/run_task.py  (excerpt)
from copilot.ai.ai_generator import AIGenerator
from copilot.prompts.registry import PromptRegistry
from copilot.context.context_builder import ContextBuilder
from copilot.context.providers.jira_provider import JiraProvider
from copilot.context.providers.git_provider import GitProvider
from copilot.context.providers.drush_provider import DrushProvider

# ... after you parse CLI args like `CCS-7`

registry = PromptRegistry()
context_builder = ContextBuilder(
    jira=JiraProvider(client=YourJiraClient()),
    git=GitProvider(),
    drush=DrushProvider(),
)
ai = AIGenerator(registry, context_builder)

if jira_key:
    output = ai.generate(
        prompt_id="jira_summary",
        version="latest",
        inputs={"unknowns": "- environment not specified"},
        context_spec={
            "jira": {"key": jira_key},
            "git": {"diff": True, "base": "origin/develop", "head": "HEAD"},
            "drush": {"status": True},
        },
        agent="jira_triage",
        temperature=0.2,
    )
    print(output)