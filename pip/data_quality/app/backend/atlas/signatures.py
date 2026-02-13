import hashlib
import logging
import json
import time
from pyspark.sql import functions as F
from rapidfuzz import fuzz
from atlas.client import atlas_get, ATLAS_SEARCH_URL
from atlas.columns import create_columns
from atlas.column_matching import ColumnMatcher
from db.crud_dataset_signatures import create_dataset_signature
from db.crud_column_signatures import create_column_signature
from sqlalchemy.orm import Session
from config import spark

logger = logging.getLogger("atlas.signatures")
logger.setLevel(logging.DEBUG)

def calculate_dataset_signature(df, dataset_name: str, sample_size=200):
    print(f"🔧 DEBUT: calculate_dataset_signature pour '{dataset_name}'")
    print(f"   - Nombre de colonnes: {len(df.columns)}")
    print(f"   - Colonnes: {df.columns}")
    
    sample_df = df.orderBy(F.rand()).limit(sample_size)
    sample_data = {
        col: [str(row[col]) for row in sample_df.select(col).limit(20).collect() if row[col] is not None]
        for col in df.columns
    }

    agg_exprs = []
    for c in df.columns:
        dtype = df.schema[c].dataType.simpleString()
        if "int" in dtype or "double" in dtype or "float" in dtype:
            agg_exprs += [
                F.min(c).alias(f"{c}_min"),
                F.max(c).alias(f"{c}_max"),
                F.mean(c).alias(f"{c}_mean"),
                F.stddev(c).alias(f"{c}_std"),
            ]
        agg_exprs.append(F.approx_count_distinct(c).alias(f"{c}_ndist"))

    stats_row = df.agg(*agg_exprs).collect()[0]

    signature = {
        "name_base": dataset_name.lower().split(".")[0],
        "columns": {},
        "columns_count": len(df.columns),
    }

    for col in df.columns:
        dtype_spark = df.schema[col].dataType.simpleString()
        if "int" in dtype_spark or "double" in dtype_spark or "float" in dtype_spark:
            col_type = "numeric"
        elif "date" in dtype_spark or "timestamp" in dtype_spark:
            col_type = "datetime"
        else:
            col_type = "string"

        min_val = float(stats_row[f"{col}_min"]) if col_type == "numeric" and stats_row[f"{col}_min"] is not None else None
        max_val = float(stats_row[f"{col}_max"]) if col_type == "numeric" and stats_row[f"{col}_max"] is not None else None
        mean_val = float(stats_row[f"{col}_mean"]) if col_type == "numeric" and stats_row[f"{col}_mean"] is not None else None
        std_val = float(stats_row[f"{col}_std"]) if col_type == "numeric" and stats_row[f"{col}_std"] is not None else None
        ndist_val = int(stats_row[f"{col}_ndist"]) if stats_row[f"{col}_ndist"] is not None else 0

        sample_list = sample_data[col][:20]
        sample_hash = hashlib.sha256(str(sample_list).encode()).hexdigest()

        signature["columns"][col] = {
            "dtype": col_type,
            "min": min_val,
            "max": max_val,
            "mean": mean_val,
            "std": std_val,
            "ndist": ndist_val,
            "sample_hash": sample_hash
        }

    struct = [(col, signature["columns"][col]["dtype"]) for col in df.columns]
    signature["structure_hash"] = hashlib.sha256(str(sorted(struct)).encode()).hexdigest()
    signature["rows_count"] = df.count()

    return signature

def compute_similarity_score(sig_current, sig_old):
    cols_new = set(sig_current["columns"].keys())
    cols_old = set(sig_old["columns"].keys())
    jaccard = len(cols_new & cols_old) / len(cols_new | cols_old) if (cols_new | cols_old) else 0
    
    common = cols_new & cols_old
    type_matches = sum(1 for c in common if sig_current["columns"][c]["dtype"] == sig_old["columns"][c]["dtype"])
    type_score = type_matches / max(len(common), 1)
    
    structure_score = 0.60 * (0.7 * jaccard + 0.3 * type_score)
    name_similarity = fuzz.partial_ratio(sig_current["name_base"], sig_old["name_base"]) / 100.0
    name_score = 0.30 * name_similarity
    
    sample_matches = sum(1 for c in common if sig_current["columns"][c]["sample_hash"] == sig_old["columns"][c]["sample_hash"])
    data_ratio = sample_matches / max(len(common), 1)
    data_score = data_ratio * 0.10
    
    return structure_score + name_score + data_score

def ensure_parent_columns(parent_guid, parent_name, parent_qualified_name):
    """
    Crée les colonnes du parent SEULEMENT SI ELLES N'EXISTENT PAS
    ET retourne (entities, column_mapping avec VRAIS GUIDs)
    """
    from db.connexion_db import get_db
    from db.datasets import Dataset
    from atlas.column_matching import ColumnMatcher
    
    logger.info(f"🔧 VÉRIFICATION des colonnes pour parent {parent_name}")
    logger.info(f"   GUID: {parent_guid}")
    
    # 🔥 ÉTAPE 1: Vérifier si les colonnes existent déjà dans Atlas
    matcher = ColumnMatcher()
    existing_columns = matcher._get_dataset_columns(parent_guid)
    
    if existing_columns:
        logger.info(f"✅ Les colonnes existent déjà pour {parent_name} ({len(existing_columns)} trouvées)")
        
        # Construire le mapping à partir des colonnes existantes
        column_mapping = {}
        for col in existing_columns:
            attrs = col.get("attributes", {})
            col_name = attrs.get("name")
            col_guid = col.get("guid")
            if col_name and col_guid:
                column_mapping[col_name] = col_guid
                logger.info(f"   - {col_name}: {col_guid} (logicalId: {attrs.get('logicalColumnId', 'N/A')})")
        
        return existing_columns, column_mapping
    
    # Si on arrive ici, les colonnes n'existent pas - on les crée
    logger.warning(f"⚠️ Colonnes non trouvées pour {parent_name}, création...")
    
    # Chercher le parent dans la DB
    db = next(get_db())
    parent_dataset = None
    
    # Par atlas_guid
    if parent_guid:
        parent_dataset = db.query(Dataset).filter(Dataset.atlas_guid == parent_guid).first()
    
    # Par nom
    if not parent_dataset and parent_name:
        parent_dataset = db.query(Dataset).filter(Dataset.name == parent_name).first()
    
    if not parent_dataset:
        logger.error(f"❌ Parent {parent_name} non trouvé dans DB")
        return [], {}
    
    if not parent_dataset.file_path:
        logger.error(f"❌ Parent {parent_name} sans file_path")
        return [], {}
    
    try:
        # Lire le fichier parent
        logger.info(f"📖 Lecture parent: {parent_dataset.file_path}")
        parent_df = spark.read.parquet(parent_dataset.file_path)
        logger.info(f"📊 {len(parent_df.columns)} colonnes dans le fichier parent")
        
        # 🔥 CRÉER LES COLONNES DU PARENT
        logger.info(f"📝 Création de {len(parent_df.columns)} colonnes pour parent...")
        column_mapping, parent_entities = create_columns(
            parent_df,
            parent_guid,
            parent_dataset.hash,
            parent_dataset_guid=None,
            parent_columns=None,
            parent_column_mapping=None
        )
        
        logger.info(f"✅ {len(column_mapping)} colonnes créées pour parent")
        logger.info(f"📋 Mapping colonnes parent: {column_mapping}")
        
        # 🔥 PAUSE POUR INDEXATION
        logger.info(f"⏳ Pause de 3 secondes pour indexation Atlas...")
        time.sleep(3)
        
        # Vérifier que les colonnes sont visibles
        verification = matcher._get_dataset_columns(parent_guid)
        logger.info(f"🔍 Vérification: {len(verification)} colonnes maintenant visibles dans Atlas")
        
        return parent_entities, column_mapping
        
    except Exception as e:
        logger.error(f"❌ Erreur création colonnes parent: {e}")
        import traceback
        traceback.print_exc()
        return [], {}

