import io
import os
import creds

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from loguru import logger

def upload_png_to_drive(
    image_path: str,
    drive_folder_id: str = None,
    service_account_path: str = creds.gspread) -> str:
    """
    Uploads a PNG image to Google Drive using a service account.

    Args:
        image_path: Path to the PNG image file.
        drive_folder_id: (Optional) ID of the folder in Google Drive to upload to.
            If None, the image will be uploaded to the root folder.
        service_account_path: (Optional) Path to the service account JSON file.
            Defaults to "service_account.json".

    Returns:
        The ID of the uploaded file in Google Drive, or None on error.

    Raises:
        FileNotFoundError: If the image file or service account file does not exist.
        Exception: For other errors during the upload process.
    """
    # Validate file paths
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    if not os.path.exists(service_account_path):
        raise FileNotFoundError(
            f"Service account file not found: {service_account_path}"
        )

    # Set up credentials
    SCOPES = ["https://www.googleapis.com/auth/drive.file"]
    try:
        credentials = service_account.Credentials.from_service_account_file(
            service_account_path, scopes=SCOPES
        )
    except Exception as e:
        raise Exception(f"Error setting up credentials: {e}")

    # Build the Drive service
    try:
        service = build("drive", "v3", credentials=credentials)
    except Exception as e:
        raise Exception(f"Error building Drive service: {e}")

    # Prepare file metadata
    file_name = os.path.basename(image_path)
    mime_type = "image/png"
    file_metadata = {"name": file_name, "mimeType": mime_type}
    if drive_folder_id:
        file_metadata["parents"] = [drive_folder_id]

    # Create media upload object
    try:
        with open(image_path, "rb") as image_file:
            media = MediaIoBaseUpload(
                image_file, mimetype=mime_type, resumable=True
            )

            # Check if a file with the same name exists and delete it
            try:
                query = f"name='{file_name}'"
                if drive_folder_id:
                    query += f" and '{drive_folder_id}' in parents"
                results = (
                    service.files()
                    .list(q=query, fields="files(id)")
                    .execute()
                )
                files = results.get("files", [])
                if files:
                    for file in files:
                        service.files().delete(fileId=file["id"]).execute()
                        logger.info(f"File with name '{file_name}' already exists. Deleted existing file (ID: {file['id']}).")
            except Exception as e:
                logger.error(f"Error checking and/or deleting existing file: {e}")

            # Upload the file
            try:
                file = (
                    service.files()
                    .create(body=file_metadata, media_body=media, fields="id,webViewLink")
                    .execute()
                )
                logger.info(f"File uploaded successfully. File ID: {file.get('id')}\nLink: {file.get('webViewLink')}")
                # Set permission to allow anyone with the link to view the image
                permission = {"role": "reader", "type": "anyone"}
                service.permission().create(fileId=file_id, body=permission).execute()
                return file.get("webViewLink")
            except Exception as e:
                logger.error(f"Error uploading file: {e}")
                return None

    except Exception as e:
        raise Exception(f"Error creating media upload object: {e}")

