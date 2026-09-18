from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class LocationOptionsResponse(BaseModel):
    states: List[str]
    districts: List[str]
    constituencies: List[str]


class LocationResolveRequest(BaseModel):
    lat: float
    lng: float


class LocationResolveResponse(BaseModel):
    state: Optional[str] = None
    district: Optional[str] = None
    constituency: Optional[str] = None
    constituency_options: List[str] = []


class RequestOTPRequest(BaseModel):
    email: str


class RequestOTPResponse(BaseModel):
    message: str = "OTP sent"


class VerifyOTPRequest(BaseModel):
    email: str
    otp: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    state: Optional[str] = None
    district: Optional[str] = None
    constituency: Optional[str] = None
    xp: int = 0


class VerifyOTPResponse(BaseModel):
    access_token: str
    user: UserResponse


class UpdateLocationRequest(BaseModel):
    state: str
    district: str
    constituency: Optional[str] = None


class AuditorLoginRequest(BaseModel):
    username: str
    password: str


class AuditorLoginResponse(BaseModel):
    access_token: str


class WorkItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    work_code: Optional[str] = None
    work_type: str
    description: str
    mp_name: Optional[str] = None
    state: str
    district: str
    constituency: Optional[str] = None
    amount: Optional[float] = None
    completion_date: Optional[date] = None
    my_submission_status: Optional[str] = None


class WorksListResponse(BaseModel):
    items: List[WorkItemResponse]
    total: int
    page: int
    page_size: int


class SubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    work_id: int
    image_path: str
    status: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    reject_reason: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None


class AuditorSubmissionWorkDetails(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    work_code: Optional[str] = None
    work_type: str
    description: str
    mp_name: Optional[str] = None
    state: str
    district: str
    constituency: Optional[str] = None


class AuditorSubmissionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    user_email: str
    work_id: int
    work: AuditorSubmissionWorkDetails
    image_path: str
    status: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    reject_reason: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None


class RejectSubmissionRequest(BaseModel):
    reason: str
