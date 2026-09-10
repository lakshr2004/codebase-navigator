from services.github_loader import load_github_repo
from services.indexer import index_repository


def load_and_index_repository(repo_url: str):

    # Step 1: Clone repository
    repository_path = load_github_repo(repo_url)

    # Step 2: Index repository
    index_repository(repository_path)

    return repository_path