from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from . import Base


class HRAuth(Base):
    __tablename__ = 'HRAuth'

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    company = Column(String(255), nullable=False)
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

