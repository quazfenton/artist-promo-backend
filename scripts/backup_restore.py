#!/usr/bin/env python3
"""Database backup and restore utilities"""
import os
import subprocess
from datetime import datetime
from pathlib import Path
import click

@click.group()
def cli():
    """Database backup and restore utilities"""
    pass

@cli.command()
@click.option('--output-dir', default='./backups', help='Backup output directory')
def backup(output_dir):
    """Create database backup"""
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        click.echo("ERROR: DATABASE_URL not set")
        return
    
    # Create backup directory
    backup_dir = Path(output_dir)
    backup_dir.mkdir(exist_ok=True)
    
    # Generate backup filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = backup_dir / f"artist_promo_backup_{timestamp}.sql"
    
    try:
        if database_url.startswith('postgresql'):
            # PostgreSQL backup
            cmd = f"pg_dump {database_url} > {backup_file}"
            subprocess.run(cmd, shell=True, check=True)
        elif database_url.startswith('sqlite'):
            # SQLite backup
            db_path = database_url.replace('sqlite:///', '')
            cmd = f"sqlite3 {db_path} .dump > {backup_file}"
            subprocess.run(cmd, shell=True, check=True)
        
        click.echo(f"✅ Backup created: {backup_file}")
        
        # Compress backup
        compressed_file = f"{backup_file}.gz"
        subprocess.run(f"gzip {backup_file}", shell=True, check=True)
        click.echo(f"✅ Compressed: {compressed_file}")
        
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Backup failed: {e}")

@cli.command()
@click.argument('backup_file')
@click.option('--confirm', is_flag=True, help='Confirm restore operation')
def restore(backup_file, confirm):
    """Restore database from backup"""
    
    if not confirm:
        click.echo("⚠️  This will overwrite the current database!")
        click.echo("Use --confirm flag to proceed")
        return
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        click.echo("ERROR: DATABASE_URL not set")
        return
    
    backup_path = Path(backup_file)
    if not backup_path.exists():
        click.echo(f"❌ Backup file not found: {backup_file}")
        return
    
    try:
        # Decompress if needed
        if backup_file.endswith('.gz'):
            subprocess.run(f"gunzip -c {backup_file} > temp_restore.sql", shell=True, check=True)
            restore_file = "temp_restore.sql"
        else:
            restore_file = backup_file
        
        if database_url.startswith('postgresql'):
            # PostgreSQL restore
            cmd = f"psql {database_url} < {restore_file}"
            subprocess.run(cmd, shell=True, check=True)
        elif database_url.startswith('sqlite'):
            # SQLite restore
            db_path = database_url.replace('sqlite:///', '')
            cmd = f"sqlite3 {db_path} < {restore_file}"
            subprocess.run(cmd, shell=True, check=True)
        
        click.echo("✅ Database restored successfully")
        
        # Clean up temp file
        if restore_file == "temp_restore.sql":
            os.remove(restore_file)
            
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Restore failed: {e}")

@cli.command()
@click.option('--days', default=30, help='Delete backups older than N days')
def cleanup(days):
    """Clean up old backup files"""
    
    backup_dir = Path('./backups')
    if not backup_dir.exists():
        click.echo("No backup directory found")
        return
    
    cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
    deleted_count = 0
    
    for backup_file in backup_dir.glob('artist_promo_backup_*.sql*'):
        if backup_file.stat().st_mtime < cutoff_time:
            backup_file.unlink()
            deleted_count += 1
            click.echo(f"Deleted: {backup_file}")
    
    click.echo(f"✅ Cleaned up {deleted_count} old backup files")

if __name__ == '__main__':
    cli()
