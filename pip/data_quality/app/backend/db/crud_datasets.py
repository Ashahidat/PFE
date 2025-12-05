from sqlalchemy.orm import Session
from db.datasets import Dataset
import uuid
import datetime

def create_dataset(db: Session, name: str, file_path: str, hash_value: str, columns_list: list):
    dataset = Dataset(
        id=uuid.uuid4(),
        name=name,
        file_path=file_path,
        hash=hash_value,
        columns_list=columns_list
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset
