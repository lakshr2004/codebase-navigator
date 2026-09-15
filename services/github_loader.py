import os
import re
import shutil
import subprocess
import tempfile
import logging
from pathlib import Path

from core.config import get_runtime_config


logger = logging.getLogger(__name__)


REPOS_DIR = Path("data/repos")

_GITHUB_URL_RE = re.compile(
    r"^https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?$"
)


def validate_github_repo_url(repo_url: str) -> str:
    """Validate a GitHub repository URL before any git operation."""
    if not isinstance(repo_url, str):
        raise ValueError("GitHub repository URL must be a string")

    candidate = repo_url.strip()
    if not candidate:
        raise ValueError("GitHub repository URL cannot be empty")

    if not _GITHUB_URL_RE.match(candidate):
        raise ValueError(
            "GitHub repository URL must be a valid https://github.com/<owner>/<repo> URL"
        )

    return candidate


def load_github_repo(repo_url: str) -> str:
    """
    Clone a GitHub repository into data/repos.

    If the repository already exists, it is removed first
    and then cloned again.
    """
    repo_url = validate_github_repo_url(repo_url)

    url_parts = repo_url.rstrip("/").split("/")
    owner_name = url_parts[-2]
    repo_name = url_parts[-1]

    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    if not repo_name:
        raise ValueError("GitHub repository URL must include a repository name")

    destination_name = f"{owner_name}__{repo_name}"
    repo_path = REPOS_DIR / destination_name

    # Make sure repositories directory exists
    REPOS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary_path = Path(tempfile.mkdtemp(prefix=f".{destination_name}-", dir=REPOS_DIR))
    logger.info("Starting GitHub repository clone")

    def remove_readonly(func, path, exc_info):
        os.chmod(path, 0o777)
        func(path)

    try:
        subprocess.run(
            [
                "git",
                "clone",
                repo_url,
                str(temporary_path)
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=get_runtime_config()["github_clone_timeout_seconds"],
        )

        if repo_path.exists():
            shutil.rmtree(repo_path, onerror=remove_readonly)
        shutil.move(str(temporary_path), str(repo_path))

    except FileNotFoundError as e:
        logger.error("Git executable was not found during repository clone")
        raise ValueError("Git executable was not found; install Git and retry") from e
    except subprocess.TimeoutExpired as e:
        logger.error("GitHub repository clone timed out")
        raise ValueError("GitHub repository clone timed out") from e
    except subprocess.CalledProcessError as e:
        logger.error("GitHub repository clone failed")
        raise ValueError("GitHub repository clone failed; check the URL and access permissions") from e
    except OSError as e:
        logger.error("GitHub repository clone could not be completed")
        raise ValueError("GitHub repository clone could not be completed") from e
    finally:
        if temporary_path.exists():
            shutil.rmtree(temporary_path, onerror=remove_readonly)

    logger.info("GitHub repository clone completed")
    return str(repo_path)