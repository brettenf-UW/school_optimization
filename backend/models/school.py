from sqlalchemy import Column, String, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from . import Base
import uuid

class School(Base):
    """
    School model representing a school in the system
    """
    __tablename__ = "schools"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    website = Column(String(255), nullable=True)
    configuration = Column(JSON, nullable=True)  # School-specific configuration for optimization
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    users = relationship("User", back_populates="school")
    jobs = relationship("Job", back_populates="school")
    files = relationship("File", back_populates="school")
    
    def __repr__(self):
        return f"<School(id='{self.id}', name='{self.name}', code='{self.code}')>"
    
    def to_dict(self):
        """
        Convert to dictionary for API response
        """
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "phone": self.phone,
            "email": self.email,
            "website": self.website,
            "configuration": self.configuration,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active
        }