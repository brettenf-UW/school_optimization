from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from . import Base
import uuid

class User(Base):
    """
    User model representing a user in the system
    """
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cognito_id = Column(String(128), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="User")  # Admin, Teacher, Staff
    school_id = Column(String(36), ForeignKey("schools.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    school = relationship("School", back_populates="users")
    jobs = relationship("Job", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    
    def __repr__(self):
        return f"<User(id='{self.id}', email='{self.email}', role='{self.role}')>"
    
    def to_dict(self):
        """
        Convert to dictionary for API response
        """
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "school_id": self.school_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active
        }