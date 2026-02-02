"""
Backup and recovery system for the artist promotion platform
"""
import os
import asyncio
import shutil
import zipfile
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import boto3
from botocore.exceptions import ClientError
import redis
from app.database.connection import get_db
from app.models.database import Base
import gzip
import tempfile
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class DatabaseBackupManager:
    """Manage database backups and recovery"""
    
    def __init__(self, database_url: str, backup_dir: str = "./backups"):
        self.database_url = database_url
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        
        # Determine database type
        if "postgresql" in database_url:
            self.db_type = "postgresql"
        elif "mysql" in database_url:
            self.db_type = "mysql"
        elif "sqlite" in database_url:
            self.db_type = "sqlite"
        else:
            raise ValueError(f"Unsupported database type in URL: {database_url}")
    
    def create_backup(self, backup_name: Optional[str] = None) -> str:
        """Create a database backup"""
        if not backup_name:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_path = self.backup_dir / f"{backup_name}.sql"
        
        try:
            if self.db_type == "postgresql":
                self._create_postgres_backup(backup_path)
            elif self.db_type == "sqlite":
                self._create_sqlite_backup(backup_path)
            else:
                raise ValueError(f"Backup not implemented for {self.db_type}")
            
            # Compress the backup
            compressed_path = backup_path.with_suffix('.sql.gz')
            with open(backup_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove uncompressed backup
            backup_path.unlink()
            
            logger.info(f"Database backup created: {compressed_path}")
            return str(compressed_path)
            
        except Exception as e:
            logger.error(f"Failed to create database backup: {str(e)}")
            raise
    
    def _create_postgres_backup(self, backup_path: Path):
        """Create PostgreSQL backup using pg_dump"""
        import subprocess
        
        # Parse database URL to extract components
        from urllib.parse import urlparse
        parsed = urlparse(self.database_url)
        
        # Extract components
        username = parsed.username
        password = parsed.password
        hostname = parsed.hostname
        port = parsed.port or 5432
        database = parsed.path.lstrip('/')
        
        # Use environment variable for password to avoid command line exposure
        env = os.environ.copy()
        if password is not None:
            env['PGPASSWORD'] = str(password)
        
        cmd = [
            'pg_dump',
            '-h', hostname,
            '-p', str(port),
            '-U', username,
            '-d', database,
            '-f', str(backup_path)
        ]
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"pg_dump failed: {result.stderr}")
    
    def _create_sqlite_backup(self, backup_path: Path):
        """Create SQLite backup by copying the file"""
        # For SQLite, we can just copy the database file
        source_path = self.database_url.replace("sqlite:///", "")
        shutil.copy2(source_path, backup_path)
    
    def restore_backup(self, backup_path: str):
        """Restore database from backup"""
        backup_path = Path(backup_path)
        
        # Track if we decompressed the file
        was_compressed = backup_path.suffix == '.gz'
        original_backup_path = backup_path

        # Decompress if needed
        if backup_path.suffix == '.gz':
            decompressed_path = backup_path.with_suffix('')
            with gzip.open(backup_path, 'rb') as f_in:
                with open(decompressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            backup_path = decompressed_path

        try:
            if self.db_type == "postgresql":
                self._restore_postgres_backup(backup_path)
            elif self.db_type == "sqlite":
                self._restore_sqlite_backup(backup_path)
            else:
                raise ValueError(f"Restore not implemented for {self.db_type}")

            logger.info(f"Database restored from: {backup_path}")

        except Exception as e:
            logger.error(f"Failed to restore database backup: {str(e)}")
            raise
        finally:
            # Clean up decompressed file only if we created one (was originally compressed)
            if was_compressed and backup_path.suffix == '.sql' and backup_path.exists():
                backup_path.unlink()
    
    def _restore_postgres_backup(self, backup_path: Path):
        """Restore PostgreSQL from backup using psql"""
        import subprocess
        
        # Parse database URL to extract components
        from urllib.parse import urlparse
        parsed = urlparse(self.database_url)
        
        # Extract components
        username = parsed.username
        password = parsed.password
        hostname = parsed.hostname
        port = parsed.port or 5432
        database = parsed.path.lstrip('/')
        
        # Use environment variable for password to avoid command line exposure
        env = os.environ.copy()
        if password is not None:
            env['PGPASSWORD'] = str(password)
        
        cmd = [
            'psql',
            '-h', hostname,
            '-p', str(port),
            '-U', username,
            '-d', database,
            '-f', str(backup_path)
        ]
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"psql restore failed: {result.stderr}")
    
    def _restore_sqlite_backup(self, backup_path: Path):
        """Restore SQLite from backup"""
        dest_path = self.database_url.replace("sqlite:///", "")
        shutil.copy2(backup_path, dest_path)
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups"""
        backups = []
        
        for file_path in self.backup_dir.glob("*.sql.gz"):
            stat = file_path.stat()
            backups.append({
                "name": file_path.name,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "path": str(file_path)
            })
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups

class FileBackupManager:
    """Manage file backups (media, documents, etc.)"""
    
    def __init__(self, source_dirs: List[str], backup_dir: str = "./file_backups"):
        self.source_dirs = [Path(d) for d in source_dirs]
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
    
    def create_backup(self, backup_name: Optional[str] = None) -> str:
        """Create a file backup archive"""
        if not backup_name:
            backup_name = f"files_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_path = self.backup_dir / f"{backup_name}.zip"
        
        try:
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for source_dir in self.source_dirs:
                    if not source_dir.exists():
                        logger.warning(f"Source directory does not exist: {source_dir}")
                        continue
                    
                    for file_path in source_dir.rglob('*'):
                        if file_path.is_file():
                            # Add file to zip with relative path
                            arcname = file_path.relative_to(source_dir.parent)
                            zipf.write(file_path, arcname)
            
            logger.info(f"File backup created: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Failed to create file backup: {str(e)}")
            raise
    
    def restore_backup(self, backup_path: str, restore_dir: str):
        """Restore files from backup"""
        backup_path = Path(backup_path)
        restore_path = Path(restore_dir)
        restore_path.mkdir(parents=True, exist_ok=True)
        
        try:
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                zipf.extractall(restore_path)
            
            logger.info(f"Files restored to: {restore_path}")
            
        except Exception as e:
            logger.error(f"Failed to restore file backup: {str(e)}")
            raise

class CloudBackupManager:
    """Manage cloud backups using AWS S3"""
    
    def __init__(self, bucket_name: str, aws_access_key_id: str, aws_secret_access_key: str, region: str = "us-east-1"):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region
        )
    
    def upload_backup(self, local_path: str, remote_path: str):
        """Upload backup to S3"""
        try:
            self.s3_client.upload_file(local_path, self.bucket_name, remote_path)
            logger.info(f"Backup uploaded to S3: s3://{self.bucket_name}/{remote_path}")
        except ClientError as e:
            logger.error(f"Failed to upload backup to S3: {e}")
            raise
    
    def download_backup(self, remote_path: str, local_path: str):
        """Download backup from S3"""
        try:
            self.s3_client.download_file(self.bucket_name, remote_path, local_path)
            logger.info(f"Backup downloaded from S3: s3://{self.bucket_name}/{remote_path}")
        except ClientError as e:
            logger.error(f"Failed to download backup from S3: {e}")
            raise
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List backups in S3 bucket"""
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix="backups/")
            
            backups = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    backups.append({
                        "name": obj['Key'],
                        "size_bytes": obj['Size'],
                        "last_modified": obj['LastModified'].isoformat(),
                        "etag": obj['ETag'].strip('"')
                    })
            
            # Sort by last modified (newest first)
            backups.sort(key=lambda x: x["last_modified"], reverse=True)
            return backups
        except ClientError as e:
            logger.error(f"Failed to list S3 backups: {e}")
            return []

class BackupScheduler:
    """Schedule automated backups"""
    
    def __init__(self, db_backup_manager: DatabaseBackupManager, 
                 file_backup_manager: Optional[FileBackupManager] = None,
                 cloud_backup_manager: Optional[CloudBackupManager] = None):
        self.db_backup_manager = db_backup_manager
        self.file_backup_manager = file_backup_manager
        self.cloud_backup_manager = cloud_backup_manager
        self.running = False
    
    async def start_scheduler(self, db_interval_hours: int = 24, 
                             file_interval_hours: int = 24,
                             retention_days: int = 30):
        """Start the backup scheduler"""
        self.running = True
        
        while self.running:
            try:
                now = datetime.now()
                
                # Perform database backup if it's time
                if now.minute == 0:  # Only check once per hour
                    if now.hour % db_interval_hours == 0:
                        await self._perform_db_backup()
                
                # Perform file backup if it's time and we have a file manager
                if self.file_backup_manager and now.minute == 0:
                    if now.hour % file_interval_hours == 0:
                        await self._perform_file_backup()
                
                # Clean up old backups
                if now.hour == 2 and now.minute == 0:  # Daily cleanup at 2 AM
                    await self._cleanup_old_backups(retention_days)
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in backup scheduler: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before continuing to avoid rapid error loops
    
    async def _perform_db_backup(self):
        """Perform database backup"""
        try:
            backup_path = self.db_backup_manager.create_backup()
            
            # Upload to cloud if configured
            if self.cloud_backup_manager:
                remote_path = f"backups/db/{Path(backup_path).name}"
                self.cloud_backup_manager.upload_backup(backup_path, remote_path)
            
            logger.info("Database backup completed")
        except Exception as e:
            logger.error(f"Database backup failed: {str(e)}")
    
    async def _perform_file_backup(self):
        """Perform file backup"""
        try:
            backup_path = self.file_backup_manager.create_backup()
            
            # Upload to cloud if configured
            if self.cloud_backup_manager:
                remote_path = f"backups/files/{Path(backup_path).name}"
                self.cloud_backup_manager.upload_backup(backup_path, remote_path)
            
            logger.info("File backup completed")
        except Exception as e:
            logger.error(f"File backup failed: {str(e)}")
    
    async def _cleanup_old_backups(self, retention_days: int):
        """Clean up backups older than retention period"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        # Clean up local database backups
        for backup in self.db_backup_manager.list_backups():
            backup_date = datetime.fromisoformat(backup["created_at"])
            if backup_date < cutoff_date:
                try:
                    Path(backup["path"]).unlink()
                    logger.info(f"Deleted old backup: {backup['path']}")
                except Exception as e:
                    logger.error(f"Failed to delete old backup {backup['path']}: {e}")
        
        logger.info(f"Backup cleanup completed, retention: {retention_days} days")
    
    def stop_scheduler(self):
        """Stop the backup scheduler"""
        self.running = False

class RecoveryManager:
    """Manage recovery operations"""
    
    def __init__(self, db_backup_manager: DatabaseBackupManager,
                 file_backup_manager: Optional[FileBackupManager] = None):
        self.db_backup_manager = db_backup_manager
        self.file_backup_manager = file_backup_manager
    
    def recover_full_system(self, db_backup_path: str, file_backup_path: Optional[str] = None, 
                           dry_run: bool = False):
        """Recover the entire system from backups"""
        if dry_run:
            logger.info("DRY RUN: Would recover system from backups")
            logger.info(f"Database backup: {db_backup_path}")
            logger.info(f"File backup: {file_backup_path}")
            return
        
        logger.info("Starting full system recovery...")
        
        # First, restore database
        self.db_backup_manager.restore_backup(db_backup_path)
        
        # Then, restore files if provided
        if file_backup_path and self.file_backup_manager:
            # Need to determine where to restore files
            restore_dir = os.path.dirname(db_backup_path) + "/restored_files"
            self.file_backup_manager.restore_backup(file_backup_path, restore_dir)
        
        logger.info("Full system recovery completed")
    
    def recover_database_only(self, backup_path: str, dry_run: bool = False):
        """Recover only the database"""
        if dry_run:
            logger.info(f"DRY RUN: Would restore database from {backup_path}")
            return
        
        logger.info(f"Restoring database from {backup_path}...")
        self.db_backup_manager.restore_backup(backup_path)
        logger.info("Database recovery completed")

class BackupSystem:
    """Main backup system orchestrator"""
    
    def __init__(self, database_url: str, file_directories: List[str] = None, 
                 s3_bucket: str = None, aws_access_key: str = None, 
                 aws_secret_key: str = None):
        self.db_manager = DatabaseBackupManager(database_url)
        self.file_manager = None
        self.cloud_manager = None
        self.scheduler = None
        self.recovery_manager = None
        
        if file_directories:
            self.file_manager = FileBackupManager(file_directories)
        
        if s3_bucket and aws_access_key and aws_secret_key:
            self.cloud_manager = CloudBackupManager(s3_bucket, aws_access_key, aws_secret_key)
        
        self.scheduler = BackupScheduler(self.db_manager, self.file_manager, self.cloud_manager)
        self.recovery_manager = RecoveryManager(self.db_manager, self.file_manager)
    
    def create_manual_backup(self, backup_name: str = None) -> Dict[str, str]:
        """Create a manual backup of the system"""
        result = {}
        
        # Create database backup
        db_backup_path = self.db_manager.create_backup(backup_name)
        result["database"] = db_backup_path
        
        # Create file backup if configured
        if self.file_manager:
            file_backup_name = backup_name + "_files" if backup_name else None
            file_backup_path = self.file_manager.create_backup(file_backup_name)
            result["files"] = file_backup_path
        
        # Upload to cloud if configured
        if self.cloud_manager:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            if "database" in result:
                remote_path = f"backups/db/manual_{timestamp}.sql.gz"
                self.cloud_manager.upload_backup(result["database"], remote_path)
                result["cloud_db"] = f"s3://{self.cloud_manager.bucket_name}/{remote_path}"
            
            if "files" in result:
                remote_path = f"backups/files/manual_{timestamp}.zip"
                self.cloud_manager.upload_backup(result["files"], remote_path)
                result["cloud_files"] = f"s3://{self.cloud_manager.bucket_name}/{remote_path}"
        
        return result
    
    def list_all_backups(self) -> Dict[str, List[Dict[str, Any]]]:
        """List all available backups"""
        result = {
            "database": self.db_manager.list_backups()
        }
        
        if self.cloud_manager:
            result["cloud"] = self.cloud_manager.list_backups()
        
        return result

# Global backup system instance
backup_system = None

def initialize_backup_system():
    """Initialize the backup system with configuration"""
    global backup_system
    
    database_url = os.getenv("DATABASE_URL")
    file_directories = os.getenv("BACKUP_FILE_DIRS", "").split(",") if os.getenv("BACKUP_FILE_DIRS") else []
    s3_bucket = os.getenv("BACKUP_S3_BUCKET")
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    if database_url:
        backup_system = BackupSystem(
            database_url=database_url,
            file_directories=file_directories if any(file_directories) else None,
            s3_bucket=s3_bucket,
            aws_access_key=aws_access_key,
            aws_secret_key=aws_secret_key
        )
        logger.info("Backup system initialized")
    else:
        logger.warning("DATABASE_URL not set, backup system not initialized")

def get_backup_system() -> Optional[BackupSystem]:
    """Get the backup system instance"""
    return backup_system

# Initialize backup system at startup
initialize_backup_system()

# Example usage
def main():
    """Example usage of the backup system"""
    import os
    
    # Get configuration from environment
    database_url = os.getenv("DATABASE_URL", "sqlite:///./artist_promo.db")
    s3_bucket = os.getenv("BACKUP_S3_BUCKET")
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    # Initialize backup system
    backup_system = BackupSystem(
        database_url=database_url,
        file_directories=["./uploads", "./media"],  # Example directories
        s3_bucket=s3_bucket,
        aws_access_key=aws_access_key,
        aws_secret_key=aws_secret_key
    )
    
    # Create a manual backup
    backup_result = backup_system.create_manual_backup("manual_backup_2024")
    print("Backup created:", backup_result)
    
    # List all backups
    all_backups = backup_system.list_all_backups()
    print("Available backups:", all_backups)
    
    # Start scheduler for automated backups
    # asyncio.run(backup_system.scheduler.start_scheduler())

if __name__ == "__main__":
    main()