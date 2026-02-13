from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User, UserRole


def create_user(email: str, full_name: str, password: str, role: UserRole) -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            print(f"User already exists: {email}")
            return

        user = User(
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Created {role.value}: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    create_user("admin@agency.com", "Agency Admin", "Admin@12345!secure", UserRole.admin)
    create_user("manager@agency.com", "Agency Manager", "Manager@12345!secure", UserRole.manager)
    create_user("agent@agency.com", "Agent One", "Agent@12345!secure", UserRole.agent)
