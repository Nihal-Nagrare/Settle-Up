"""
Settle Up - Secure Payment Proof Storage & Validation Service
Handles file type validation (magic bytes), safe filename generation,
directory traversal prevention, file size limits, and secure disk storage.
"""

import os
import re
import base64
import secrets
import logging
from pathlib import Path
from flask import current_app
from .config import BASE_DIR

logger = logging.getLogger(__name__)

# Max file size: 5 MB (in bytes)
MAX_PROOF_SIZE_BYTES = 5 * 1024 * 1024

# Strict whitelist of allowed extensions and MIME types
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
ALLOWED_MIMETYPES = {'image/jpeg', 'image/png', 'image/webp'}

# Magic byte signatures for image formats
MAGIC_SIGNATURES = {
    'image/jpeg': [b'\xff\xd8\xff'],
    'image/png': [b'\x89PNG\r\n\x1a\n'],
    'image/webp': [b'RIFF']  # Note: Also verify 'WEBP' at index 8
}


def get_storage_provider():
    """
    Identifies the active storage provider.
    Returns: 's3', 'cloudinary', 'vercel_blob', or 'local'.
    In production, fails fast if local storage is selected or if no persistent provider is configured.
    """
    is_prod = False
    if current_app:
        is_prod = (
            current_app.config.get('ENV') == 'production' or
            os.getenv('FLASK_ENV', '').lower() == 'production'
        )
    else:
        is_prod = (os.getenv('FLASK_ENV', '').lower() == 'production')

    configured = os.getenv('STORAGE_PROVIDER', '').lower().strip()
    if configured:
        if is_prod and configured == 'local':
            raise RuntimeError(
                "CRITICAL CONFIGURATION ERROR: 'STORAGE_PROVIDER=local' is not permitted in production. "
                "Persistent object storage ('s3', 'cloudinary', or 'vercel_blob') is required on Vercel."
            )
        return configured

    if os.getenv('AWS_S3_BUCKET') or os.getenv('S3_BUCKET_NAME'):
        return 's3'
    if os.getenv('CLOUDINARY_URL') or os.getenv('CLOUDINARY_CLOUD_NAME'):
        return 'cloudinary'
    if os.getenv('BLOB_READ_WRITE_TOKEN'):
        return 'vercel_blob'

    if is_prod:
        raise RuntimeError(
            "CRITICAL CONFIGURATION ERROR: No persistent 'STORAGE_PROVIDER' configured in production. "
            "Persistent object storage ('s3', 'cloudinary', or 'vercel_blob') must be configured."
        )

    return 'local'


def get_upload_dir(app=None):
    """
    Retrieves and ensures creation of the secure upload directory for local storage.
    Automatically falls back to /tmp/uploads/proofs if the target filesystem is read-only (e.g. Vercel serverless).
    """
    if app:
        upload_dir = app.config.get('UPLOAD_FOLDER', str(BASE_DIR / 'uploads' / 'proofs'))
    elif current_app:
        upload_dir = current_app.config.get('UPLOAD_FOLDER', str(BASE_DIR / 'uploads' / 'proofs'))
    else:
        upload_dir = str(BASE_DIR / 'uploads' / 'proofs')

    upload_path = Path(upload_dir).resolve()
    try:
        upload_path.mkdir(parents=True, exist_ok=True)
        # Test directory writability
        test_file = upload_path / '.write_test'
        test_file.touch(exist_ok=True)
        test_file.unlink(missing_ok=True)
        return str(upload_path)
    except (PermissionError, OSError):
        # Fallback for serverless read-only filesystems (Vercel / AWS Lambda)
        tmp_upload_dir = Path('/tmp/uploads/proofs').resolve()
        try:
            tmp_upload_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return str(tmp_upload_dir)


def detect_image_type_from_magic_bytes(header_bytes):
    """
    Inspects leading bytes of file content to detect true image format.
    Prevents executable scripts (e.g. PHP/JS/HTML) renamed as images.
    """
    if not header_bytes or len(header_bytes) < 12:
        return None

    # Check JPEG
    if header_bytes.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'

    # Check PNG
    if header_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'

    # Check WebP (starts with 'RIFF' and contains 'WEBP' at bytes 8-12)
    if header_bytes.startswith(b'RIFF') and header_bytes[8:12] == b'WEBP':
        return 'image/webp'

    return None


