import asyncio
import uuid
from datetime import datetime, timedelta
from jose import jwt
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User
from app.config import settings

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=365) # long lived for testing
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def main():
    async with AsyncSessionLocal() as db:
        roles = ["student", "instructor", "admin"]
        for role in roles:
            email = f"{role}@test.com"
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            
            if not user:
                user = User(
                    id=uuid.uuid4(),
                    email=email,
                    name=f"Test {role.capitalize()}",
                    role=role
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)
                print(f"Created user {role}: {user.email}")
            else:
                print(f"User {role} already exists: {user.email}")
                
            token = create_access_token({"sub": str(user.id)})
            print(f"\n--- {role.upper()} JWT TOKEN ---")
            print(token)
            print("-" * 50 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
