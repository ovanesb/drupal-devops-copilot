# copilot/task_runner.py

import os
from copilot.git import init_repo, create_feature_branch, commit_changes
from copilot.drush import run_drush_status
from copilot.jira import fetch_jira_task

def run_task(task_id: str):
    print(f"📡 Fetching Jira task: {task_id}")
    task = fetch_jira_task(task_id)

    if not task:
        print("❌ Task not found or failed to fetch.")
        return

    print(f"📝 {task['summary']}")
    print(f"📄 {task['description']}")

    init_repo()

    # ✅ Make sure notes directory exists
    notes_dir = "notes"
    os.makedirs(notes_dir, exist_ok=True)

    # 🗂 Create markdown file from Jira content
    filename = os.path.join(notes_dir, f"{task_id}.md")
    with open(filename, 'w') as f:
        f.write(f"# {task['summary']}\n\n{task['description']}\n")

    create_feature_branch(task_id)
    commit_changes(task_id, filename)

    run_drush_status()

    print("✅ Co-Pilot finished the task.")