def get_extension_for_mime(mime_type):
    """Maps safe MIME type to standard file extension."""
    mapping = {
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/webp': 'webp'
    }
    return mapping.get(mime_type, 'jpg')


def sanitize_identifier(ident):
    """Sanitizes room or settlement IDs to safe alphanumeric/underscore characters."""
    if not ident:
        return 'unknown'
    return re.sub(r'[^a-zA-Z0-9_-]', '', str(ident))[:32]


def generate_safe_filename(room_id, settlement_id, mime_type):
    """
    Generates a cryptographically random, collision-resistant, non-guessable filename.
    Never uses user-supplied filenames for disk storage.
    """
    clean_room = sanitize_identifier(room_id)
    clean_set = sanitize_identifier(settlement_id)
    ext = get_extension_for_mime(mime_type)
    random_token = secrets.token_hex(10)
    return f"proof_{clean_room}_{clean_set}_{random_token}.{ext}"


def _get_s3_client_and_bucket():
    """
    Constructs an authenticated boto3 S3 client and returns (client, bucket_name).
    Consistently applies AWS_REGION, AWS_S3_ENDPOINT_URL (for Cloudflare R2 / MinIO),
    and AWS credentials across upload, delete, and URL signing operations.
    """
    import boto3
    bucket = os.getenv('AWS_S3_BUCKET') or os.getenv('S3_BUCKET_NAME')
    if not bucket:
        raise ValueError("S3 storage configured but AWS_S3_BUCKET is not set.")

    region = os.getenv('AWS_REGION', 'us-east-1')
    endpoint_url = os.getenv('AWS_S3_ENDPOINT_URL')

    s3_kwargs = {'region_name': region}
    if endpoint_url:
        s3_kwargs['endpoint_url'] = endpoint_url
    if os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY'):
        s3_kwargs['aws_access_key_id'] = os.getenv('AWS_ACCESS_KEY_ID')
        s3_kwargs['aws_secret_access_key'] = os.getenv('AWS_SECRET_ACCESS_KEY')

    client = boto3.client('s3', **s3_kwargs)
    return client, bucket


def _get_s3_presigned_url(key, expires_in=900):
    """
    Generates a short-lived (default 15-minute) presigned URL for private S3 object.
    Ensures payment proofs remain private in bucket storage.
    """
    try:
        client, bucket = _get_s3_client_and_bucket()
        url = client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expires_in
        )
        return url
    except Exception as e:
        logger.error("Failed to generate presigned S3 URL for %s: %s", key, e)
        return None


def _upload_to_s3(file_bytes, safe_name, mime_type):
    """Uploads file bytes to AWS S3 or S3-compatible storage (e.g., Cloudflare R2). Private by default."""
    client, bucket = _get_s3_client_and_bucket()
    key = f"proofs/{safe_name}"

    # Stored privately without public ACL
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=file_bytes,
        ContentType=mime_type
    )

    region = os.getenv('AWS_REGION', 'us-east-1')
    endpoint_url = os.getenv('AWS_S3_ENDPOINT_URL')
    custom_domain = os.getenv('AWS_S3_CUSTOM_DOMAIN')
    if custom_domain:
        url = f"https://{custom_domain.rstrip('/')}/{key}"
    elif endpoint_url:
        url = f"{endpoint_url.rstrip('/')}/{bucket}/{key}"
    else:
        url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

    return url


def _upload_to_vercel_blob(file_bytes, safe_name, mime_type):
    """Uploads file bytes to Vercel Blob storage via REST API."""
    import requests
    token = os.getenv('BLOB_READ_WRITE_TOKEN')
    if not token:
        raise ValueError("Vercel Blob storage configured but BLOB_READ_WRITE_TOKEN is not set.")

    endpoint = f"https://blob.vercel-storage.com/{safe_name}?access=public"
    headers = {
        'Authorization': f"Bearer {token}",
        'x-api-version': '7',
        'Content-Type': mime_type
    }
    resp = requests.put(endpoint, data=file_bytes, headers=headers, timeout=15)
    resp.raise_for_status()
    blob_data = resp.json()
    return blob_data.get('url') or endpoint


