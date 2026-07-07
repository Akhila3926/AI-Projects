from __future__ import annotations
from sqlalchemy import create_engine, Column, String, text
from sqlalchemy.orm import DeclarativeBase, Session
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data_store" / "care_intelligence.db"
ENGINE = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


class Base(DeclarativeBase):
    pass


class Record(Base):
    """Flat denormalized table — one row = one patient/appointment/claim."""
    __tablename__ = "patients"

    Patient_ID         = Column(String, primary_key=True)
    Full_Name          = Column(String)
    DOB                = Column(String)
    Age                = Column(String)
    Gender             = Column(String)
    Phone_Number       = Column(String)
    Email              = Column(String)
    City               = Column(String)
    State              = Column(String)
    Insurance_Payer    = Column(String)
    Policy_Number      = Column(String)
    Provider           = Column(String)
    Department         = Column(String)
    Appointment_Date   = Column(String)
    Appointment_Type   = Column(String)
    Appointment_Status = Column(String)
    Encounter_ID       = Column(String)
    Diagnosis          = Column(String)
    Clinical_Notes     = Column(String)
    Allergies          = Column(String)
    Procedure          = Column(String)
    Claim_ID           = Column(String)
    Claim_Status       = Column(String)
    Charges_USD        = Column(String)
    Balance_USD        = Column(String)
    Claim_Amount_USD   = Column(String)
    Denial_Reason      = Column(String)
    Last_Updated       = Column(String)


def get_session() -> Session:
    return Session(ENGINE)


def create_tables():
    # Tables already exist — this is a no-op for existing tables
    Base.metadata.create_all(ENGINE)
