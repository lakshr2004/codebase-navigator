import os
import shutil
import subprocess
from pathlib import Path


REPOS_DIR = Path("data/repos")


def load_github_repo(repo_url: str) -> str:
    """
    Clone a GitHub repository into data/repos.

    If the repository already exists, it is removed first
    and then cloned again.
    """

    repo_name = repo_url.rstrip("/").split("/")[-1]

    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    if not repo_name:
        raise ValueError("Invalid repository URL")

    repo_path = REPOS_DIR / repo_name

    # Remove existing repository
    if repo_path.exists():

        def remove_readonly(func, path, exc_info):
            os.chmod(path, 0o777)
            func(path)

        shutil.rmtree(
            repo_path,
            onerror=remove_readonly
        )

    # Make sure repositories directory exists
    REPOS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    try:
        subprocess.run(
            [
                "git",
                "clone",
                repo_url,
                str(repo_path)
            ],
            check=True,
            capture_output=True,
            text=True
        )

    except subprocess.CalledProcessError as e:
        raise ValueError(
            f"Failed to clone repository: {repo_url}"
        ) from e

    return str(repo_path)