from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


OUT_DIR = Path("/home/ashahi/PFE/data")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def generate_numeric_dataset(n: int, rng: np.random.Generator) -> pd.DataFrame:
    latent_usage = rng.normal(0, 1.0, n)
    latent_risk = rng.normal(0, 1.0, n)
    latent_cycle = np.sin(np.linspace(0, 10 * np.pi, n)) + rng.normal(0, 0.15, n)

    amount = np.exp(4.2 + 0.65 * latent_usage + 0.25 * latent_risk + rng.normal(0, 0.35, n))
    v1 = 1.8 * latent_usage + 0.25 * latent_risk + rng.normal(0, 0.18, n)
    v2 = -1.1 * latent_usage + 0.5 * latent_cycle + rng.normal(0, 0.2, n)
    v3 = 4.5 + 1.3 * latent_risk + 0.3 * latent_usage + rng.normal(0, 0.35, n)
    v4 = rng.uniform(-10, 10, n) + 0.2 * latent_cycle
    v5 = 0.4 * latent_usage + rng.normal(0, 0.12, n)
    v6 = 2.8 + 2.2 * latent_cycle + rng.normal(0, 0.55, n)
    v7 = rng.normal(0, 1, n) + 0.4 * latent_risk
    time = np.arange(n, dtype=float)

    anomaly_score = 0.9 * latent_risk + 0.3 * np.log1p(amount) - 5.8
    anomaly_prob = _sigmoid(anomaly_score)
    class_label = rng.binomial(1, np.clip(anomaly_prob, 0.001, 0.04))

    df = pd.DataFrame(
        {
            "amount": amount,
            "v1": v1,
            "v2": v2,
            "v3": v3,
            "v4": v4,
            "v5": v5,
            "v6": v6,
            "v7": v7,
            "time": time,
            "class": class_label,
        }
    )

    return df


def generate_mixed_dataset(n: int, rng: np.random.Generator) -> pd.DataFrame:
    employment_type = rng.choice(["CDI", "CDD", "Freelance", "Chomage"], size=n, p=[0.46, 0.22, 0.19, 0.13])
    marital_status = rng.choice(["Celibataire", "Marie", "Divorce"], size=n, p=[0.38, 0.48, 0.14])
    education = rng.choice(["Bac", "Licence", "Master", "Doctorat"], size=n, p=[0.22, 0.41, 0.29, 0.08])
    region = rng.choice(["Nord", "Sud", "Est", "Ouest"], size=n, p=[0.27, 0.24, 0.21, 0.28])
    has_mortgage = rng.choice(["Oui", "Non"], size=n, p=[0.61, 0.39])
    loan_purpose = rng.choice(["Maison", "Auto", "Travaux", "Conso", "Etudes"], size=n, p=[0.28, 0.21, 0.19, 0.22, 0.10])
    residency = rng.choice(["Proprietaire", "Locataire", "Famille"], size=n, p=[0.42, 0.46, 0.12])

    base_income = np.select(
        [
            employment_type == "CDI",
            employment_type == "CDD",
            employment_type == "Freelance",
            employment_type == "Chomage",
        ],
        [52000, 36000, 61000, 15000],
        default=30000,
    ).astype(float)

    age = rng.integers(18, 72, size=n)
    income = np.clip(base_income + 850 * (age - 35) + rng.normal(0, 11500, n), 9000, None)
    credit_signal = (
        0.9 * (employment_type == "CDI").astype(float)
        + 0.45 * (education == "Master").astype(float)
        + 0.7 * (has_mortgage == "Non").astype(float)
        - 0.35 * (loan_purpose == "Conso").astype(float)
        - 0.25 * (residency == "Famille").astype(float)
        + rng.normal(0, 0.4, n)
    )
    credit_score = np.clip(520 + 85 * credit_signal + rng.normal(0, 35, n), 300, 850)
    loan_amount = np.clip(0.18 * income + rng.normal(0, 16000, n) + 5000 * (loan_purpose == "Maison").astype(float), 1000, 90000)
    num_dependents = np.clip(rng.poisson(1.2 + 0.3 * (marital_status == "Marie").astype(float), size=n), 0, 6)
    employment_length = np.clip(
        (age - 18) * rng.uniform(0.35, 0.85, n) + rng.normal(0, 2.0, n),
        0,
        45,
    )
    savings = np.clip(income * rng.uniform(0.03, 0.32, n) + rng.normal(0, 3500, n), 0, None)
    debt_ratio = np.clip(loan_amount / np.maximum(income, 1) + rng.normal(0, 0.06, n), 0.01, 1.8)

    risk_score = (
        0.018 * (loan_amount / 1000)
        - 0.010 * (credit_score - 600)
        + 0.22 * (employment_type == "Chomage").astype(float)
        + 0.09 * (residency == "Famille").astype(float)
        + 0.06 * num_dependents
        + 0.18 * debt_ratio
        - 0.11 * (employment_type == "CDI").astype(float)
        - 0.09 * (loan_purpose == "Maison").astype(float)
    )
    approval_prob = _sigmoid(2.0 - risk_score)
    loan_status = np.where(rng.random(n) < approval_prob, "Approuve", "Refuse")

    df = pd.DataFrame(
        {
            "age": age,
            "income": income,
            "loan_amount": loan_amount,
            "credit_score": credit_score,
            "employment_length": employment_length,
            "num_dependents": num_dependents,
            "debt_ratio": debt_ratio,
            "savings": savings,
            "employment_type": employment_type,
            "marital_status": marital_status,
            "education": education,
            "region": region,
            "has_mortgage": has_mortgage,
            "loan_purpose": loan_purpose,
            "residency": residency,
            "loan_status": loan_status,
        }
    )

    missing_income = rng.choice(n, size=900, replace=False)
    missing_credit = rng.choice(n, size=500, replace=False)
    missing_region = rng.choice(n, size=250, replace=False)
    df.loc[missing_income, "income"] = np.nan
    df.loc[missing_credit, "credit_score"] = np.nan
    df.loc[missing_region, "region"] = np.nan

    return df


