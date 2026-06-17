"""001_initial_schema

Create all GridSense tables: incidents, corridor_risk_index,
corridor_station_map, station_concurrency, duration_lookup.

Revision ID: 001
Revises:
Create Date: 2024-06-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── incidents ──────────────────────────────────────────────────────────────
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("event_cause", sa.String(50), nullable=False),
        sa.Column("latitude", sa.Float, nullable=False),
        sa.Column("longitude", sa.Float, nullable=False),
        sa.Column("address", sa.Text),
        sa.Column("corridor", sa.String(100)),
        sa.Column("junction", sa.String(100)),
        sa.Column("zone", sa.String(50)),
        sa.Column("police_station", sa.String(100), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("requires_road_closure", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("vehicle_type", sa.String(30)),
        sa.Column("start_datetime", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("end_datetime", postgresql.TIMESTAMP(timezone=True)),
        sa.Column("closed_datetime", postgresql.TIMESTAMP(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("is_stale_active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("duration_mins", sa.Float),
        sa.Column("hour_of_day", sa.Integer),
        sa.Column("day_of_week", sa.Integer),
        sa.Column("month", sa.Integer),
        sa.Column("is_high_priority_corridor", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_non_corridor", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("description", sa.Text),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("idx_incidents_corridor", "incidents", ["corridor"])
    op.create_index("idx_incidents_junction", "incidents", ["junction"])
    op.create_index("idx_incidents_start_datetime", "incidents", ["start_datetime"])
    op.create_index("idx_incidents_status", "incidents", ["status"])
    op.create_index("idx_incidents_priority", "incidents", ["priority"])
    op.create_index("idx_incidents_police_station", "incidents", ["police_station"])
    op.create_index("idx_incidents_geo", "incidents", ["latitude", "longitude"])
    op.create_index(
        "idx_incidents_non_stale_corridor",
        "incidents",
        ["corridor"],
        postgresql_where=sa.text("is_stale_active = FALSE"),
    )

    # ── corridor_risk_index ────────────────────────────────────────────────────
    op.create_table(
        "corridor_risk_index",
        sa.Column("corridor", sa.String(100), primary_key=True),
        sa.Column("total_incidents", sa.Integer, nullable=False),
        sa.Column("high_priority_count", sa.Integer, nullable=False),
        sa.Column("high_priority_rate", sa.Float, nullable=False),
        sa.Column("closure_count", sa.Integer, nullable=False),
        sa.Column("closure_rate", sa.Float, nullable=False),
        sa.Column("composite_risk_score", sa.Float, nullable=False),
        sa.Column("top_junction", sa.String(100)),
        sa.Column("top_police_station", sa.String(100)),
        sa.Column("median_duration_mins", sa.Float),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # ── corridor_station_map ───────────────────────────────────────────────────
    op.create_table(
        "corridor_station_map",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "corridor",
            sa.String(100),
            sa.ForeignKey("corridor_risk_index.corridor", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("police_station", sa.String(100), nullable=False),
        sa.Column("incident_count", sa.Integer, nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.UniqueConstraint("corridor", "rank", name="uq_corridor_rank"),
    )

    # ── station_concurrency ────────────────────────────────────────────────────
    op.create_table(
        "station_concurrency",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("police_station", sa.String(100), nullable=False),
        sa.Column("hour_of_day", sa.Integer, nullable=False),
        sa.Column("day_of_week", sa.Integer, nullable=False),
        sa.Column("avg_concurrent", sa.Float, nullable=False),
        sa.Column("max_concurrent", sa.Integer, nullable=False),
        sa.UniqueConstraint(
            "police_station", "hour_of_day", "day_of_week",
            name="uq_station_hour_dow",
        ),
    )

    # ── duration_lookup ────────────────────────────────────────────────────────
    op.create_table(
        "duration_lookup",
        sa.Column("event_cause", sa.String(50), primary_key=True),
        sa.Column("median_duration_mins", sa.Float, nullable=False),
        sa.Column("p25_duration_mins", sa.Float),
        sa.Column("p75_duration_mins", sa.Float),
        sa.Column("sample_count", sa.Integer, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("duration_lookup")
    op.drop_table("station_concurrency")
    op.drop_table("corridor_station_map")
    op.drop_table("corridor_risk_index")
    op.drop_index("idx_incidents_non_stale_corridor", table_name="incidents")
    op.drop_index("idx_incidents_geo", table_name="incidents")
    op.drop_index("idx_incidents_police_station", table_name="incidents")
    op.drop_index("idx_incidents_priority", table_name="incidents")
    op.drop_index("idx_incidents_status", table_name="incidents")
    op.drop_index("idx_incidents_start_datetime", table_name="incidents")
    op.drop_index("idx_incidents_junction", table_name="incidents")
    op.drop_index("idx_incidents_corridor", table_name="incidents")
    op.drop_table("incidents")