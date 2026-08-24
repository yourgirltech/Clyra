from app.db.database import SessionLocal
from app import models
s=SessionLocal()
claim = s.query(models.Claim).filter(models.Claim.patient_id!=None).first()
if claim:
    print({
        'claim_id': claim.claim_id,
        'patient_id': claim.patient_id,
        'patient_name': f"{claim.patient.first_name} {claim.patient.last_name}".strip(),
        'payer_name': getattr(claim.payer,'name',None),
        'amount': float(claim.amount),
        'risk_level': claim.risk_level,
        'risk_score': claim.risk_score,
    })
else:
    print('no claim with patient')
s.close()
