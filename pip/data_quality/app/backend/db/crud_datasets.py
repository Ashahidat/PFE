from sqlalchemy.orm import Session
from db.datasets import Dataset
import uuid

from sqlalchemy.orm import Session
from db.datasets import Dataset
import uuid


def create_dataset(
    db: Session,
    name: str,
    file_path: str,
    hash_value: str,
    columns_list: list,
    owner_employee_id: str = None,
    atlas_guid: str = None,
    project_id: uuid.UUID = None,
    description: str = None  # ✅ ajouté
):
    dataset = Dataset(
        id=uuid.uuid4(),  # cohérent avec UUID(as_uuid=True)
        name=name,
        file_path=file_path,
        hash=hash_value,
        columns_list=columns_list,
        owner_employee_id=owner_employee_id,
        atlas_guid=atlas_guid,
        project_id=project_id,
        description=description  # ✅ ajouté
    )

    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    return dataset