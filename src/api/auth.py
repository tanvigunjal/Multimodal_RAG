from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, EmailStr
from fastapi import HTTPException, Security, status, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
import jwt
from decouple import config

# Models
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    email: EmailStr
    token: str

# Password hashing
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Explicitly set number of rounds
    bcrypt__ident="2b"  # Use the latest bcrypt variant
)

def truncate_password(password: str, max_bytes: int = 72) -> str:
    """Truncate password to maximum number of bytes for bcrypt."""
    try:
        encoded = password.encode('utf-8')
        return encoded[:max_bytes].decode('utf-8', errors='ignore')
    except UnicodeError:
        # Fallback for any Unicode issues
        return password[:72]

# JWT settings
JWT_SECRET = config('JWT_SECRET', default='your-secret-key')  # Should be set in environment variables
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Security utilities
security = HTTPBearer(auto_error=False)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        truncated = truncate_password(plain_password)
        return pwd_context.verify(truncated, hashed_password)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False

def get_password_hash(password: str) -> str:
    try:
        truncated = truncate_password(password)
        return pwd_context.hash(truncated)
    except Exception as e:
        print(f"Password hashing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing password"
        )

def create_access_token(email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": email,
        "exp": expire
    }
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if datetime.fromtimestamp(payload['exp']) < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        return payload['sub']
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    token: Optional[str] = Query(None, description="JWT token (alternative to Authorization header)")
) -> str:
    if credentials:
        token_str = credentials.credentials
    elif token:
        token_str = token
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return decode_token(token_str)

# In-memory user storage (replace with database in production)
USERS = {
    "admin@gmail.com": get_password_hash("admin123")  # Demo user
}