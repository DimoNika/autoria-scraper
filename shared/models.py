from sqlalchemy import Column, DateTime, String, Integer, func, ForeignKey, Boolean, Table
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base



Base = declarative_base()
metadata = Base.metadata

#  === Models ===

class Car(Base):
    __tablename__ = "car"
    id = Column(Integer, primary_key=True)
    url = Column(String(1000), unique=True, nullable=False)
    title = Column(String(1000), unique=False, nullable=False)
    price_usd = Column(Integer, unique=False, nullable=False)
    odometer = Column(Integer, unique=False, nullable=False)
    username = Column(String(1000), unique=False, nullable=False)
    phone_number = Column(Integer, unique=False, nullable=False)

    image_url = Column(String(2000), unique=False, nullable=False)
    images_count = Column(Integer, unique=False, nullable=False)

    car_vin = Column(String(100), unique=False, nullable=False)


    car_number = Column(String(100), unique=False, nullable=False)

    datetime_found = Column(DateTime, default=func.now())


class UrlQueue(Base):
    __tablename__ = "url_queue"
    id = Column(Integer, primary_key=True)
    url = Column(String(1000), unique=True, nullable=False)
    is_processed = Column(Boolean, unique=False, nullable=False)

    def __init__(self, url: str):
        self.url = url
