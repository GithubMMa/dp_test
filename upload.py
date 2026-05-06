import os
import sys
import requests
import json
import time

# ==============================================================================
# Configuration Variables for upload.py
# ==============================================================================
# IMPORTANT: Replace these values with your actual GitHub credentials.
# For production, consider using environment variables to avoid hardcoding secrets.

GITHUB_TOKEN = "your_github_personal_access_token_here"
REPO_OWNER = "your_github_username_or_org"
REPO_NAME = "your_repository_name"
BRANCH_NAME = "main"  # or the target branch for beta testing

# Base URL for GitHub API
GITHUB_API_URL = "https://api.github.com"

# ==============================================================================
# Helper Functions
# ==============================================================================

def get_headers():
    """Returns the headers required for authenticated GitHub API requests."""
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }

def get_sha_for_branch(branch_name):
    """Fetches the commit SHA for the specified branch."""
    url = f"{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/branches/{branch_name}"
    response = requests.get(url, headers=get_headers())
    
    if response.status_code == 200:
        return response.json()['commit']['sha']
    else:
        print(f"Error fetching branch SHA: {response.status_code} - {response.text}")
        sys.exit(1)

def get_file_sha(path):
    """Fetches the SHA of a file at a specific path in the repository."""
    url = f"{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    response = requests.get(url, headers=get_headers())
    
    if response.status_code == 200:
        return response.json()['sha']
    elif response.status_code == 404:
        return None  # File does not exist
    else:
        print(f"Error fetching file SHA for {path}: {response.status_code}")
        return None

def upload_file(local_path, remote_path, branch_sha):
    """
    Uploads a file to the GitHub repository.
    Creates the file if it doesn't exist, or updates it if it does.
    """
    # Read file content in binary mode
    with open(local_path, 'rb') as f:
        content = f.read().decode('utf-8', errors='ignore')
    
    # Get current SHA if file exists
    current_sha = get_file_sha(remote_path)
    
    payload = {
        "message": f"Update {remote_path} via dp_test upload",
        "content": content,
        "branch": BRANCH_NAME,
        "sha": current_sha  # Required for updating existing files
    }
    
    url = f"{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{remote_path}"
    headers = get_headers()
    headers["Content-Type"] = "application/json"
    
    response = requests.put(url, headers=headers, json=payload)
    
    if response.status_code in [200, 201]:
        print(f"Successfully uploaded: {remote_path}")
        return True
    else:
        print(f"Failed to upload {remote_path}: {response.status_code} - {response.text}")
        return False

def create_directory(remote_path, branch_sha):
    """
    Creates an empty file in a directory to force its creation in Git.
    GitHub requires at least one file in a directory to track it.
    """
    # Create a placeholder file inside the directory
    placeholder_name = ".gitkeep"
    placeholder_path = f"{remote_path}/{placeholder_name}"
    
    payload = {
        "message": f"Create directory {remote_path}",
        "content": "",  # Empty content
        "branch": BRANCH_NAME,
        "sha": None  # No SHA needed for new files
    }
    
    url = f"{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{placeholder_path}"
    headers = get_headers()
    headers["Content-Type"] = "application/json"
    
    response = requests.put(url, headers=headers, json=payload)
    
    if response.status_code in [200, 201]:
        print(f"Created directory structure: {remote_path}")
        # Delete the placeholder file immediately to keep the repo clean
        delete_file(placeholder_path, branch_sha)
        return True
    else:
        print(f"Failed to create directory {remote_path}: {response.status_code} - {response.text}")
        return False

def delete_file(remote_path, branch_sha):
    """Deletes a file from the repository."""
    current_sha = get_file_sha(remote_path)
    if not current_sha:
        return True  # Already deleted or doesn't exist
        
    url = f"{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{remote_path}"
    payload = {
        "message": f"Delete {remote_path}",
        "sha": current_sha,
        "branch": BRANCH_NAME
    }
    
    headers = get_headers()
    headers["Content-Type"] = "application/json"
    
    response = requests.delete(url, headers=headers, json=payload)
    
    if response.status_code in [200, 204]:
        print(f"Deleted placeholder: {remote_path}")
        return True
    else:
        print(f"Failed to delete {remote_path}: {response.status_code}")
        return False

def sync_directory(local_dir, remote_base_path, branch_sha):
    """
    Recursively syncs a local directory to the remote repository.
    """
    # List all files in the local directory
    try:
        entries = os.listdir(local_dir)
    except FileNotFoundError:
        print(f"Local directory not found: {local_dir}")
        return

    for entry in entries:
        local_path = os.path.join(local_dir, entry)
        remote_path = f"{remote_base_path}/{entry}" if remote_base_path else entry
        
        if os.path.isdir(local_path):
            # If it's a directory, ensure it exists on GitHub, then recurse
            # We create the directory structure first
            create_directory(remote_path, branch_sha)
            # Recursively sync contents
            sync_directory(local_path, remote_path, branch_sha)
        elif os.path.isfile(local_path):
            # If it's a file, upload it
            upload_file(local_path, remote_path, branch_sha)
        else:
            print(f"Skipping unsupported file type: {local_path}")

def main():
    """Main execution function."""
    print("Starting dp_test upload process...")
    
    # Validate configuration
    if GITHUB_TOKEN == "your_github_personal_access_token_here":
        print("Error: Please configure GITHUB_TOKEN in upload.py")
        sys.exit(1)
    if REPO_OWNER == "your_github_username_or_org":
        print("Error: Please configure REPO_OWNER in upload.py")
        sys.exit(1)
    if REPO_NAME == "your_repository_name":
        print("Error: Please configure REPO_NAME in upload.py")
        sys.exit(1)

    # Define local directory to upload
    UPLOAD_DIR = "./upload"
    
    # Check if upload directory exists
    if not os.path.exists(UPLOAD_DIR):
        print(f"Error: Directory '{UPLOAD_DIR}' does not exist.")
        sys.exit(1)

    # Get the current SHA of the branch to ensure we are updating the latest version
    print(f"Fetching latest commit SHA for branch '{BRANCH_NAME}'...")
    branch_sha = get_sha_for_branch(BRANCH_NAME)
    
    # Start synchronization
    print(f"Syncing files from '{UPLOAD_DIR}' to '{REPO_OWNER}/{REPO_NAME}'...")
    sync_directory(UPLOAD_DIR, "", branch_sha)
    
    print("Upload process completed.")

if __name__ == "__main__":
    main()