def find_smart_parent(df_current, dataset_name: str, dataset_id: str = None, db: Session = None):
    """
    Recherche le parent ET récupère ses colonnes (les crée si nécessaire)
    Retourne (parent_guid, parent_qn, parent_columns, parent_column_mapping)
    """
    print(f"\n{'='*60}")
    print(f"🎯 RECHERCHE PARENT: {dataset_name}")
    print(f"{'='*60}")
    
    try:
        # Récupérer tous les datasets
        res = atlas_get(f"{ATLAS_SEARCH_URL}?typeName=DataSet&query=*")
        entities = res.json().get("entities", [])
        print(f"📥 {len(entities)} datasets trouvés")
        
        # Signature courante
        sig_current = calculate_dataset_signature(df_current, dataset_name)
        
        best_score = 0
        best_parent = None
        best_parent_guid = None
        best_parent_qn = None
        
        # Récupérer les entités complètes
        base_url = ATLAS_SEARCH_URL.split("/search")[0]
        full_entities = []
        
        for e in entities:
            guid = e.get("guid")
            if not guid:
                continue
            try:
                full = atlas_get(f"{base_url}/entity/guid/{guid}").json()
                full_entities.append(full.get("entity", full))
            except:
                continue
        
        # Comparer chaque dataset
        for ds in full_entities:
            if ds.get("status") == "DELETED":
                continue
                
            attrs = ds.get("attributes", {})
            ds_name = attrs.get('name', 'Unknown')
            ds_guid = ds.get("guid")
            ds_qn = attrs.get('qualifiedName', 'Unknown')
            sig_old = attrs.get("signature")
            
            if isinstance(sig_old, str):
                try:
                    sig_old = json.loads(sig_old)
                except:
                    continue
            
            if not sig_old:
                continue
            
            score = compute_similarity_score(sig_current, sig_old)
            print(f"   {ds_name}: score {score:.3f}")
            
            if score > best_score:
                best_score = score
                best_parent = ds
                best_parent_guid = ds_guid
                best_parent_qn = ds_qn
        
        # ✅ Si parent trouvé avec bon score
        if best_parent and best_score >= 0.60:
            parent_name = best_parent.get("attributes", {}).get("name", "Unknown")
            print(f"\n🏆 PARENT TROUVÉ: {parent_name} (score: {best_score:.3f})")
            print(f"   GUID: {best_parent_guid}")
            print(f"   QualifiedName: {best_parent_qn}")
            
            # 🔥 ensure_parent_columns vérifie d'abord si les colonnes existent
            parent_columns, parent_column_mapping = ensure_parent_columns(
                best_parent_guid,
                parent_name,
                best_parent_qn
            )
            
            if parent_columns:
                print(f"✅ {len(parent_columns)} colonnes parent récupérées")
                print(f"✅ {len(parent_column_mapping)} mappings colonnes disponibles")
                print(f"📋 Mappings: {parent_column_mapping}")
            else:
                print(f"⚠️ Échec récupération colonnes parent")
                parent_columns = []
                parent_column_mapping = {}
            
            return best_parent_guid, best_parent_qn, parent_columns, parent_column_mapping
        
        else:
            print(f"\n❌ AUCUN PARENT TROUVÉ")
            return None, None, [], {}
            
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return None, None, [], {}


def persist_signature_to_db(db: Session, dataset_id: str, signature: dict):
    ds_sig = create_dataset_signature(
        db=db,
        dataset_id=dataset_id,
        structure_hash=signature["structure_hash"],
        signature=signature,
        columns_count=signature.get("columns_count"),
        rows_count=signature.get("rows_count"),
        algo_version="v1"
    )
    
    for col_name, meta in signature["columns"].items():
        create_column_signature(
            db=db,
            dataset_signature_id=str(ds_sig.id),
            column_name=col_name,
            data_type=meta["dtype"],
            mean=meta.get("mean"),
            std=meta.get("std"),
            distinct_count=meta.get("ndist"),
            sample_hash=meta.get("sample_hash")
        )
    
    return ds_sig