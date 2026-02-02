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
    atlas_guid: str = None  # ajouté pour la nouvelle colonne
):
    dataset = Dataset(
        id=uuid.uuid4(),
        name=name,
        file_path=file_path,
        hash=hash_value,
        columns_list=columns_list,
        owner_employee_id=owner_employee_id,
        atlas_guid=atlas_guid
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset
