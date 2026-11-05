import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class UserIn(BaseModel):
    name: str
    email: str
    color: Optional[str] = "#6c5ce7"


class UserCreate(UserIn):
    password: Optional[str] = None
    role: Optional[str] = "member"


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    color: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None


class UserOut(UserIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: Optional[str] = "member"


class LoginIn(BaseModel):
    email: str
    password: str


class SetupIn(UserIn):
    password: str
    mode: Optional[str] = "studio"  # "team" | "studio"


class ModeIn(BaseModel):
    mode: str


class ProjectIn(BaseModel):
    name: str
    project_type: str = "Vídeo"
    root_path: str
    color: Optional[str] = "#3B82F6"
    create_structure: bool = True


class ProjectPatch(BaseModel):
    name: Optional[str] = None
    project_type: Optional[str] = None
    root_path: Optional[str] = None
    color: Optional[str] = None
    statuses: Optional[list[str]] = None
    archived: Optional[bool] = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    project_type: str
    root_path: str
    color: str
    statuses: list[str]
    archived: bool
    created_at: datetime.datetime


class TaskListIn(BaseModel):
    project_id: str
    name: str
    folder_path: str = ""


class TaskListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    name: str
    folder_path: str
    position: int


class TaskIn(BaseModel):
    task_list_id: str
    title: str
    description: str = ""
    status: str = "Por hacer"
    priority: str = "Media"
    assignee_id: Optional[str] = None
    start_date: Optional[datetime.datetime] = None
    due_date: Optional[datetime.datetime] = None
    tags: list[str] = []


class TaskPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_id: Optional[str] = None
    start_date: Optional[datetime.datetime] = None
    due_date: Optional[datetime.datetime] = None
    tags: Optional[list[str]] = None
    position: Optional[int] = None
    task_list_id: Optional[str] = None
    clear_start_date: Optional[bool] = False
    clear_due_date: Optional[bool] = False
    clear_assignee: Optional[bool] = False


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_list_id: str
    title: str
    description: str
    status: str
    priority: str
    assignee_id: Optional[str]
    start_date: Optional[datetime.datetime]
    due_date: Optional[datetime.datetime]
    tags: list[str]
    position: int
    gcal_event_id: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime


class CommentIn(BaseModel):
    task_id: Optional[str] = None
    project_id: Optional[str] = None
    asset_rel_path: Optional[str] = None
    author_id: Optional[str] = None
    body: str


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: Optional[str]
    project_id: Optional[str]
    asset_rel_path: Optional[str]
    author_id: Optional[str]
    body: str
    created_at: datetime.datetime


class AssetMetaPatch(BaseModel):
    status: Optional[str] = None
    assignee_id: Optional[str] = None
    tags: Optional[list[str]] = None
    starred: Optional[bool] = None
    notes: Optional[str] = None
    color: Optional[str] = None


class LockIn(BaseModel):
    project_id: str
    rel_path: str
    note: Optional[str] = None
    user_id: Optional[str] = None  # only used when auth is off


class LockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    project_id: str
    rel_path: str
    user_id: str
    note: Optional[str] = None
    created_at: datetime.datetime
    heartbeat_at: datetime.datetime


class MemberIn(BaseModel):
    user_id: str
    role: str = "editor"


class MemberOut(MemberIn):
    model_config = ConfigDict(from_attributes=True)


class VersionIn(BaseModel):
    project_id: str
    rel_path: str
    note: Optional[str] = None


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    rel_path: str
    sha256: str
    size: int = 0
    user_id: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime.datetime


class RenamePayload(BaseModel):
    project_id: str
    rel_path: str
    new_name: str


class NotificationIn(BaseModel):
    project_id: str
    rel_path: str
    to_user_id: str
    from_user_id: Optional[str] = None
    message: str = ""


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    rel_path: str
    from_user_id: Optional[str]
    to_user_id: str
    message: str
    read: bool
    created_at: datetime.datetime
