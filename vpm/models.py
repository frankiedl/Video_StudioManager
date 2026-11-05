import datetime
import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship

from .database import Base


def gen_id():
    return uuid.uuid4().hex


DEFAULT_STATUSES = ["Por hacer", "En progreso", "Revisión", "Hecho"]

PROJECT_TYPES = ["Vídeo", "Animación", "Edición", "3D", "Rodaje", "Otro"]


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    color = Column(String, default="#6c5ce7")
    password_hash = Column(String, nullable=True)
    role = Column(String, default="member")  # "admin" | "member"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash = Column(String, primary_key=True)  # sha256 of the cookie token
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class FileLock(Base):
    __tablename__ = "file_locks"
    __table_args__ = (UniqueConstraint("project_id", "rel_path", name="uq_lock_path"),)
    id = Column(String, primary_key=True, default=gen_id)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    rel_path = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    heartbeat_at = Column(DateTime, default=datetime.datetime.utcnow)


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_member"),)
    id = Column(String, primary_key=True, default=gen_id)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, default="editor")  # viewer | editor | owner


class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    project_type = Column(String, default="Vídeo")
    root_path = Column(String, nullable=False)  # absolute path inside Dropbox folder
    color = Column(String, default="#3B82F6")
    statuses = Column(JSON, default=lambda: list(DEFAULT_STATUSES))
    archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    task_lists = relationship("TaskList", back_populates="project", cascade="all, delete-orphan")


class TaskList(Base):
    __tablename__ = "task_lists"
    id = Column(String, primary_key=True, default=gen_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)
    folder_path = Column(String, default="")  # relative path inside project root, "" = project root
    position = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    project = relationship("Project", back_populates="task_lists")
    tasks = relationship("Task", back_populates="task_list", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True, default=gen_id)
    task_list_id = Column(String, ForeignKey("task_lists.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    status = Column(String, default="Por hacer")
    priority = Column(String, default="Media")  # Baja / Media / Alta / Urgente
    assignee_id = Column(String, ForeignKey("users.id"), nullable=True)
    start_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    tags = Column(JSON, default=list)
    position = Column(Integer, default=0)
    gcal_event_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    task_list = relationship("TaskList", back_populates="tasks")
    assignee = relationship("User")
    comments = relationship("Comment", back_populates="task", cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"
    id = Column(String, primary_key=True, default=gen_id)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    asset_rel_path = Column(String, nullable=True)  # set when the comment is on a file/asset instead of a task
    author_id = Column(String, ForeignKey("users.id"), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    task = relationship("Task", back_populates="comments")
    author = relationship("User")


class AssetMeta(Base):
    """Extra metadata attached to a real file/folder living on disk (identified by project + relative path)."""
    __tablename__ = "asset_meta"
    id = Column(String, primary_key=True, default=gen_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    rel_path = Column(String, nullable=False)
    status = Column(String, nullable=True)
    assignee_id = Column(String, ForeignKey("users.id"), nullable=True)
    tags = Column(JSON, default=list)
    starred = Column(Boolean, default=False)
    notes = Column(Text, default="")
    color = Column(String, nullable=True)  # custom folder color, e.g. "#3B82F6"

    assignee = relationship("User")


class AppSetting(Base):
    __tablename__ = "app_settings"
    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)


class Notification(Base):
    """An in-app 'inbox' entry: a link to a file/folder sent to a teammate.

    This app has no real login system, so "sending to someone's inbox" is simulated:
    the sender picks a recipient from the team list, and the recipient later picks
    themselves in the sidebar "Soy:" selector to see notifications addressed to them.
    """
    __tablename__ = "notifications"
    id = Column(String, primary_key=True, default=gen_id)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    rel_path = Column(String, nullable=False)
    from_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    to_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    message = Column(Text, default="")
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    from_user = relationship("User", foreign_keys=[from_user_id])
    to_user = relationship("User", foreign_keys=[to_user_id])
