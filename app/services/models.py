# app/services/models.py
import uuid
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .db import Base

class User(Base):
    __tablename__ = "users"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = sa.Column(sa.String, unique=True, nullable=False, index=True)
    password_hash = sa.Column(sa.String, nullable=False)
    is_active = sa.Column(sa.Boolean, server_default=sa.text("true"))
    created_at = sa.Column(sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"))

class Transcript(Base):
    __tablename__ = "transcripts"

    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    session_id = sa.Column(sa.String, index=True)
    
    text = sa.Column(sa.Text)
    assistant_text = sa.Column(sa.Text) 
    tokens = sa.Column(sa.Integer, server_default=sa.text("0"))
    meta = sa.Column(sa.JSON)
    created_at = sa.Column(sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"))

    user = relationship("User", backref="transcripts")

class UserProfile(Base):
    __tablename__ = "user_profiles"
    user_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    resume = sa.Column(sa.Text)
    projects = sa.Column(sa.Text)
    job_description = sa.Column(sa.Text)
    updated_at = sa.Column(sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), onupdate=sa.text("now()"))

