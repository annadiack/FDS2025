import numpy as np
import pandas as pd

# Laplace mechanism (same as before)

def laplace_mech(v, sensitivity, epsilon):
    scale = sensitivity / epsilon
    noise = np.random.laplace(0, scale)
    return v + noise


# Scoring function:
# returns the (non-private) number of occurrences of an occupation

def score(df, occupation):
    """
    Score = number of people with that occupation.
    Higher count = more common occupation.
    """
    return (df["Occupation"] == occupation).sum()


# Differentially private "argmax" over occupations
def most_common_occupation(df, epsilon):
    """
    Computes the most common occupation in a DP way.
    Uses Laplace noise on each occupation's count.
    Returns only the occupation with the highest noisy score.
    """
    occupations = df["Occupation"].unique()

    # Sensitivity of the score function = 1 (counting query)
    sensitivity = 1

    noisy_scores = {}
    for occ in occupations:
        true_score = score(df, occ)
        noisy_score = laplace_mech(true_score, sensitivity, epsilon)
        noisy_scores[occ] = noisy_score

    # Choose occupation with highest noisy score
    return max(noisy_scores, key=noisy_scores.get)


# Required computation: ε = 0.05
if __name__ == "__main__":
    adult = pd.read_csv("adult_with_pii.csv")
    epsilon = 0.05
    result = most_common_occupation(adult, epsilon)
    print("DP most common occupation:", result)
