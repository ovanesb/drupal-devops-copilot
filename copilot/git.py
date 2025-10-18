# copilot/git.py
import git
import os

repo = None

def init_repo():
    global repo
    repo = git.Repo(os.getcwd())
    print("🔧 Repo initialized.")

def create_feature_branch(task_id):
    branch_name = f"feature/{task_id}"
    repo.git.checkout("main")
    repo.git.pull()
    if branch_name in repo.heads:
        repo.git.checkout(branch_name)
    else:
        repo.git.checkout("-b", branch_name)
    print(f"🌿 Switched to branch: {branch_name}")

def commit_changes(task_id, file_path):
    repo.git.add(file_path)
    repo.git.commit(m=f"Add notes for task {task_id}")
    repo.git.push("--set-upstream", "origin", repo.active_branch.name)
    print(f"📤 Changes committed and pushed for {file_path}")
