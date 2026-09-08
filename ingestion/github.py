import os
import subprocess


def clone_repository(repo_url: str, destination: str) -> str:
    """
    Clone a GitHub repository into the given destination.
    """

    if os.path.exists(destination):
        raise FileExistsError(
            f"Destination already exists: {destination}"
        )

    subprocess.run(
        ["git", "clone", repo_url, destination],
        check=True,
    )

    return destination


if __name__ == "__main__":
    repo_url = "https://github.com/lakshr2004/Monetrik-FinanceSystem"
    destination = "data/monetrik-financesystem"

    path = clone_repository(repo_url, destination)

    print(f"Repository cloned successfully: {path}")