def generate_churn_dataset(n: int, rng: np.random.Generator) -> pd.DataFrame:
    customer_id = [f"C{i:06d}" for i in range(n)]
    tenure_months = rng.integers(1, 73, size=n)
    contract_type = rng.choice(["Mensuel", "Annuel", "Biennal"], size=n, p=[0.54, 0.30, 0.16])
    payment_method = rng.choice(["Carte", "Virement", "Cheque", "Prelevement"], size=n, p=[0.32, 0.27, 0.14, 0.27])
    internet_service = rng.choice(["Fibre", "DSL", "Non"], size=n, p=[0.53, 0.33, 0.14])
    phone_service = rng.choice(["Oui", "Non"], size=n, p=[0.88, 0.12])
    paperless_billing = rng.choice(["Oui", "Non"], size=n, p=[0.72, 0.28])
    streaming_tv = rng.choice(["Oui", "Non"], size=n, p=[0.57, 0.43])
    support_tickets = rng.poisson(0.9 + 0.6 * (internet_service == "DSL").astype(float) + 0.4 * (contract_type == "Mensuel").astype(float), size=n)
    monthly_charges = np.clip(
        rng.normal(35, 8, n)
        + 32 * (internet_service == "Fibre").astype(float)
        + 18 * (streaming_tv == "Oui").astype(float)
        + 11 * (phone_service == "Oui").astype(float),
        20,
        140,
    )
    total_charges = np.clip(monthly_charges * tenure_months + rng.normal(0, 280, n), 100, None)
    senior_citizen = rng.choice(["Oui", "Non"], size=n, p=[0.19, 0.81])

    churn_risk = (
        0.055 * monthly_charges
        - 0.03 * tenure_months
        + 0.75 * (contract_type == "Mensuel").astype(float)
        + 0.35 * (payment_method == "Cheque").astype(float)
        + 0.28 * (internet_service == "DSL").astype(float)
        + 0.25 * (paperless_billing == "Oui").astype(float)
        + 0.14 * support_tickets
        + 0.33 * (senior_citizen == "Oui").astype(float)
        - 0.42 * (contract_type == "Biennal").astype(float)
        + rng.normal(0, 0.7, n)
    )
    churn_prob = _sigmoid(churn_risk - 3.5)
    churn = np.where(rng.random(n) < churn_prob, "Oui", "Non")

    df = pd.DataFrame(
        {
            "customer_id": customer_id,
            "tenure_months": tenure_months,
            "monthly_charges": monthly_charges,
            "total_charges": total_charges,
            "contract_type": contract_type,
            "payment_method": payment_method,
            "internet_service": internet_service,
            "phone_service": phone_service,
            "paperless_billing": paperless_billing,
            "streaming_tv": streaming_tv,
            "support_tickets": support_tickets,
            "senior_citizen": senior_citizen,
            "churn": churn,
        }
    )

    missing_payment = rng.choice(n, size=650, replace=False)
    missing_service = rng.choice(n, size=450, replace=False)
    df.loc[missing_payment, "payment_method"] = np.nan
    df.loc[missing_service, "internet_service"] = np.nan

    return df


def main() -> None:
    rng = np.random.default_rng(42)
    n = 50_000

    df_numeric = generate_numeric_dataset(n, rng)
    df_numeric.to_csv(OUT_DIR / "synthetic_numeric.csv", index=False)
    print("Dataset 1 OK -", df_numeric.shape)

    df_mixed = generate_mixed_dataset(n, rng)
    df_mixed.to_csv(OUT_DIR / "synthetic_mixed.csv", index=False)
    print("Dataset 2 OK -", df_mixed.shape)

    df_churn = generate_churn_dataset(n, rng)
    df_churn.to_csv(OUT_DIR / "synthetic_churn.csv", index=False)
    print("Dataset 3 OK -", df_churn.shape)


if __name__ == "__main__":
    main()

