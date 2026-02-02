# backend/db/models.py
from __future__ import annotations

import uuid
from sqlalchemy import (
    Column,
    Text,
    Boolean,
    Integer,
    ForeignKey,
    DateTime,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(Text, nullable=False, unique=True, index=True)
    password_hash = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class League(Base):
    __tablename__ = "leagues"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(Text, nullable=False, unique=True, index=True)
    name = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default="lobby")  # lobby | drafting | locked
    commissioner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class LeagueMember(Base):
    __tablename__ = "league_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    league_id = Column(UUID(as_uuid=True), ForeignKey("leagues.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    joined_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("league_id", "user_id", name="uq_league_member"),)


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sport = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    event_key = Column(Text, nullable=False, unique=True)
    is_team_event = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, unique=True)


class DraftPick(Base):
    """
    One pick per user per event per league.
    No duplicate entry per league+event (so two people can't draft the same athlete/team/country).
    """
    __tablename__ = "draft_picks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    league_id = Column(UUID(as_uuid=True), ForeignKey("leagues.id"), nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # “entry_key” is the unique identifier you decide for an athlete/team/country (string).
    entry_key = Column(Text, nullable=False)
    entry_name = Column(Text, nullable=False)

    picked_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("league_id", "event_id", "user_id", name="uq_pick_user_per_event"),
        UniqueConstraint("league_id", "event_id", "entry_key", name="uq_pick_no_dupe_entry"),
    )


class LeagueEventResult(Base):
    """
    Manual top-8 results per league per event (simplest).
    One entry per place. Prevent duplicates.
    """
    __tablename__ = "league_event_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    league_id = Column(UUID(as_uuid=True), ForeignKey("leagues.id"), nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False, index=True)

    place = Column(Integer, nullable=False)  # 1..8
    entry_key = Column(Text, nullable=False)
    entry_name = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("league_id", "event_id", "place", name="uq_result_place"),
        UniqueConstraint("league_id", "event_id", "entry_key", name="uq_result_no_dupe_entry"),
    )
