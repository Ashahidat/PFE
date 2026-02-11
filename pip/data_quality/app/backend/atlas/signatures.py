import hashlib
import logging
import json
from pyspark.sql import functions as F
from rapidfuzz import fuzz
from atlas.client import atlas_get
from atlas.client import atlas_post, atlas_put, ATLAS_TYPEDEF_URL, ATLAS_RELATIONSHIP_URL, ATLAS_SEARCH_URL

from db.crud_dataset_signatures import create_dataset_signature
from db.crud_column_signatures import create_column_signature
from sqlalchemy.orm import Session


logger = logging.getLogger("atlas.signatures")
logger.setLevel(logging.DEBUG)

# ----------------------------------------------
# 1) SIGNATURE BIG DATA 
# ----------------------------------------------
def calculate_dataset_signature(df, dataset_name: str, sample_size=200):
    # print(f"🔧 DEBUT: calculate_dataset_signature pour '{dataset_name}'")
    # print(f"   - Nombre de colonnes: {len(df.columns)}")
    # print(f"   - Colonnes: {df.columns}")
    
    # Sample Spark (max sample_size lignes)
    sample_df = df.orderBy(F.rand()).limit(sample_size)
    # print(f"   - Échantillonnage: {sample_size} lignes aléatoires")

    # Collecte des samples pour hash
    sample_data = {
        col: [str(row[col]) for row in sample_df.select(col).limit(20).collect() if row[col] is not None]
        for col in df.columns
    }
    # print(f"   - Échantillons collectés pour {len(sample_data)} colonnes")

    # Stats Spark groupées
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

    # print(f"   - Calcul des statistiques avec {len(agg_exprs)} expressions d'agrégation")
    stats_row = df.agg(*agg_exprs).collect()[0]
    # print("   - Statistiques calculées avec succès")

    # Construire signature
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

    # Hash structure globale
    struct = [(col, signature["columns"][col]["dtype"]) for col in df.columns]
    signature["structure_hash"] = hashlib.sha256(str(sorted(struct)).encode()).hexdigest()
    signature["rows_count"] = df.count()

    # print(f"✅ FIN: calculate_dataset_signature - Structure hash: {signature['structure_hash'][:16]}...")
    # print(f"   - Base name: {signature['name_base']}")
    # print(f"   - Nombre de colonnes dans signature: {len(signature['columns'])}")
    
    return signature

# ---------------------------------------------------
# 2) MATCH FLEXIBLE ENTRE COLONNES
# ---------------------------------------------------
def match_columns(sig_current, sig_old):
    # print(f"🔧 DEBUT: match_columns")
    # print(f"   - Colonnes actuelles: {list(sig_current['columns'].keys())}")
    # print(f"   - Colonnes anciennes: {list(sig_old['columns'].keys())}")
    
    matches = {}
    used = set()
    
    for col_c, sc in sig_current["columns"].items():
        print(f"   --- Recherche match pour '{col_c}' (type: {sc['dtype']}) ---")
        best_col = None
        best_score = 0
        
        for col_o, so in sig_old["columns"].items():
            if col_o in used:
                continue
                
            score = 0
            print(f"     Comparaison avec '{col_o}' (type: {so['dtype']})")
            
            # Score type de données
            type_match = sc["dtype"] == so["dtype"]
            if type_match:
                score += 0.4
                print(f"       ✅ Types compatibles: +0.4")
            else:
                print(f"       ❌ Types différents: {sc['dtype']} vs {so['dtype']}")

            # Score statistiques pour colonnes numériques
            if sc["dtype"] == "numeric" and so["dtype"] == "numeric":
                def sim(x, y):
                    if x is None or y is None:
                        return 0
                    return 1 - min(abs(x - y) / (abs(y) + 1e-9), 1)
                
                mean_sim = sim(sc["mean"], so["mean"])
                std_sim = sim(sc["std"], so["std"])
                score += 0.1 * mean_sim
                score += 0.1 * std_sim
                # print(f"       📊 Similarité moyenne: {mean_sim:.3f} (+{0.1 * mean_sim:.3f})")
                # print(f"       📊 Similarité écart-type: {std_sim:.3f} (+{0.1 * std_sim:.3f})")

            # Score échantillons
            sample_match = sc["sample_hash"] == so["sample_hash"]
            if sample_match:
                score += 0.4
                print(f"       ✅ Hash échantillons identiques: +0.4")
            else:
                print(f"       ❌ Hash échantillons différents")

            print(f"       🎯 Score total pour cette paire: {score:.3f}")
            
            if score > best_score:
                best_score = score
                best_col = col_o
                print(f"       🏆 Nouveau meilleur match: '{col_o}' avec score {score:.3f}")

        if best_col and best_score > 0.35:
            matches[col_c] = best_col
            used.add(best_col)
            print(f"   ✅ MATCH TROUVÉ: '{col_c}' -> '{best_col}' (score: {best_score:.3f})")
        else:
            print(f"   ❌ AUCUN MATCH pour '{col_c}' (meilleur score: {best_score:.3f})")

    # print(f"✅ FIN: match_columns - {len(matches)} matches trouvés: {matches}")
    # return matches

