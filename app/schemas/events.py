from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


NotificationType = Literal[
    "Message",
    "New_post",
    "Test",
    "New_achievement",
    "Reservation_alert",
]

UrgencyType = Literal["Low", "Medium", "High"]
DistanceBucketType = Literal["500m", "1km", "5km"]
OriginType = Literal["map", "list"]


class NotificationCommandEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    event_id: UUID = Field(default_factory=uuid4, alias="eventId")
    user_id: UUID = Field(alias="userId")
    title: str
    body: str
    type: NotificationType
    save: bool
    meta: dict[str, Any] = Field(default_factory=dict)


class BeneficiarySearchPerformedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    event_id: UUID = Field(alias="eventId")
    timestamp: datetime
    event_name: Literal["BeneficiarySearchPerformed"] = Field(alias="eventName")
    user_id: UUID = Field(alias="userId")
    category_id: UUID | None = Field(default=None, alias="categoryId")
    urgency: UrgencyType | None = None
    distance_bucket: DistanceBucketType | None = Field(default=None, alias="distanceBucket")
    origin: OriginType | None = None

    @field_validator("origin")
    @classmethod
    def validate_origin(cls, value: OriginType | None) -> OriginType | None:
        return value


class DonationPublishedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    event_id: UUID = Field(alias="eventId")
    timestamp: datetime
    event_name: Literal["DonationPublished"] = Field(alias="eventName")
    donor_id: UUID = Field(alias="donorId")
    donation_id: UUID = Field(alias="donationId")
    category_id: UUID | None = Field(default=None, alias="categoryId")
    urgency: UrgencyType | None = None
    safety_checklist_completed: bool = Field(alias="safetyChecklistCompleted")
    metadata: dict[str, Any] = Field(default_factory=dict)
