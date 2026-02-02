# backend/db/init_db.py
from db.session import engine
from db.models import Base

def main():
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created (if they didn't already exist).")

if __name__ == "__main__":
    main()