# ---------------------------------------------------
# 3) SCORE GLOBAL
# ---------------------------------------------------
def compute_similarity_score(sig_current, sig_old, verbose=True):
    # print(f"\n🔧 DEBUT: compute_similarity_score")
    # print(f"   - Dataset courant: {sig_current['name_base']}")
    # print(f"   - Dataset ancien: {sig_old['name_base']}")
    
    # Calcul Jaccard
    cols_new = set(sig_current["columns"].keys())
    cols_old = set(sig_old["columns"].keys())
    jaccard = len(cols_new & cols_old) / len(cols_new | cols_old) if (cols_new | cols_old) else 0
    print(f"   📊 Jaccard: {jaccard:.3f} (intersection: {len(cols_new & cols_old)}, union: {len(cols_new | cols_old)})")

    # Score types de données
    common = cols_new & cols_old
    type_matches = sum(1 for c in common if sig_current["columns"][c]["dtype"] == sig_old["columns"][c]["dtype"])
    type_score = type_matches / max(len(common), 1)
    # print(f"   📊 Type score: {type_score:.3f} ({type_matches}/{len(common)} types correspondants)")

    # Score structure
    structure_score = 0.60 * (0.7 * jaccard + 0.3 * type_score)
    # print(f"   📊 Structure score: {structure_score:.3f} (0.60 * (0.7*{jaccard:.3f} + 0.3*{type_score:.3f}))")

    # Score nom
    name_similarity = fuzz.partial_ratio(sig_current["name_base"], sig_old["name_base"]) / 100.0
    name_score = 0.30 * name_similarity
    # print(f"   📊 Name similarity: {name_similarity:.3f} -> Name score: {name_score:.3f}")

    # Score données (échantillons)
    sample_matches = sum(1 for c in common if sig_current["columns"][c]["sample_hash"] == sig_old["columns"][c]["sample_hash"])
    data_ratio = sample_matches / max(len(common), 1)
    data_score = data_ratio * 0.10
    # print(f"   📊 Data score: {data_score:.3f} ({sample_matches}/{len(common)} hash d'échantillons identiques)")

    # Score final
    final = structure_score + name_score + data_score
    # print(f"   🎯 SCORE FINAL: {final:.3f} = {structure_score:.3f} + {name_score:.3f} + {data_score:.3f}")
    
    return final

