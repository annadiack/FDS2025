import numpy as np
import pandas as pd


# Laplace mechanism for a single numeric value

def laplace_mech(v, sensitivity, epsilon):
    scale = sensitivity / epsilon
    noise = np.random.laplace(0, scale)
    return v + noise


# Differentially private contingency table for two columns

def dp_contingency_table(df, col_a, col_b, epsilon):
    """
    Compute a differentially private contingency table for columns col_a and col_b.
    Each cell receives Laplace noise independently.
    """
    # true counts first
    true_table = pd.crosstab(df[col_a], df[col_b])

    # sensitivity of each cell count = 1
    sensitivity = 1

    # add Laplace noise to each entry
    noisy_table = true_table.copy().astype(float)
    for i in noisy_table.index:
        for j in noisy_table.columns:
            noisy_table.loc[i, j] = laplace_mech(
                true_table.loc[i, j], sensitivity, epsilon
            )

    return noisy_table

# Example required by the exercise (ε = 0.3)

if __name__ == "__main__":
    adult = pd.read_csv("adult_with_pii.csv")

    # Generate DP contingency table for Relationship × Race
    epsilon = 0.3
    table = dp_contingency_table(adult, "Relationship", "Race", epsilon)

    print("DP contingency table (Relationship × Race):")
    print(table)
