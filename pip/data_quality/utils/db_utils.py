import json
from airflow.hooks.postgres_hook import PostgresHook

def insert_result(cur, dag_run_id, validator_name, res):
    cur.execute("""
        INSERT INTO validation_results
        (dag_run_id, validator_name, test_type, statut, colonne, nombre, ratio, alerte, exemples)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        dag_run_id,
        validator_name,
        res.get("type de test"),
        res.get("statut"),
        res.get("colonne testée"),
        res.get("nombre"),
        res.get("ratio"),
        res.get("alerte"),
        json.dumps(res.get("exemples", []))
    ))

def save_results_to_postgres(results, dag_run_id, conn_id="postgres_airflow"):
    """Sauvegarde des résultats de validation dans Postgres"""
    hook = PostgresHook(postgres_conn_id=conn_id)
    conn = hook.get_conn()
    cur = conn.cursor()

    for validator_name, validator_results in results.items():
        if isinstance(validator_results, list):
            for res in validator_results:
                insert_result(cur, dag_run_id, validator_name, res)
        elif isinstance(validator_results, dict):
            for _, sub_results in validator_results.items():
                if isinstance(sub_results, list):
                    for res in sub_results:
                        insert_result(cur, dag_run_id, validator_name, res)

    conn.commit()
    cur.close()
    conn.close()
