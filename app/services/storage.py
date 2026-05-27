"""Storage service — local disk or AWS S3."""

import boto3
from botocore.exceptions import ClientError
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _s3_client(settings):
    """Create S3 client from settings."""
    return boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )


def upload_to_s3(local_path: Path, s3_key: str, settings=None) -> None:
    """Upload a file to S3."""
    if settings is None:
        from app.config import get_settings
        settings = get_settings()
    
    try:
        s3 = _s3_client(settings)
        s3.upload_file(str(local_path), settings.s3_bucket_name, s3_key)
        logger.info(f"Uploaded {s3_key} to S3 bucket {settings.s3_bucket_name}")
    except ClientError as e:
        logger.error(f"S3 upload failed for {s3_key}: {e}")
        raise


def download_from_s3(s3_key: str, local_path: str, settings=None) -> None:
    """Download a file from S3 to local path."""
    if settings is None:
        from app.config import get_settings
        settings = get_settings()
    
    try:
        s3 = _s3_client(settings)
        s3.download_file(settings.s3_bucket_name, s3_key, local_path)
        logger.info(f"Downloaded {s3_key} from S3 to {local_path}")
    except ClientError as e:
        logger.error(f"S3 download failed for {s3_key}: {e}")
        raise


def get_presigned_url(s3_key: str, ttl: int = 3600, settings=None) -> str:
    """Generate a presigned URL for temporary access."""
    if settings is None:
        from app.config import get_settings
        settings = get_settings()
    
    try:
        s3 = _s3_client(settings)
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket_name, "Key": s3_key},
            ExpiresIn=ttl,
        )
        return url
    except ClientError as e:
        logger.error(f"Presigned URL failed for {s3_key}: {e}")
        raise


def delete_from_s3(s3_key: str, settings=None) -> None:
    """Delete a file from S3."""
    if settings is None:
        from app.config import get_settings
        settings = get_settings()
    
    try:
        s3 = _s3_client(settings)
        s3.delete_object(Bucket=settings.s3_bucket_name, Key=s3_key)
        logger.info(f"Deleted {s3_key} from S3")
    except ClientError as e:
        logger.error(f"S3 delete failed for {s3_key}: {e}")
        raise
# Aliases for routes compatibility
upload_file = upload_to_s3
delete_file = delete_from_s3

