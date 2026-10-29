from sqlalchemy import Column, Integer, String, ForeignKey
from database import Base

class Route(Base):
    __tablename__ = "routes"
    
    route_id = Column(String, primary_key=True, index=True)
    route_short_name = Column(String, nullable=True)
    route_long_name = Column(String, nullable=True)
    route_type = Column(Integer, nullable=True)

class Trip(Base):
    __tablename__ = "trips"
    
    trip_id = Column(String, primary_key=True, index=True)
    route_id = Column(String, ForeignKey("routes.route_id"), nullable=False, index=True)
    service_id = Column(String, index=True)
    trip_headsign = Column(String, nullable=True)
    shape_id = Column(String, nullable=True, index=True)

class Shape(Base):
    __tablename__ = "shapes"

    shape_id = Column(String, primary_key=True, index=True)
    shape_pt_sequence = Column(Integer, primary_key=True)
    shape_pt_lat = Column(String, nullable=False)
    shape_pt_lon = Column(String, nullable=False)

class Stop(Base):
    __tablename__ = "stops"
    
    stop_id = Column(String, primary_key=True, index=True)
    stop_name = Column(String, nullable=False, index=True)
    stop_lat = Column(String, nullable=True)
    stop_lon = Column(String, nullable=True)

class StopTime(Base):
    __tablename__ = "stop_times"

    trip_id = Column(String, ForeignKey("trips.trip_id"), primary_key=True, index=True)
    stop_id = Column(String, ForeignKey("stops.stop_id"), nullable=False, index=True)
    arrival_time = Column(String, nullable=False)
    departure_time = Column(String, nullable=False, index=True)
    stop_sequence = Column(Integer, primary_key=True, index=True)

class Calendar(Base):
    __tablename__ = "calendars"
  
    service_id = Column(String, primary_key=True)
    monday = Column(Integer, nullable=False)
    tuesday = Column(Integer, nullable=False)
    wednesday = Column(Integer, nullable=False)
    thursday = Column(Integer, nullable=False)
    friday = Column(Integer, nullable=False)
    saturday = Column(Integer, nullable=False)
    sunday = Column(Integer, nullable=False)
    start_date = Column(Integer, nullable=False)
    end_date = Column(Integer, nullable=False)


class CalendarDate(Base):
    __tablename__ = "calendar_dates"

    service_id = Column(String, primary_key=True)
    date = Column(Integer, primary_key=True)
    exception_type = Column(Integer, nullable=False)

    

    


class FeedInfo(Base):
    __tablename__ = "feed_info"

    feed_version = Column(String, primary_key=True)
    feed_publisher_name = Column(String, nullable=True)
    feed_publisher_url = Column(String, nullable=True)
    feed_lang = Column(String, nullable=True)
    feed_start_date = Column(String, nullable=True)
    feed_end_date = Column(String, nullable=True)
    feed_contact_url = Column(String, nullable=True)
