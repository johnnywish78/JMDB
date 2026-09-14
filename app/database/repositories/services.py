from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional, Dict
from app.database.models import Service, ApplicationSetting, BrowserSetting

class ServicesRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all_services(self) -> List[Service]:
        return self.db.query(Service).order_by(Service.name).all()

    def get_service(self, sid: int) -> Optional[Service]:
        return self.db.query(Service).filter(Service.id == sid).first()

    def create_service(self, service: Service) -> Service:
        self.db.add(service)
        self.db.commit()
        self.db.refresh(service)
        return service

    def update_service(self, service: Service) -> Service:
        self.db.commit()
        self.db.refresh(service)
        return service

    def update_health(self, sid: int, status: str, error: str = ""):
        s = self.get_service(sid)
        if s:
            s.health_status = status
            s.last_error = error
            if status == "healthy":
                s.last_connected = datetime.utcnow()
            self.db.commit()

class SettingsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> Dict[str, str]:
        return {s.key: s.value for s in self.db.query(ApplicationSetting).all()}

    def set(self, key: str, value: str, category: str = "general"):
        s = self.db.query(ApplicationSetting).filter(ApplicationSetting.key == key).first()
        if s:
            s.value = value
        else:
            self.db.add(ApplicationSetting(key=key, value=value, category=category))
        self.db.commit()

class BrowserSettingsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> Dict[str, str]:
        return {s.key: s.value for s in self.db.query(BrowserSetting).all()}

    def set(self, key: str, value: str, category: str = "general"):
        s = self.db.query(BrowserSetting).filter(BrowserSetting.key == key).first()
        if s:
            s.value = value
        else:
            self.db.add(BrowserSetting(key=key, value=value, category=category))
        self.db.commit()
