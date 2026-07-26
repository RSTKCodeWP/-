"""
Cloud Storage Integration
Support for S3, Azure Blob, and Google Cloud Storage
"""

import logging
import mimetypes
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CloudStorageProvider(ABC):
    """Base class for cloud storage providers"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", False)

    @abstractmethod
    async def upload_file(
        self,
        local_path: Path,
        remote_path: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Upload file to cloud storage

        Args:
            local_path: Path to local file
            remote_path: Remote path/key
            metadata: Optional metadata

        Returns:
            URL of uploaded file
        """
        pass

    @abstractmethod
    async def download_file(
        self,
        remote_path: str,
        local_path: Path
    ) -> bool:
        """
        Download file from cloud storage

        Args:
            remote_path: Remote path/key
            local_path: Path to save file

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def delete_file(self, remote_path: str) -> bool:
        """
        Delete file from cloud storage

        Args:
            remote_path: Remote path/key

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def list_files(self, prefix: str = "") -> List[str]:
        """
        List files in cloud storage

        Args:
            prefix: Path prefix to filter by

        Returns:
            List of file paths
        """
        pass

    @abstractmethod
    async def get_url(self, remote_path: str, expires_in: int = 3600) -> str:
        """
        Get signed URL for file access

        Args:
            remote_path: Remote path/key
            expires_in: URL expiry in seconds

        Returns:
            Signed URL
        """
        pass


class S3Storage(CloudStorageProvider):
    """Amazon S3 storage provider"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bucket_name = config.get("bucket_name")
        self.region = config.get("region", "us-east-1")
        self.access_key = config.get("access_key")
        self.secret_key = config.get("secret_key")
        self.client = None

        if self.enabled:
            self._initialize_client()

    def _initialize_client(self):
        """Initialize S3 client"""
        try:
            # In production, install boto3: pip install boto3
            import boto3

            self.client = boto3.client(
                's3',
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key
            )
            logger.info(f"S3 client initialized for bucket: {self.bucket_name}")
        except ImportError:
            logger.error("boto3 not installed. Install with: pip install boto3")
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            self.enabled = False

    async def upload_file(
        self,
        local_path: Path,
        remote_path: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """Upload file to S3"""
        if not self.enabled or not self.client:
            raise RuntimeError("S3 storage not enabled")

        try:
            # Determine content type
            content_type, _ = mimetypes.guess_type(str(local_path))

            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            if metadata:
                extra_args['Metadata'] = {k: str(v) for k, v in metadata.items()}

            # Upload
            self.client.upload_file(
                str(local_path),
                self.bucket_name,
                remote_path,
                ExtraArgs=extra_args
            )

            # Generate URL
            url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{remote_path}"

            logger.info(f"Uploaded to S3: {remote_path}")
            return url

        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            raise

    async def download_file(self, remote_path: str, local_path: Path) -> bool:
        """Download file from S3"""
        if not self.enabled or not self.client:
            return False

        try:
            self.client.download_file(
                self.bucket_name,
                remote_path,
                str(local_path)
            )
            logger.info(f"Downloaded from S3: {remote_path}")
            return True
        except Exception as e:
            logger.error(f"S3 download failed: {e}")
            return False

    async def delete_file(self, remote_path: str) -> bool:
        """Delete file from S3"""
        if not self.enabled or not self.client:
            return False

        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=remote_path
            )
            logger.info(f"Deleted from S3: {remote_path}")
            return True
        except Exception as e:
            logger.error(f"S3 delete failed: {e}")
            return False

    async def list_files(self, prefix: str = "") -> List[str]:
        """List files in S3 bucket"""
        if not self.enabled or not self.client:
            return []

        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )

            files = [obj['Key'] for obj in response.get('Contents', [])]
            return files
        except Exception as e:
            logger.error(f"S3 list failed: {e}")
            return []

    async def get_url(self, remote_path: str, expires_in: int = 3600) -> str:
        """Get signed URL for S3 object"""
        if not self.enabled or not self.client:
            raise RuntimeError("S3 storage not enabled")

        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': remote_path
                },
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise


class AzureBlobStorage(CloudStorageProvider):
    """Azure Blob Storage provider"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.container_name = config.get("container_name")
        self.connection_string = config.get("connection_string")
        self.account_name = config.get("account_name")
        self.account_key = config.get("account_key")
        self.client = None

        if self.enabled:
            self._initialize_client()

    def _initialize_client(self):
        """Initialize Azure Blob client"""
        try:
            # In production, install: pip install azure-storage-blob
            from azure.storage.blob import BlobServiceClient

            if self.connection_string:
                self.client = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
            else:
                from azure.storage.blob import BlobServiceClient
                account_url = f"https://{self.account_name}.blob.core.windows.net"
                self.client = BlobServiceClient(
                    account_url=account_url,
                    credential=self.account_key
                )

            logger.info(f"Azure Blob client initialized for container: {self.container_name}")
        except ImportError:
            logger.error("azure-storage-blob not installed. Install with: pip install azure-storage-blob")
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize Azure Blob client: {e}")
            self.enabled = False

    async def upload_file(
        self,
        local_path: Path,
        remote_path: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """Upload file to Azure Blob"""
        if not self.enabled or not self.client:
            raise RuntimeError("Azure Blob storage not enabled")

        try:
            blob_client = self.client.get_blob_client(
                container=self.container_name,
                blob=remote_path
            )

            with open(local_path, 'rb') as data:
                blob_client.upload_blob(
                    data,
                    metadata=metadata,
                    overwrite=True
                )

            url = blob_client.url
            logger.info(f"Uploaded to Azure Blob: {remote_path}")
            return url

        except Exception as e:
            logger.error(f"Azure Blob upload failed: {e}")
            raise

    async def download_file(self, remote_path: str, local_path: Path) -> bool:
        """Download file from Azure Blob"""
        if not self.enabled or not self.client:
            return False

        try:
            blob_client = self.client.get_blob_client(
                container=self.container_name,
                blob=remote_path
            )

            with open(local_path, 'wb') as f:
                data = blob_client.download_blob()
                f.write(data.readall())

            logger.info(f"Downloaded from Azure Blob: {remote_path}")
            return True
        except Exception as e:
            logger.error(f"Azure Blob download failed: {e}")
            return False

    async def delete_file(self, remote_path: str) -> bool:
        """Delete file from Azure Blob"""
        if not self.enabled or not self.client:
            return False

        try:
            blob_client = self.client.get_blob_client(
                container=self.container_name,
                blob=remote_path
            )
            blob_client.delete_blob()

            logger.info(f"Deleted from Azure Blob: {remote_path}")
            return True
        except Exception as e:
            logger.error(f"Azure Blob delete failed: {e}")
            return False

    async def list_files(self, prefix: str = "") -> List[str]:
        """List files in Azure Blob container"""
        if not self.enabled or not self.client:
            return []

        try:
            container_client = self.client.get_container_client(self.container_name)
            blobs = container_client.list_blobs(name_starts_with=prefix)

            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"Azure Blob list failed: {e}")
            return []

    async def get_url(self, remote_path: str, expires_in: int = 3600) -> str:
        """Get SAS URL for Azure Blob"""
        if not self.enabled or not self.client:
            raise RuntimeError("Azure Blob storage not enabled")

        try:
            from datetime import datetime, timedelta

            from azure.storage.blob import BlobSasPermissions, generate_blob_sas

            sas_token = generate_blob_sas(
                account_name=self.account_name,
                container_name=self.container_name,
                blob_name=remote_path,
                account_key=self.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(seconds=expires_in)
            )

            url = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{remote_path}?{sas_token}"
            return url
        except Exception as e:
            logger.error(f"Failed to generate SAS URL: {e}")
            raise


