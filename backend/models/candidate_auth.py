from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from . import Base


class CandidateAuth(Base):
    __tablename__ = 'CandidateAuth'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255))
    phone = Column(String(20))
    password_hash = Column(String(255), nullable=False)
    otp = Column(String(6))
    otp_expiry = Column(DateTime)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def mark_verified(self):
        self.is_verified = True
        self.otp = None
        self.otp_expiry = None
        self.updated_at = datetime.utcnow()

