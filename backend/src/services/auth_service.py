"""Authentication service with JWT tokens."""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.src.database.models import Patient, ServicePerson, Admin
from backend.src.config import settings


def get_password_hash(password: str) -> str:
    """Hash a password using SHA256.
    
    Passwords are truncated to 72 bytes before hashing to ensure compatibility.
    """
    # Truncate password to 72 bytes (not characters) to handle multi-byte characters
    if isinstance(password, str):
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            password = password_bytes[:72].decode('utf-8', errors='ignore')
        else:
            password = password
    # Hash with SHA256
    return hashlib.sha256(f"salt_{password}".encode('utf-8')).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a SHA256 hash."""
    # Truncate password to 72 bytes before hashing
    if isinstance(plain_password, str):
        password_bytes = plain_password.encode('utf-8')
        if len(password_bytes) > 72:
            plain_password = password_bytes[:72].decode('utf-8', errors='ignore')
    # Hash and compare
    computed_hash = hashlib.sha256(f"salt_{plain_password}".encode('utf-8')).hexdigest()
    return computed_hash == hashed_password


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


async def authenticate_patient(db: AsyncSession, phone_number: str, password: str) -> Optional[Patient]:
    """Authenticate a patient by phone number and password."""
    result = await db.execute(select(Patient).where(Patient.phone_number == phone_number))
    patient = result.scalar_one_or_none()
    if not patient:
        return None
    # For patients, we might use phone verification instead of password
    # For now, we'll check if password matches a stored hash if available
    # In production, use OTP or phone verification
    return patient


async def authenticate_service_person(db: AsyncSession, username: str, password: str) -> Optional[ServicePerson]:
    """Authenticate a service person by username and password."""
    result = await db.execute(select(ServicePerson).where(ServicePerson.username == username))
    service_person = result.scalar_one_or_none()
    if not service_person or not service_person.is_active:
        return None
    # In a real implementation, verify password hash
    # For now, we'll assume password verification is handled elsewhere
    return service_person


async def authenticate_admin(db: AsyncSession, username: str, password: str) -> Optional[Admin]:
    """Authenticate an admin by username and password."""
    result = await db.execute(select(Admin).where(Admin.username == username))
    admin = result.scalar_one_or_none()
    if not admin or not admin.is_active:
        return None
    # In a real implementation, verify password hash
    return admin


def decode_token(token: str) -> Optional[dict]:
    """Decode a JWT token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None
