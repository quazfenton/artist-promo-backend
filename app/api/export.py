"""Enhanced export API with multiple formats"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import csv
import json
import io
from datetime import datetime
import pandas as pd
from app.models.database import get_db, Contact
from app.middleware.auth_middleware import get_current_user
from app.tasks.scraper_tasks import celery_app

router = APIRouter(prefix="/export", tags=["export"])

class ExportRequest(BaseModel):
    format: str = "csv"  # csv, json, excel
    filters: Optional[Dict[str, Any]] = {}
    fields: Optional[List[str]] = None
    template: Optional[str] = None
    async_export: bool = False

class ExportTemplate(BaseModel):
    name: str
    fields: List[str]
    filters: Dict[str, Any]
    format: str

@router.post("/contacts")
async def export_contacts(
    export_request: ExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Export contacts in various formats"""
    
    if export_request.async_export:
        # Queue background export task
        task = export_contacts_async.delay(
            export_request.dict(),
            current_user["user_id"]
        )
        return {
            "status": "queued",
            "task_id": task.id,
            "message": "Export queued for background processing"
        }
    
    # Synchronous export
    query = _build_export_query(db, export_request.filters)
    contacts = query.all()
    
    if export_request.format.lower() == "csv":
        return _export_csv(contacts, export_request.fields)
    elif export_request.format.lower() == "json":
        return _export_json(contacts, export_request.fields)
    elif export_request.format.lower() == "excel":
        return _export_excel(contacts, export_request.fields)
    else:
        raise HTTPException(status_code=400, detail="Unsupported export format")

@router.get("/templates")
async def get_export_templates(current_user: dict = Depends(get_current_user)):
    """Get predefined export templates"""
    
    templates = [
        {
            "name": "High Priority Curators",
            "fields": ["full_name", "email", "priority_score", "follower_count", "instagram_handle"],
            "filters": {"min_score": 80, "contact_type": "playlist_curator"},
            "format": "csv"
        },
        {
            "name": "All Contacts Full Export",
            "fields": ["full_name", "email", "contact_type", "priority_score", "follower_count", 
                      "company", "instagram_handle", "twitter_handle", "verified", "source_platform"],
            "filters": {},
            "format": "excel"
        },
        {
            "name": "Verified Contacts Only",
            "fields": ["full_name", "email", "contact_type", "priority_score", "company"],
            "filters": {"verified_only": True},
            "format": "csv"
        }
    ]
    
    return {"templates": templates}

@router.post("/templates")
async def create_export_template(
    template: ExportTemplate,
    current_user: dict = Depends(get_current_user)
):
    """Create custom export template"""
    
    # In a real implementation, save to database
    # For now, just validate and return
    
    return {
        "status": "created",
        "template": template.dict(),
        "message": f"Template '{template.name}' created successfully"
    }

@router.get("/fields")
async def get_available_fields(current_user: dict = Depends(get_current_user)):
    """Get available fields for export"""
    
    fields = [
        {"name": "id", "label": "ID", "type": "integer"},
        {"name": "full_name", "label": "Full Name", "type": "string"},
        {"name": "email", "label": "Email", "type": "string"},
        {"name": "contact_type", "label": "Contact Type", "type": "enum"},
        {"name": "priority_score", "label": "Priority Score", "type": "float"},
        {"name": "follower_count", "label": "Follower Count", "type": "integer"},
        {"name": "company", "label": "Company", "type": "string"},
        {"name": "title", "label": "Title", "type": "string"},
        {"name": "instagram_handle", "label": "Instagram", "type": "string"},
        {"name": "twitter_handle", "label": "Twitter", "type": "string"},
        {"name": "website", "label": "Website", "type": "string"},
        {"name": "verified", "label": "Verified", "type": "boolean"},
        {"name": "source_platform", "label": "Source Platform", "type": "enum"},
        {"name": "created_at", "label": "Created Date", "type": "datetime"},
        {"name": "genres", "label": "Genres", "type": "array"}
    ]
    
    return {"fields": fields}

def _build_export_query(db: Session, filters: Dict[str, Any]):
    """Build query based on export filters"""
    
    query = db.query(Contact).filter(Contact.deleted_at.is_(None))
    
    if filters.get("contact_type"):
        query = query.filter(Contact.contact_type == filters["contact_type"])
    
    if filters.get("min_score"):
        query = query.filter(Contact.priority_score >= filters["min_score"])
    
    if filters.get("max_score"):
        query = query.filter(Contact.priority_score <= filters["max_score"])
    
    if filters.get("verified_only"):
        query = query.filter(Contact.verified == True)
    
    if filters.get("platform"):
        query = query.filter(Contact.source_platform == filters["platform"])
    
    return query.order_by(Contact.priority_score.desc())

def _export_csv(contacts: List[Contact], fields: Optional[List[str]] = None) -> StreamingResponse:
    """Export contacts as CSV"""
    
    output = io.StringIO()
    
    # Default fields if none specified
    if not fields:
        fields = ["full_name", "email", "contact_type", "priority_score", "follower_count", 
                 "company", "instagram_handle", "verified", "source_platform"]
    
    writer = csv.writer(output)
    
    # Write header
    headers = [field.replace('_', ' ').title() for field in fields]
    writer.writerow(headers)
    
    # Write data
    for contact in contacts:
        row = []
        for field in fields:
            value = getattr(contact, field, '')
            
            # Handle special field types
            if field == 'contact_type' and value:
                value = value.value
            elif field == 'source_platform' and value:
                value = value.value
            elif field == 'genres' and value:
                value = ','.join(value) if isinstance(value, list) else value
            elif field == 'verified':
                value = 'Yes' if value else 'No'
            elif value is None:
                value = ''
            
            row.append(str(value))
        
        writer.writerow(row)
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=contacts_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )

def _export_json(contacts: List[Contact], fields: Optional[List[str]] = None) -> Dict:
    """Export contacts as JSON"""
    
    if not fields:
        fields = ["id", "full_name", "email", "contact_type", "priority_score", 
                 "follower_count", "company", "verified"]
    
    results = []
    for contact in contacts:
        contact_data = {}
        for field in fields:
            value = getattr(contact, field, None)
            
            if field == 'contact_type' and value:
                value = value.value
            elif field == 'source_platform' and value:
                value = value.value
            elif field == 'created_at' and value:
                value = value.isoformat()
            
            contact_data[field] = value
        
        results.append(contact_data)
    
    return {
        "export_date": datetime.now().isoformat(),
        "total_records": len(results),
        "contacts": results
    }

def _export_excel(contacts: List[Contact], fields: Optional[List[str]] = None) -> StreamingResponse:
    """Export contacts as Excel file"""
    
    if not fields:
        fields = ["full_name", "email", "contact_type", "priority_score", "follower_count", 
                 "company", "instagram_handle", "twitter_handle", "verified", "source_platform"]
    
    # Prepare data for DataFrame
    data = []
    for contact in contacts:
        row = {}
        for field in fields:
            value = getattr(contact, field, '')
            
            if field == 'contact_type' and value:
                value = value.value
            elif field == 'source_platform' and value:
                value = value.value
            elif field == 'genres' and value:
                value = ','.join(value) if isinstance(value, list) else value
            elif field == 'verified':
                value = 'Yes' if value else 'No'
            
            row[field.replace('_', ' ').title()] = value
        
        data.append(row)
    
    # Create DataFrame and Excel file
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Contacts', index=False)
    
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=contacts_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        }
    )

@celery_app.task(bind=True)
def export_contacts_async(self, export_request: Dict, user_id: int):
    """Background export task"""
    
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        import os
        
        # Database setup
        DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./artist_promo.db")
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        db = SessionLocal()
        
        self.update_state(state='PROGRESS', meta={'status': 'Building query'})
        
        query = _build_export_query(db, export_request.get('filters', {}))
        contacts = query.all()
        
        self.update_state(state='PROGRESS', meta={'status': f'Exporting {len(contacts)} contacts'})
        
        # Generate export based on format
        export_format = export_request.get('format', 'csv').lower()
        fields = export_request.get('fields')
        
        if export_format == 'json':
            result = _export_json(contacts, fields)
        else:
            # For CSV/Excel, save to file and return path
            filename = f"export_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format}"
            # In production, save to cloud storage and return download URL
            result = {"filename": filename, "download_url": f"/downloads/{filename}"}
        
        db.close()
        
        return {
            'status': 'completed',
            'export_format': export_format,
            'total_records': len(contacts),
            'result': result
        }
        
    except Exception as e:
        self.retry(countdown=60, exc=e)
