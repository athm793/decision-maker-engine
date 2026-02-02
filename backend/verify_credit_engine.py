from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.credit_ledger import CreditLedger
from app.services.credits_engine import grant_business_topup, grant_monthly_credits, recalculate_effective_balance, spend_credits_for_job


def main() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        user_id = "user-1"
        period_end = datetime.now(timezone.utc) + timedelta(days=30)
        grant_monthly_credits(db, user_id=user_id, plan_key="trial", current_period_end=period_end, source="test_trial")
        bal = recalculate_effective_balance(db, user_id)
        assert bal == 500, bal

        grant_monthly_credits(db, user_id=user_id, plan_key="entry", current_period_end=period_end, source="test_entry")
        bal = recalculate_effective_balance(db, user_id)
        assert bal == 7750, bal

        spend_credits_for_job(db, user_id=user_id, amount=10, job_id=1)
        bal2 = recalculate_effective_balance(db, user_id)
        assert bal2 == 7740, bal2

        grant_business_topup(db, user_id=user_id, credits=7000, source="test_topup")
        bal3 = recalculate_effective_balance(db, user_id)
        assert bal3 == 14740, bal3

        spend_credits_for_job(db, user_id=user_id, amount=5000, job_id=2)
        bal4 = recalculate_effective_balance(db, user_id)
        assert bal4 == 9740, bal4

        rows = db.query(CreditLedger).filter(CreditLedger.user_id == user_id).all()
        assert any(r.delta < 0 for r in rows)
        assert any(r.delta > 0 and r.lot_id for r in rows)
    finally:
        db.close()


if __name__ == "__main__":
    main()
    print("OK")
