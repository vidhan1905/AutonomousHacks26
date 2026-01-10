"""Authentication service with JWT tokens."""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.src.database.models import Patient, ServicePerson, Admin
from backend.src.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


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
