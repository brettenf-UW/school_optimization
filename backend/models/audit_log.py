from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from . import Base
import uuid

class AuditLog(Base):
    """
    AuditLog model for tracking user activities and system events
    """
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(50), nullable=False)  # LOGIN, LOGOUT, CREATE, UPDATE, DELETE, etc.
    resource_type = Column(String(50), nullable=False)  # USER, SCHOOL, JOB, FILE, etc.
    resource_id = Column(String(36), nullable=True)  # ID of the affected resource
    description = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)  # Additional details about the event
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog(id='{self.id}', event_type='{self.event_type}', resource_type='{self.resource_type}')>"
    
    def to_dict(self):
        """
        Convert to dictionary for API response
        """
        return {
            "id": self.id,
            "event_type": self.event_type,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "description": self.description,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }