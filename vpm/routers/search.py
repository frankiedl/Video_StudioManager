from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from .. import access, auth, models
from ..database import get_db

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def search(q: str, db: Session = Depends(get_db), me: models.User | None = Depends(auth.current_user)):
    query = q.strip()
    if not query:
        raise HTTPException(400, "El parámetro q no puede estar vacío")

    ilike_query = f"%{query.lower()}%"

    projects = (
        db.query(models.Project)
        .filter(func.lower(models.Project.name).like(ilike_query))
        .all()
    )

    tasks = (
        db.query(models.Task)
        .filter(
            or_(
                func.lower(models.Task.title).like(ilike_query),
                func.lower(models.Task.description).like(ilike_query),
            )
        )
        .all()
    )

    assets = (
        db.query(models.AssetMeta)
        .filter(
            or_(
                func.lower(models.AssetMeta.rel_path).like(ilike_query),
                func.lower(models.AssetMeta.notes).like(ilike_query),
            )
        )
        .all()
    )

    results = []
    project_ids = {project.id for project in projects}

    task_project_ids = {task.task_list.project_id for task in tasks if task.task_list}
    asset_project_ids = {asset.project_id for asset in assets}

    project_ids.update(task_project_ids)
    project_ids.update(asset_project_ids)

    if project_ids:
        project_rows = db.query(models.Project).filter(models.Project.id.in_(project_ids)).all()
        for project in project_rows:
            results.append({
                "type": "project",
                "id": project.id,
                "name": project.name,
                "project_type": project.project_type,
            })

    for task in tasks:
        results.append({
            "type": "task",
            "id": task.id,
            "title": task.title,
            "project_id": task.task_list.project_id if task.task_list else None,
        })
    for asset in assets:
        results.append({
            "type": "asset",
            "id": asset.id,
            "rel_path": asset.rel_path,
            "project_id": asset.project_id,
        })

    ids = access.visible_project_ids(db, me)
    if ids is not None:
        results = [r for r in results if (r.get("project_id") or r["id"]) in ids]
    return results
