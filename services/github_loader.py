import os
import shutil
import subprocess
from pathlib import Path


REPOS_DIR = Path("data/repos")


def load_github_repo(repo_url: str) -> str:

    repo_name = repo_url.rstrip("/").split("/")[-1]

    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    repo_path = REPOS_DIR / repo_name

    if repo_path.exists():

        def remove_readonly(func, path, exc_info):
            os.chmod(path, 0o777)
            func(path)

        shutil.rmtree(repo_path, onerror=remove_readonly)

    REPOS_DIR.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["git", "clone", repo_url, str(repo_path)],
        check=True
    )

    return str(repo_path)