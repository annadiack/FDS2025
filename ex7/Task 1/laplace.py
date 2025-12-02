import numpy as np
import pandas as pd


# Laplace mechanism

def laplace_mech(v, sensitivity, epsilon):
    """
    Apply the Laplace mechanism to a numeric value v.
    """
    scale = sensitivity / epsilon
    noise = np.random.laplace(0, scale)
    return v + noise

# DP counting query: Age > 29

def dp_count_over_29(adult_df, epsilon=np.log(2)):
    """
    Differentially private count of individuals older than 29.

    adult_df : pandas DataFrame containing the column 'Age'
    epsilon  : privacy budget (default: ln(2))
    """
    # true count
    true_count = (adult_df["Age"] > 29).sum()

    # L1 sensitivity of a counting query is always 1
    sensitivity = 1

    return laplace_mech(true_count, sensitivity, epsilon)


if __name__ == "__main__":
    df = pd.read_csv("adult_with_pii.csv")
    result = dp_count_over_29(df)
    print("Differentially private count of people > 29:", result)