class CloudStorageManager:
    """
    Manages multiple cloud storage providers
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize cloud storage manager

        Args:
            config: Configuration with provider settings
        """
        self.providers: Dict[str, CloudStorageProvider] = {}

        # Initialize S3
        if config.get("s3", {}).get("enabled"):
            try:
                self.providers["s3"] = S3Storage(config["s3"])
            except Exception as e:
                logger.error(f"Failed to initialize S3: {e}")

        # Initialize Azure Blob
        if config.get("azure_blob", {}).get("enabled"):
            try:
                self.providers["azure_blob"] = AzureBlobStorage(config["azure_blob"])
            except Exception as e:
                logger.error(f"Failed to initialize Azure Blob: {e}")

        logger.info(f"Cloud storage initialized with {len(self.providers)} providers")

    def get_provider(self, name: str) -> Optional[CloudStorageProvider]:
        """Get storage provider by name"""
        return self.providers.get(name)

    def get_default_provider(self) -> Optional[CloudStorageProvider]:
        """Get first enabled provider"""
        for provider in self.providers.values():
            if provider.enabled:
                return provider
        return None

    async def upload(
        self,
        local_path: Path,
        remote_path: str,
        provider: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Upload file using specified or default provider

        Args:
            local_path: Local file path
            remote_path: Remote path
            provider: Provider name (optional, uses default if None)
            metadata: Optional metadata

        Returns:
            URL of uploaded file or None if failed
        """
        storage = self.providers.get(provider) if provider else self.get_default_provider()

        if not storage:
            logger.error("No cloud storage provider available")
            return None

        try:
            return await storage.upload_file(local_path, remote_path, metadata)
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return None

    async def upload_directory(
        self,
        local_dir: Path,
        remote_prefix: str,
        provider: Optional[str] = None
    ) -> List[str]:
        """
        Upload entire directory to cloud storage

        Args:
            local_dir: Local directory
            remote_prefix: Remote path prefix
            provider: Provider name (optional)

        Returns:
            List of uploaded file URLs
        """
        if not local_dir.is_dir():
            logger.error(f"Not a directory: {local_dir}")
            return []

        uploaded = []

        for file_path in local_dir.rglob('*'):
            if file_path.is_file():
                # Calculate relative path
                relative = file_path.relative_to(local_dir)
                remote_path = f"{remote_prefix}/{relative}".replace("\\", "/")

                # Upload
                url = await self.upload(file_path, remote_path, provider)
                if url:
                    uploaded.append(url)

        logger.info(f"Uploaded {len(uploaded)} files to cloud storage")
        return uploaded

    def list_providers(self) -> List[Dict[str, Any]]:
        """Get list of configured providers"""
        return [
            {
                "name": name,
                "enabled": provider.enabled,
                "type": provider.__class__.__name__
            }
            for name, provider in self.providers.items()
        ]


# Global instance
_cloud_storage = None


def get_cloud_storage(config: Optional[Dict] = None) -> CloudStorageManager:
    """Get or create global cloud storage manager"""
    global _cloud_storage

    if _cloud_storage is None:
        from ..config import settings

        default_config = {
            "s3": {
                "enabled": getattr(settings, 's3_enabled', False),
                "bucket_name": getattr(settings, 's3_bucket_name', None),
                "region": getattr(settings, 's3_region', 'us-east-1'),
                "access_key": getattr(settings, 's3_access_key', None),
                "secret_key": getattr(settings, 's3_secret_key', None),
            },
            "azure_blob": {
                "enabled": getattr(settings, 'azure_blob_enabled', False),
                "container_name": getattr(settings, 'azure_blob_container', None),
                "connection_string": getattr(settings, 'azure_blob_connection_string', None),
                "account_name": getattr(settings, 'azure_blob_account_name', None),
                "account_key": getattr(settings, 'azure_blob_account_key', None),
            }
        }

        _cloud_storage = CloudStorageManager(config or default_config)

    return _cloud_storage