def _upload_to_cloudinary(file_bytes, safe_name, mime_type):
    """Uploads file bytes to Cloudinary storage using signed upload if credentials are present, or upload preset."""
    import urllib.request
    import urllib.parse
    import hashlib
    import time
    import json

    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
    api_key = os.getenv('CLOUDINARY_API_KEY')
    api_secret = os.getenv('CLOUDINARY_API_SECRET')
    upload_preset = os.getenv('CLOUDINARY_UPLOAD_PRESET', 'settleup_proofs')

    # Try parsing from CLOUDINARY_URL: cloudinary://key:secret@cloud_name
    cloudinary_url = os.getenv('CLOUDINARY_URL')
    if cloudinary_url:
        match = re.match(r'cloudinary://([^:]+):([^@]+)@(.+)$', cloudinary_url)
        if match:
            api_key = api_key or match.group(1)
            api_secret = api_secret or match.group(2)
            cloud_name = cloud_name or match.group(3)

    if not cloud_name:
        raise ValueError("Cloudinary storage configured but CLOUDINARY_CLOUD_NAME is not set.")

    public_id = Path(safe_name).stem
    b64_content = base64.b64encode(file_bytes).decode('utf-8')
    data_uri = f"data:{mime_type};base64,{b64_content}"

    # If API key and secret are present, use signed upload
    if api_key and api_secret:
        timestamp = str(int(time.time()))
        to_sign = f"public_id={public_id}&timestamp={timestamp}{api_secret}"
        signature = hashlib.sha1(to_sign.encode('utf-8')).hexdigest()
        post_dict = {
            'file': data_uri,
            'public_id': public_id,
            'api_key': api_key,
            'timestamp': timestamp,
            'signature': signature
        }
    else:
        post_dict = {
            'file': data_uri,
            'upload_preset': upload_preset,
            'public_id': public_id
        }

    api_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
    payload = urllib.parse.urlencode(post_dict).encode('utf-8')

    req = urllib.request.Request(api_url, data=payload, method='POST')
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        return res.get('secure_url') or res.get('url')


def save_proof_file_bytes(file_bytes, room_id, settlement_id, original_filename=None, upload_dir=None):
    """
    Validates file content, size, and magic bytes, then writes to cloud object storage or local disk.
    
    Returns:
        dict: {
            'filename': safe_filename or public_url,
            'content_type': detected_mime,
            'size_bytes': len(file_bytes),
            'storage_path': full_storage_path or public_url
        }
    Raises:
        ValueError: If file is too large, invalid format, or fails verification.
    """
    if not file_bytes:
        raise ValueError("Uploaded proof file is empty.")

    size = len(file_bytes)
    if size > MAX_PROOF_SIZE_BYTES:
        raise ValueError(f"Proof file exceeds maximum allowed size of {MAX_PROOF_SIZE_BYTES // (1024*1024)}MB.")

    # Magic byte verification
    detected_mime = detect_image_type_from_magic_bytes(file_bytes[:16])
    if not detected_mime or detected_mime not in ALLOWED_MIMETYPES:
        raise ValueError("Invalid file format. Only valid JPEG, PNG, and WebP images are permitted.")

    safe_name = generate_safe_filename(room_id, settlement_id, detected_mime)
    provider = get_storage_provider()

    if provider == 's3':
        logger.info("Uploading payment proof to S3/R2: %s", safe_name)
        remote_url = _upload_to_s3(file_bytes, safe_name, detected_mime)
        return {
            'filename': remote_url,
            'content_type': detected_mime,
            'size_bytes': size,
            'storage_path': remote_url
        }
    elif provider == 'vercel_blob':
        logger.info("Uploading payment proof to Vercel Blob: %s", safe_name)
        remote_url = _upload_to_vercel_blob(file_bytes, safe_name, detected_mime)
        return {
            'filename': remote_url,
            'content_type': detected_mime,
            'size_bytes': size,
            'storage_path': remote_url
        }
    elif provider == 'cloudinary':
        logger.info("Uploading payment proof to Cloudinary: %s", safe_name)
        remote_url = _upload_to_cloudinary(file_bytes, safe_name, detected_mime)
        return {
            'filename': remote_url,
            'content_type': detected_mime,
            'size_bytes': size,
            'storage_path': remote_url
        }
    else:
        # Default: Local disk storage
        target_dir = upload_dir or get_upload_dir()
        dest_path = (Path(target_dir) / safe_name).resolve()

        # Directory traversal sanity check
        if not str(dest_path).startswith(str(Path(target_dir).resolve())):
            raise ValueError("Security violation: Invalid storage target path.")

        with open(dest_path, 'wb') as f:
            f.write(file_bytes)

        return {
            'filename': safe_name,
            'content_type': detected_mime,
            'size_bytes': size,
            'storage_path': str(dest_path)
        }


def save_proof_from_upload(file_storage, room_id, settlement_id, upload_dir=None):
    """
    Extracts and saves a payment proof from a Flask FileStorage object.
    """
    if not file_storage or not getattr(file_storage, 'filename', None):
        raise ValueError("No valid file uploaded.")

    file_bytes = file_storage.read()
    return save_proof_file_bytes(
        file_bytes,
        room_id=room_id,
        settlement_id=settlement_id,
        original_filename=file_storage.filename,
        upload_dir=upload_dir
    )


def save_proof_from_base64(base64_data, room_id, settlement_id, upload_dir=None):
    """
    Decodes and saves a base64 encoded proof string (e.g. data:image/png;base64,...).
    """
    if not base64_data or not isinstance(base64_data, str):
        raise ValueError("Invalid base64 proof payload.")

    clean_b64 = base64_data
    if ',' in clean_b64:
        clean_b64 = clean_b64.split(',', 1)[1]

    try:
        file_bytes = base64.b64decode(clean_b64)
    except Exception:
        raise ValueError("Malformed base64 image data.")

    return save_proof_file_bytes(
        file_bytes,
        room_id=room_id,
        settlement_id=settlement_id,
        upload_dir=upload_dir
    )


def get_proof_url(proof_file_ref, expires_in=900):
    """
    Returns public/direct or signed HTTP(S) URL if the proof is hosted on remote cloud object storage,
    or None if it is stored locally on disk.
    For S3, generates a short-lived (default 15-minute) presigned URL to keep private payment proofs protected.
    """
    if not proof_file_ref or not isinstance(proof_file_ref, str):
        return None

    ref = proof_file_ref.strip()

    # If S3 key or S3 URL, generate presigned URL to preserve privacy
    match = re.search(r'proofs/[a-zA-Z0-9_.-]+', ref)
    if match and (os.getenv('AWS_S3_BUCKET') or os.getenv('S3_BUCKET_NAME')):
        key = match.group(0)
        signed_url = _get_s3_presigned_url(key, expires_in=expires_in)
        if signed_url:
            return signed_url

    if ref.startswith('http://') or ref.startswith('https://'):
        return ref

    return None


def resolve_proof_file_path(filename, upload_dir=None):
    """
    Safely resolves the absolute path for a local proof filename.
    Guarantees that path cannot escape the private upload folder (anti-traversal).
    Returns (resolved_path_str, exists_bool).
    """
    if not filename or not isinstance(filename, str):
        return None, False

    # Remote URLs are handled via get_proof_url, not local filesystem
    if filename.startswith('http://') or filename.startswith('https://'):
        return None, False

    # Prevent filename from containing path separators or null bytes
    if '/' in filename or '\\' in filename or '\x00' in filename or '..' in filename:
        return None, False

    target_dir = Path(upload_dir or get_upload_dir()).resolve()
    target_file = (target_dir / filename).resolve()

    # Strict containment check
    if not str(target_file).startswith(str(target_dir)):
        return None, False

    return str(target_file), target_file.is_file()


def _delete_from_s3(filename_or_url):
    """
    Deletes an object from S3/R2 using the shared client configuration.
    Extracts the key and deletes via boto3 client with full endpoint/credentials support.
    Returns True if deletion succeeded, False otherwise.
    """
    match = re.search(r'proofs/[a-zA-Z0-9_.-]+', filename_or_url)
    if not match:
        logger.error("Could not extract S3 object key from %s", filename_or_url)
        return False

    key = match.group(0)
    try:
        client, bucket = _get_s3_client_and_bucket()
        client.delete_object(Bucket=bucket, Key=key)
        logger.info("Successfully deleted S3 object %s from bucket %s", key, bucket)
        return True
    except Exception as e:
        logger.error("Failed to delete S3 object %s: %s", key, e)
        return False


def _delete_from_vercel_blob(url):
    """
    Deletes a blob from Vercel Blob storage via REST API.
    Returns True if deletion succeeded, False otherwise.
    """
    import requests
    token = os.getenv('BLOB_READ_WRITE_TOKEN')
    if not token:
        logger.error("BLOB_READ_WRITE_TOKEN is not configured for Vercel Blob deletion.")
        return False
    try:
        resp = requests.post(
            "https://blob.vercel-storage.com/delete",
            json={"urls": [url]},
            headers={
                "Authorization": f"Bearer {token}",
                "x-api-version": "7",
                "Content-Type": "application/json"
            },
            timeout=15
        )
        if resp.status_code in (200, 204):
            return True
        logger.error("Vercel Blob deletion failed with status %s: %s", resp.status_code, resp.text)
        return False
    except Exception as e:
        logger.error("Error during Vercel Blob deletion: %s", e)
        return False


def _delete_from_cloudinary(filename_or_url):
    """
    Deletes an asset from Cloudinary if API credentials (key/secret) are configured.
    If credentials are not available, does NOT fake success; returns False.
    """
    import urllib.request
    import urllib.parse
    import hashlib
    import time
    import json

    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
    api_key = os.getenv('CLOUDINARY_API_KEY')
    api_secret = os.getenv('CLOUDINARY_API_SECRET')

    cloudinary_url = os.getenv('CLOUDINARY_URL')
    if cloudinary_url:
        match = re.match(r'cloudinary://([^:]+):([^@]+)@(.+)$', cloudinary_url)
        if match:
            api_key = match.group(1)
            api_secret = match.group(2)
            cloud_name = match.group(3)

    if not cloud_name or not api_key or not api_secret:
        logger.warning("Cloudinary deletion unavailable: missing API key or secret credentials.")
        return False

    match = re.search(r'(proof_[a-zA-Z0-9_-]+)', filename_or_url)
    if not match:
        logger.error("Could not determine Cloudinary public_id from %s", filename_or_url)
        return False
    public_id = match.group(1)

    try:
        timestamp = str(int(time.time()))
        to_sign = f"public_id={public_id}&timestamp={timestamp}{api_secret}"
        signature = hashlib.sha1(to_sign.encode('utf-8')).hexdigest()

        payload = urllib.parse.urlencode({
            'public_id': public_id,
            'api_key': api_key,
            'timestamp': timestamp,
            'signature': signature
        }).encode('utf-8')

        api_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/destroy"
        req = urllib.request.Request(api_url, data=payload, method='POST')
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('result') in ('ok', 'not found'):
                return True
            logger.error("Cloudinary destroy returned: %s", data)
            return False
    except Exception as e:
        logger.error("Error during Cloudinary deletion: %s", e)
        return False


def delete_proof_file(filename, upload_dir=None):
    """
    Safely deletes a proof file from local disk or cloud object storage.
    Returns True if deletion was confirmed, False otherwise.
    Never fakes success.
    """
    if not filename or not isinstance(filename, str):
        return False

    # Handle remote object deletion
    if filename.startswith('http://') or filename.startswith('https://') or filename.startswith('proofs/'):
        provider = get_storage_provider()
        if provider == 's3':
            return _delete_from_s3(filename)
        elif provider == 'vercel_blob':
            return _delete_from_vercel_blob(filename)
        elif provider == 'cloudinary':
            return _delete_from_cloudinary(filename)
        else:
            logger.warning("No supported cloud provider configured to delete remote proof: %s", filename)
            return False

    # Local file deletion
    file_path, exists = resolve_proof_file_path(filename, upload_dir=upload_dir)
    if exists and file_path:
        try:
            os.remove(file_path)
            return True
        except Exception as e:
            logger.error("Failed to delete local proof file %s: %s", file_path, e)
            return False
    return False
