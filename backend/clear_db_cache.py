from app.database import SessionLocal, engine, Base
from app.models.db_models import Session, Conversation, Document, Chunk, EvaluationResult

def clean_db():
    print("Connecting to DB...")
    db = SessionLocal()
    try:
        print("Clearing conversations...")
        db.query(Conversation).delete()
        print("Clearing sessions...")
        db.query(Session).delete()
        db.commit()
        print("Done clearing DB caches!")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clean_db()
