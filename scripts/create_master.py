"""Bootstrap CLI: create the first master user.

The POST /users endpoint requires a master JWT, which creates a chicken-and-egg
problem for the very first user. This script writes directly to the database,
bypassing the endpoint.

Usage:
    python scripts/create_master.py --email admin@example.com --name "Admin" --password "...."

After running, login via POST /auth/login with these credentials to get a JWT,
then use that JWT to register additional users via POST /users.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select  # noqa: E402

from domain.auth.enums import Role  # noqa: E402
from domain.models.user import User  # noqa: E402
from services.auth_service import ensure_role, hash_password  # noqa: E402
from utils.database import SessionLocal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    if len(args.password) < 8:
        print("ERROR: password must be at least 8 characters.", file=sys.stderr)
        return 2

    with SessionLocal() as session:
        existing = session.scalar(select(User).where(User.email == args.email))
        if existing is not None:
            print(
                f"ERROR: user with email {args.email} already exists.", file=sys.stderr
            )
            return 1

        master_role = ensure_role(session, Role.MASTER)
        user = User(
            role_id=master_role.id,
            organization_id=None,
            name=args.name,
            email=args.email,
            phone=None,
            password_hash=hash_password(args.password),
            verified=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        print("Master user created.")
        print(f"  id:    {user.id}")
        print(f"  email: {user.email}")
        print("  role:  master")
        print()
        print("Login via POST /auth/login to get a JWT.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
