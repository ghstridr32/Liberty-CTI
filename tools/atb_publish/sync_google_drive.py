"""
sync_google_drive.py -- Sync the local "ATB Archive/<year>/" tree to
Google Drive at:  Liberty CTI/Alamo Threat Brief Archive/<year>/

IMPORTANT / KNOWN LIMITATION
-----------------------------
This script talks to the Google Drive API directly using a service account,
so it can run completely unattended (e.g. from a scheduled task with no
Claude session involved). That requires Google credentials that only the
Liberty CTI Google Workspace admin can provision -- this script deliberately
does NOT embed, generate, or guess at any credential. It reads a path to a
service-account key JSON file from the GOOGLE_SERVICE_ACCOUNT_JSON
environment variable and does nothing else with secrets.

If that environment variable is not set (the default, out of the box), sync
fails closed and clearly: it prints "DRIVE SYNC FAILED -- credentials not
configured" and exits non-zero. It never silently skips and never pretends
the archive is on Drive when it isn't. It also never blocks DOCX/PDF/HTML
archival, which succeeds independently of Drive.

Setup (one-time, done by a human with Drive admin access):
  1. Create a Google Cloud service account with Drive API access.
  2. Share the "Liberty CTI/Alamo Threat Brief Archive" Drive folder with
     that service account's email address (Editor access).
  3. Download the service account's JSON key and store it outside the repo.
  4. Set the environment variable before running publish_atb.py / archive_all.py:
       setx GOOGLE_SERVICE_ACCOUNT_JSON "C:\\secure\\path\\lcti-drive-sa.json"
  5. pip install google-api-python-client google-auth

Idempotency: files are matched by name under their parent folder; an existing
file is updated in place (new revision), never duplicated. Folders are
created only if they don't already exist under their parent.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

DRIVE_ROOT_NAME = "Liberty CTI"
ARCHIVE_FOLDER_NAME = "Alamo Threat Brief Archive"

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_ROOT = REPO_ROOT / "ATB Archive"

CREDENTIALS_ENV = "GOOGLE_SERVICE_ACCOUNT_JSON"


class DriveSyncUnavailable(Exception):
    pass


def _get_drive_service():
    cred_path = os.environ.get(CREDENTIALS_ENV)
    if not cred_path or not Path(cred_path).exists():
        raise DriveSyncUnavailable(
            f"DRIVE SYNC FAILED -- credentials not configured. "
            f"Set the {CREDENTIALS_ENV} environment variable to a Google "
            f"service-account JSON key path. See sync_google_drive.py module "
            f"docstring for one-time setup steps."
        )
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as e:
        raise DriveSyncUnavailable(
            "DRIVE SYNC FAILED -- google-api-python-client / google-auth not "
            "installed. Run: pip install google-api-python-client google-auth"
        ) from e

    creds = service_account.Credentials.from_service_account_file(
        cred_path, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)


def _find_or_create_folder(service, name: str, parent_id: str | None) -> str:
    query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    resp = service.files().list(q=query, fields="files(id, name)").execute()
    files = resp.get("files", [])
    if files:
        return files[0]["id"]
    metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]
    created = service.files().create(body=metadata, fields="id").execute()
    return created["id"]


def _upsert_file(service, local_path: Path, parent_id: str):
    from googleapiclient.http import MediaFileUpload

    query = f"name = '{local_path.name}' and trashed = false and '{parent_id}' in parents"
    resp = service.files().list(q=query, fields="files(id, name)").execute()
    existing = resp.get("files", [])
    media = MediaFileUpload(str(local_path), resumable=True)
    if existing:
        service.files().update(fileId=existing[0]["id"], media_body=media).execute()
        return "updated"
    metadata = {"name": local_path.name, "parents": [parent_id]}
    service.files().create(body=metadata, media_body=media, fields="id").execute()
    return "created"


def sync_year(year: int) -> dict:
    year_dir = ARCHIVE_ROOT / str(year)
    if not year_dir.exists():
        return {"status": "NO_LOCAL_ARCHIVE", "year": year}

    try:
        service = _get_drive_service()
    except DriveSyncUnavailable as e:
        print(str(e), file=sys.stderr)
        return {"status": "DRIVE SYNC FAILED", "year": year, "reason": str(e)}

    root_id = _find_or_create_folder(service, DRIVE_ROOT_NAME, None)
    archive_id = _find_or_create_folder(service, ARCHIVE_FOLDER_NAME, root_id)
    year_id = _find_or_create_folder(service, str(year), archive_id)

    synced_files = []
    for item in sorted(year_dir.iterdir()):
        if item.is_file():
            action = _upsert_file(service, item, year_id)
            synced_files.append({"file": item.name, "action": action})
        elif item.is_dir():
            issue_id = _find_or_create_folder(service, item.name, year_id)
            for f in sorted(item.iterdir()):
                if f.is_file() and f.name != "meta.json":
                    action = _upsert_file(service, f, issue_id)
                    synced_files.append({"file": f"{item.name}/{f.name}", "action": action})

    return {"status": "OK", "year": year, "synced_files": synced_files}


def main():
    if len(sys.argv) < 2:
        print("usage: sync_google_drive.py <year>", file=sys.stderr)
        sys.exit(1)
    result = sync_year(int(sys.argv[1]))
    print(result["status"], "--", result.get("reason") or f"{len(result.get('synced_files', []))} file(s) synced")
    sys.exit(0 if result["status"] == "OK" else 4)


if __name__ == "__main__":
    main()
