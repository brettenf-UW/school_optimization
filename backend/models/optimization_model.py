from sqlalchemy import Column, String, DateTime, JSON, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from . import Base
import uuid

class OptimizationModel(Base):
    """
    OptimizationModel model representing an optimization model template
    """
    __tablename__ = "optimization_models"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    model_type = Column(String(50), nullable=False)  # master_schedule, student_assignments, etc.
    code = Column(Text, nullable=True)  # Python code for the model
    parameters_schema = Column(JSON, nullable=True)  # JSON Schema for model parameters
    default_parameters = Column(JSON, nullable=True)  # Default parameter values
    resource_requirements = Column(JSON, nullable=True)  # CPU, memory, etc.
    version = Column(String(50), nullable=False)
    school_id = Column(String(36), ForeignKey("schools.id"), nullable=True)  # Null for system-wide models
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    jobs = relationship("Job", back_populates="model")
    
    def __repr__(self):
        return f"<OptimizationModel(id='{self.id}', name='{self.name}', version='{self.version}')>"
    
    def to_dict(self):
        """
        Convert to dictionary for API response
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "model_type": self.model_type,
            "parameters_schema": self.parameters_schema,
            "default_parameters": self.default_parameters,
            "resource_requirements": self.resource_requirements,
            "version": self.version,
            "school_id": self.school_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }