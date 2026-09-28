from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Camera, CameraStatusHistory, User, WatchlistEntry
from .schemas import AnalyticsEventCreate
from .security import hash_password
from .services.analytics_service import ingest_event


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(User.id).limit(1)) is None:
        db.add_all(
            [
                User(
                    username="admin",
                    display_name="Platform Administrator",
                    password_hash=hash_password(settings.demo_admin_password),
                    role="admin",
                    department="Control Room",
                ),
                User(
                    username="operator",
                    display_name="Control Room Operator",
                    password_hash=hash_password(settings.demo_operator_password),
                    role="operator",
                    department="Operations",
                ),
            ]
        )
        db.commit()

    if db.scalar(select(Camera.id).limit(1)) is None:
        now = datetime.now(timezone.utc)
        cameras = [
            Camera(
                camera_id="C001",
                name="Ahmedabad Traffic Junction",
                department="City Police",
                latitude=23.0225,
                longitude=72.5714,
                camera_type="ANPR_FIXED",
                source_protocol="RTSP",
                stream_endpoint="sim://rtsp/ahmedabad/junction-01",
                status="ONLINE",
                last_heartbeat=now,
                zone="West Ahmedabad",
                storage_provider="Regional object store",
                storage_bucket="cctv-west-hot",
                storage_retention_days=15,
                coverage_area="4-lane junction and crossing",
                extra_data={"vendor": "SyntheticVMS", "model": "ANPR-Edge-4K", "fov_deg": 110},
            ),
            Camera(
                camera_id="C002",
                name="RTO Checkpoint East",
                department="Transport Department",
                latitude=23.0451,
                longitude=72.6498,
                camera_type="PTZ_DOME",
                source_protocol="ONVIF",
                stream_endpoint="sim://onvif/rto/checkpoint-east",
                status="ONLINE",
                last_heartbeat=now,
                zone="RTO East",
                storage_provider="Department NVR",
                storage_bucket="rto-nvr-02",
                storage_retention_days=30,
                coverage_area="Vehicle inspection lanes",
                extra_data={"vendor": "TranscendVMS", "onvif_profile": "T"},
            ),
            Camera(
                camera_id="C003",
                name="Sabarmati Bridge Approach",
                department="Municipal Corporation",
                latitude=23.0608,
                longitude=72.5809,
                camera_type="VEHICLE_DETECTION",
                source_protocol="RTSP",
                stream_endpoint="sim://rtsp/bridge/approach-02",
                status="DEGRADED",
                last_heartbeat=now - timedelta(minutes=4),
                zone="Sabarmati Corridor",
                storage_provider="Edge NAS",
                storage_bucket="edge-nas-west",
                storage_retention_days=7,
                coverage_area="Bridge approach and transit lanes",
                extra_data={"vendor": "CityView", "health_note": "Packet loss above threshold"},
            ),
            Camera(
                camera_id="C004",
                name="Gandhinagar Sector 11 Gate",
                department="Home Department",
                latitude=23.2235,
                longitude=72.6497,
                camera_type="FIXED_DOME",
                source_protocol="ONVIF",
                stream_endpoint="sim://onvif/home/sector-11-gate",
                status="ONLINE",
                last_heartbeat=now,
                zone="Gandhinagar North",
                storage_provider="Regional object store",
                storage_bucket="cctv-north-hot",
                storage_retention_days=15,
                coverage_area="Restricted gate perimeter",
                extra_data={"vendor": "SecureCity", "onvif_profile": "S"},
            ),
            Camera(
                camera_id="C005",
                name="Sardar Bridge Entry",
                department="Traffic Police",
                latitude=23.0521,
                longitude=72.5324,
                camera_type="ANPR_FIXED",
                source_protocol="RTSP",
                stream_endpoint="sim://rtsp/sardar/entry-01",
                status="ONLINE",
                last_heartbeat=now,
                zone="South Ahmedabad",
                storage_provider="Regional object store",
                storage_bucket="cctv-south-hot",
                storage_retention_days=15,
                coverage_area="Bridge entry and speed monitoring",
                extra_data={"vendor": "RoadEye", "edge_gateway": "west-02"},
            ),
            Camera(
                camera_id="C006",
                name="PDS Warehouse Yard",
                department="Food & Civil Supplies",
                latitude=22.9925,
                longitude=72.3812,
                camera_type="FIXED_DOME",
                source_protocol="ONVIF",
                stream_endpoint="sim://onvif/pds/yard-01",
                status="OFFLINE",
                last_heartbeat=now - timedelta(hours=2),
                zone="East Ahmedabad",
                storage_provider="Department NVR",
                storage_bucket="pds-nvr-01",
                storage_retention_days=30,
                coverage_area="Warehouse loading yard",
                extra_data={"vendor": "FoodWatch", "maintenance_ticket": "GTAI-4821"},
            ),
        ]
        db.add_all(cameras)
        db.flush()
        db.add_all(
            [
                CameraStatusHistory(
                    camera_id=camera.id, status=camera.status, heartbeat_at=camera.last_heartbeat or now
                )
                for camera in cameras
            ]
        )
        db.commit()

    if db.scalar(select(WatchlistEntry.id).limit(1)) is None:
        db.add_all(
            [
                WatchlistEntry(
                    entity_type="VEHICLE",
                    identifier="GJ01AB1234",
                    display_name="Synthetic stolen vehicle",
                    reason="Representative stolen-vehicle record for the prototype",
                    severity="CRITICAL",
                    department="City Police",
                    extra_data={"case_reference": "SYN-2026-001", "source": "synthetic", "last_seen": "Ahmedabad"},
                ),
                WatchlistEntry(
                    entity_type="VEHICLE",
                    identifier="GJ01CD9012",
                    display_name="Synthetic blacklisted vehicle",
                    reason="Representative blacklisted vehicle for correlation testing",
                    severity="HIGH",
                    department="Transport Department",
                    extra_data={"case_reference": "SYN-2026-002", "source": "synthetic"},
                ),
                WatchlistEntry(
                    entity_type="PERSON",
                    identifier="PERSON-0042",
                    display_name="Synthetic wanted person",
                    reason="Representative person-of-interest record",
                    severity="HIGH",
                    department="Home Department",
                    extra_data={"case_reference": "SYN-2026-003", "source": "synthetic"},
                ),
            ]
        )
        db.commit()

    if db.scalar(select(Camera.id).where(Camera.camera_id == "C001")) is not None:
        from .models import AnalyticsEvent

        if db.scalar(select(AnalyticsEvent.id).limit(1)) is None:
            now = datetime.now(timezone.utc)
            historical_events = [
                AnalyticsEventCreate(
                    camera_id="C001",
                    event_type="ANPR",
                    occurred_at=now - timedelta(minutes=39),
                    entity_type="VEHICLE",
                    entity_identifier="GJ01AB1234",
                    confidence=0.987,
                    vehicle_type="CAR",
                    source="adapter:rtsp",
                    metadata={"simulated": True, "sequence": 1},
                    idempotency_key="seed-c001-gj01ab1234",
                ),
                AnalyticsEventCreate(
                    camera_id="C003",
                    event_type="ANPR",
                    occurred_at=now - timedelta(minutes=23),
                    entity_type="VEHICLE",
                    entity_identifier="GJ01AB1234",
                    confidence=0.972,
                    vehicle_type="CAR",
                    source="adapter:rtsp",
                    metadata={"simulated": True, "sequence": 2},
                    idempotency_key="seed-c003-gj01ab1234",
                ),
                AnalyticsEventCreate(
                    camera_id="C005",
                    event_type="ANPR",
                    occurred_at=now - timedelta(minutes=2),
                    entity_type="VEHICLE",
                    entity_identifier="GJ01AB1234",
                    confidence=0.994,
                    vehicle_type="CAR",
                    source="adapter:rtsp",
                    metadata={"simulated": True, "sequence": 3},
                    idempotency_key="seed-c005-gj01ab1234",
                ),
            ]
            for event in historical_events:
                ingest_event(db, event)