def find_smart_parent(df_current, dataset_name: str):
    """
    Recherche intelligente du parent d'un dataset via signature Big Data.
    """
    # print(f"\n🎯 DEBUT: find_smart_parent pour '{dataset_name}'")
    # print("=" * 60)
    
    try:
        # --- 1) Récupérer tous les datasets existants (résumé uniquement)
        # print("📥 Étape 1: Récupération des datasets existants...")
        res = atlas_get(f"{ATLAS_SEARCH_URL}?typeName=DataSet&query=*")
        entities = res.json().get("entities", [])
        # print(f"   ✅ {len(entities)} datasets existants récupérés")

        # --- 2) Calculer la signature du dataset courant
        # print(f"\n📊 Étape 2: Calcul de la signature du dataset courant...")
        sig_current = calculate_dataset_signature(df_current, dataset_name)

        best_score = 0
        best_parent = None
        all_scores = []

        # --- 3) Récupérer la version COMPLÈTE de chaque entité
        # print(f"\n📥 Étape 3: Récupération des signatures complètes...")
        full_entities = []
        for i, e in enumerate(entities):
            guid = e.get("guid")
            if not guid:
                continue

            base_url = ATLAS_SEARCH_URL.split("/search")[0]
            full = atlas_get(f"{base_url}/entity/guid/{guid}").json()

            if "entity" in full:
                full_entities.append(full["entity"])
            else:
                full_entities.append(full)
                
        # print(f"   ✅ {len(full_entities)} entités complètes récupérées")

        # --- 4) Comparer chaque dataset existant
        # print(f"\n🔍 Étape 4: Comparaison avec les datasets existants...")
        # print("-" * 50)
        
        for i, ds in enumerate(full_entities):
            # Exclure si supprimé
            if ds.get("status") == "DELETED":
                continue

            attrs = ds.get("attributes", {})
            ds_name = attrs.get('name', 'Unknown')
            sig_old = attrs.get("signature")

            # Parser signature string -> dict
            if isinstance(sig_old, str):
                try:
                    sig_old = json.loads(sig_old)
                except Exception:
                    print(f"   ❌ Impossible de parser signature pour {ds_name}")
                    continue

            if not sig_old:
                print(f"   ⚠️  Pas de signature pour {ds_name}")
                continue

            # print(f"\n   Comparaison {i+1}/{len(full_entities)}: '{dataset_name}' vs '{ds_name}'")
            # print(f"   {'-' * 40}")

            # Calcul du score
            score = compute_similarity_score(sig_current, sig_old)
            all_scores.append((ds_name, score))

            # Vérifier structure hash
            structure_match = sig_current['structure_hash'] == sig_old.get('structure_hash')
            # print(f"   🔗 Structure hash identique: {structure_match}")

            # print(f"   🎯 SCORE FINAL pour '{ds_name}': {score:.3f}")

            # meilleur score
            if score > best_score:
                best_parent = ds
                best_score = score
                print(f"   🏆 NOUVEAU MEILLEUR SCORE!")
            print(f"   {'-' * 40}")

        # --- 5) Résultats finaux
        # print(f"\n📊 Étape 5: Analyse des résultats...")
        # print(f"   Nombre de datasets comparés: {len(all_scores)}")
        # print(f"   Scores obtenus:")
        for ds_name, score in sorted(all_scores, key=lambda x: x[1], reverse=True)[:5]:
            print(f"     - {ds_name}: {score:.3f}")

        # print(f"\n🎯 RÉSULTAT FINAL:")
        # print(f"   🏆 Meilleur score global: {best_score:.3f}")
        
        if best_parent:
            parent_name = best_parent.get("attributes", {}).get("qualifiedName", "Unknown")
            print(f"   ✅ Parent trouvé: {parent_name}")
        else:
            print(f"   ❌ Aucun parent trouvé")

        if best_parent and best_score >= 0.60:
            print(f"   📌 SEUIL ATTEINT (>0.70) - Retour du parent")
            return best_parent["guid"], best_parent["attributes"]["qualifiedName"]
        else:
            print(f"   📌 SEUIL NON ATTEINT (≤0.70) - Aucun parent retourné")
            return None, None

    except Exception as e:
        print(f"❌ ERREUR dans find_smart_parent: {e}")
        logger.error(f"Erreur find_smart_parent (BIG DATA): {e}")
        return None, None


# 4) PERSISTE LA SIGNATURE DANS LA BASE DE DONNÉES
def persist_signature_to_db(db: Session, dataset_id: str, signature: dict):

    # ✅ créer la signature dataset VIA LA FONCTION SERVICE
    ds_sig = create_dataset_signature(
        db=db,
        dataset_id=dataset_id,
        structure_hash=signature["structure_hash"],
        signature=signature,
        columns_count=signature.get("columns_count"),
        rows_count=signature.get("rows_count"),
        algo_version="v1"
    )

    # ✅ créer les signatures colonnes
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

