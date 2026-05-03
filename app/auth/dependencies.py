from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt
from jose.exceptions import JWTError

from app.config import settings
from app.database import get_db
from app.models.user import User

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get('sub')
        if user_id is None:
            raise HTTPException(401, 'Invalid token payload')
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, 'Token expired')
    except JWTError:
        raise HTTPException(401, 'Invalid token')
        
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(401, 'User not found')
    return user

def require_role(*roles: str):
    '''Dependency factory for role-gated routes.'''
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(403,
                f"Role '{current_user.role}' not allowed. Required: {roles}")
        return current_user
    return checker
