from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


NotificationType = Literal["New_post"]
Event_Type = Literal[
    "BeneficiarySearchPerformed",
    "DonationPublished",
    "publish_donation",
    "LikedDonation",
]
UrgencyType = Literal["Low", "Medium", "High"]
DistanceBucketType = Literal["500m", "1km", "5km"]


class Location(BaseModel):
    city: str | None = None
    neighborhood: str | None = None
    country: str | None = None
    latitude: float
    longitude: float


class DonationPublishedEvent(BaseModel):
    eventId: UUID
    timestamp: datetime
    eventName: Literal["DonationPublished", "publish_donation"]
    donorId: UUID
    donationId: UUID
    donationTitle: str
    donationDescription: str | None = None
    category: str
    urgency: UrgencyType
    safetyChecklistCompleted: bool
    quantity: int
    location: Location
    tags: list[str] = Field(default_factory=list)

    @field_validator("category", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        return v if v else None


class DonationLikedEvent(BaseModel):
    eventId: UUID
    timestamp: datetime
    eventName: Literal["LikedDonation"]
    userId: UUID
    likerUserId: UUID
    donationId: UUID
    donationTitle: str
    category: str
    quantity: int
    urgency: UrgencyType
    location: Location


class BeneficiarySearchPerformedEvent(BaseModel):
    eventId: UUID
    timestamp: datetime
    eventName: Literal["BeneficiarySearchPerformed"]
    beneficiaryId: UUID
    category: str | None = None
    location: Location | None = None
    distanceBucket: DistanceBucketType | None = None


class NotificationCommandEvent(BaseModel):
    eventId: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    eventName: Literal["notify_user"] = Field(default="notify_user")
    userId: UUID
    title: str
    body: str
    type: NotificationType = Field(default="New_post")
    save: bool = Field(default=True)
    meta: dict[str, Any] = Field(default_factory=dict)