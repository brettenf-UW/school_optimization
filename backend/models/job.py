from sqlalchemy import Column, String, DateTime, Float, JSON, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from . import Base
import uuid

class Job(Base):
    """
    Job model representing an optimization job in the system
    """
    __tablename__ = "jobs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    job_type = Column(String(50), nullable=False)  # master_schedule, student_assignments, etc.
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, QUEUED, RUNNING, COMPLETED, FAILED
    parameters = Column(JSON, nullable=True)  # Job-specific parameters
    batch_job_id = Column(String(255), nullable=True)  # AWS Batch job ID
    progress = Column(Float, nullable=True)  # Progress percentage (0-100)
    error_message = Column(String(1000), nullable=True)
    result_summary = Column(JSON, nullable=True)  # Summary of job results
    execution_time = Column(Integer, nullable=True)  # Execution time in seconds
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    school_id = Column(String(36), ForeignKey("schools.id"), nullable=False)
    model_id = Column(String(36), ForeignKey("optimization_models.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="jobs")
    school = relationship("School", back_populates="jobs")
    model = relationship("OptimizationModel", back_populates="jobs")
    files = relationship("File", back_populates="job")
    
    def __repr__(self):
        return f"<Job(id='{self.id}', name='{self.name}', status='{self.status}')>"
    
    def to_dict(self):
        """
        Convert to dictionary for API response
        """
        return {
            "id": self.id,
            "name": self.name,
            "job_type": self.job_type,
            "status": self.status,
            "parameters": self.parameters,
            "batch_job_id": self.batch_job_id,
            "progress": self.progress,
            "error_message": self.error_message,
            "result_summary": self.result_summary,
            "execution_time": self.execution_time,
            "user_id": self.user_id,
            "school_id": self.school_id,
            "model_id": self.model_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }