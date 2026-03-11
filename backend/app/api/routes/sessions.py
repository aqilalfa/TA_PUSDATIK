"""
Session management endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.db_models import Session as DBSession, User
from app.models.schemas import SessionCreate, SessionResponse
from datetime import datetime
from typing import List
import uuid

router = APIRouter()


@router.post("/", response_model=SessionResponse)
def create_session(session_data: SessionCreate, db: Session = Depends(get_db)):
    """Create a new conversation session"""
    # Verify user exists
    user = db.query(User).filter(User.id == session_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Create session with UUID
    session_id = str(uuid.uuid4())
    db_session = DBSession(
        id=session_id,
        user_id=session_data.user_id,
        title=session_data.title or "New Conversation",
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    return db_session


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, db: Session = Depends(get_db)):
    """Get session by ID"""
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@router.get("/user/{user_id}", response_model=List[SessionResponse])
def list_user_sessions(user_id: int, db: Session = Depends(get_db)):
    """List all sessions for a user"""
    sessions = (
        db.query(DBSession)
        .filter(DBSession.user_id == user_id, DBSession.is_active == True)
        .order_by(DBSession.updated_at.desc())
        .all()
    )

    return sessions


@router.get("/", response_model=List[SessionResponse])
def list_all_sessions(limit: int = 50, db: Session = Depends(get_db)):
    """List all sessions (defaults to user 1 for demo purposes)"""
    sessions = (
        db.query(DBSession)
        .filter(DBSession.user_id == 1, DBSession.is_active == True)
        .order_by(DBSession.updated_at.desc())
        .limit(limit)
        .all()
    )

    return sessions


@router.put("/{session_id}/title")
def update_session_title(session_id: str, title: str, db: Session = Depends(get_db)):
    """Update session title"""
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.title = title
    session.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "Title updated successfully"}


@router.delete("/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    """Delete (deactivate) a session"""
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.is_active = False
    db.commit()

    return {"message": "Session deleted successfully"}
