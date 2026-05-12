import asyncio
from app.database import SessionLocal
from app.models.db_models import User

db = SessionLocal()
try:
    test_pwd_hash = '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW'
    admin_user = db.query(User).filter(User.email == 'admin@bssn.go.id').first()
    if not admin_user:
        admin_user = User(
            name='Admin PUSDATIK', 
            email='admin@bssn.go.id',
            hashed_password=test_pwd_hash,
            roles='["admin_pusdatik"]',
            department='PUSDATIK'
        )
        db.add(admin_user)
        db.commit()
        print('[OK] Test user created: admin@bssn.go.id')
    else:
        # Update hash if it exists but is wrong
        admin_user.hashed_password = test_pwd_hash
        admin_user.roles = '["admin_pusdatik"]'
        db.commit()
        print('[OK] Test user updated: admin@bssn.go.id')
        
    eval_user = db.query(User).filter(User.email == 'evaluator@bssn.go.id').first()
    if not eval_user:
        eval_user = User(
            name='Evaluator SPBE', 
            email='evaluator@bssn.go.id',
            hashed_password=test_pwd_hash,
            roles='["evaluator_spbe"]',
            department='DEPUTI_EVALUASI'
        )
        db.add(eval_user)
        db.commit()
        print('[OK] Test user created: evaluator@bssn.go.id')
    else:
        eval_user.hashed_password = test_pwd_hash
        eval_user.roles = '["evaluator_spbe"]'
        db.commit()
        print('[OK] Test user updated: evaluator@bssn.go.id')
finally:
    db.close()
