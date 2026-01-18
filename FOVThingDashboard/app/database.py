from datetime import datetime
from pathlib import Path   
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import os

Base = declarative_base()


class Device(Base):
    __tablename__ = 'devices'
    stadium = Column(String, nullable=False, index=True)
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)
    wifi_connected = Column(Boolean, default=False)
    last_message_time = Column(DateTime)
    first_seen = Column(DateTime, default=datetime.utcnow)

    # Latest known values
    last_metric_values = Column(String)
    # JSON string now includes:
    # {
    #   "battery": "85.5",
    #   "temperature": "24.3",
    #   "version": "1.1.0",
    #   "ota": {
    #     "status": "success|error|in_progress",
    #     "event": "updateFirmware",
    #     "message": "Firmware written successfully",
    #     "timestamp": "2024-02-20T10:00:00Z"
    #   }
    # }

    # Relationship to DeviceLog
    logs = relationship("DeviceLog", back_populates="device", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_device_last_message', 'last_message_time'),
    )


class DeviceLog(Base):
    __tablename__ = 'device_logs'

    id = Column(Integer, primary_key=True)
    device_id = Column(Integer, ForeignKey('devices.id'), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    metric_type = Column(String, nullable=False)  # 'battery', 'temperature', 'version' or 'ota'
    metric_value = Column(String, nullable=False)  # Store all values as strings

    # Relationship to Device
    device = relationship("Device", back_populates="logs")

    __table_args__ = (
        # Composite index for efficient querying of device history
        Index('idx_device_metric_time', 'device_id', 'metric_type', 'timestamp'),
    )

def init_db() -> sessionmaker:
    """
    Initialise the SQLite DB and return a Session factory.

    • If $DB_PATH is set → use that.
    • Otherwise create ./fov_dashboard.db next to this file.
    • Always create the parent directory if it doesn't exist.
    """
    default_path = Path(__file__).with_name("fov_dashboard.db")
    db_path      = Path(os.getenv("DB_PATH", default_path)).expanduser().resolve()

    # Make sure the folder exists (works on Windows & Linux)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Path must be POSIX-style for SQLAlchemy URI; as_posix() does that
    db_url = f"sqlite:///{db_path.as_posix()}"
    print(f"Opening SQLite DB at: {db_path}")   # handy log

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)