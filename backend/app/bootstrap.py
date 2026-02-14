import os

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
    # Do not hardcode credentials in the repo. Use env vars for local bootstrap.
    admin_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL")
    admin_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
    if admin_email and admin_password:
        create_user(admin_email, "Agency Admin", admin_password, UserRole.admin)
    else:
        print("Bootstrap skipped. Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD to create an admin user.")
