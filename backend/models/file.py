from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from . import Base
import uuid

class File(Base):
    """
    File model representing a file in the system
    """
    __tablename__ = "files"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # sections, students, teachers, preferences, results
    s3_key = Column(String(1000), nullable=False)
    content_type = Column(String(100), nullable=True)
    size = Column(Integer, nullable=True)  # File size in bytes
    file_metadata = Column(JSON, nullable=True)  # File metadata (headers, data summary, etc.)
    validation_status = Column(String(50), nullable=True)  # PENDING, VALID, INVALID
    validation_errors = Column(JSON, nullable=True)
    is_input = Column(Boolean, default=True)  # True for input files, False for result files
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    school_id = Column(String(36), ForeignKey("schools.id"), nullable=False)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    school = relationship("School", back_populates="files")
    job = relationship("Job", back_populates="files")
    
    def __repr__(self):
        return f"<File(id='{self.id}', name='{self.name}', file_type='{self.file_type}')>"
    
    def to_dict(self):
        """
        Convert to dictionary for API response
        """
        return {
            "id": self.id,
            "name": self.name,
            "file_type": self.file_type,
            "s3_key": self.s3_key,
            "content_type": self.content_type,
            "size": self.size,
            "metadata": self.file_metadata,
            "validation_status": self.validation_status,
            "validation_errors": self.validation_errors,
            "is_input": self.is_input,
            "user_id": self.user_id,
            "school_id": self.school_id,
            "job_id": self.job_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }