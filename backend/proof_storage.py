"""
Settle Up - Secure Payment Proof Storage & Validation Service
Handles file type validation (magic bytes), safe filename generation,
directory traversal prevention, file size limits, and secure disk storage.
"""

import os
import re
import base64
import secrets
from pathlib import Path
from flask import current_app
from .config import BASE_DIR

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


def get_upload_dir(app=None):
    """Retrieves and ensures creation of the secure upload directory."""
    if app:
        upload_dir = app.config.get('UPLOAD_FOLDER', str(BASE_DIR / 'uploads' / 'proofs'))
    elif current_app:
        upload_dir = current_app.config.get('UPLOAD_FOLDER', str(BASE_DIR / 'uploads' / 'proofs'))
    else:
        upload_dir = str(BASE_DIR / 'uploads' / 'proofs')

    upload_path = Path(upload_dir).resolve()
    upload_path.mkdir(parents=True, exist_ok=True)
    return str(upload_path)


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


def save_proof_file_bytes(file_bytes, room_id, settlement_id, original_filename=None, upload_dir=None):
    """
    Validates file content, size, and magic bytes, then securely writes to private disk storage.
    
    Returns:
        dict: {
            'filename': safe_filename,
            'content_type': detected_mime,
            'size_bytes': len(file_bytes),
            'storage_path': full_storage_path
        }
    Raises:
        ValueError: If file is too large, invalid format, or fails magic byte verification.
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

    # Target upload directory
    target_dir = upload_dir or get_upload_dir()
    safe_name = generate_safe_filename(room_id, settlement_id, detected_mime)
    dest_path = (Path(target_dir) / safe_name).resolve()

    # Directory traversal sanity check
    if not str(dest_path).startswith(str(Path(target_dir).resolve())):
        raise ValueError("Security violation: Invalid storage target path.")

    # Write file securely
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

    # Read bytes
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
    except Exception as e:
        raise ValueError("Malformed base64 image data.")

    return save_proof_file_bytes(
        file_bytes,
        room_id=room_id,
        settlement_id=settlement_id,
        upload_dir=upload_dir
    )


def resolve_proof_file_path(filename, upload_dir=None):
    """
    Safely resolves the absolute path for a proof filename.
    Guarantees that path cannot escape the private upload folder (anti-traversal).
    Returns (resolved_path_str, exists_bool).
    """
    if not filename or not isinstance(filename, str):
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


def delete_proof_file(filename, upload_dir=None):
    """Safely deletes an uploaded proof file from disk."""
    file_path, exists = resolve_proof_file_path(filename, upload_dir=upload_dir)
    if exists and file_path:
        try:
            os.remove(file_path)
            return True
        except Exception:
            return False
    return False
