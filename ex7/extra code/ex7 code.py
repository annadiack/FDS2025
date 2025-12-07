import pandas as pd
import numpy as np
from scipy import stats  # allowed import (not strictly needed, but permitted)

# ---------------------------------------------------------------------------
# Load dataset (make sure adult_with_pii.csv is in the same folder)
# ---------------------------------------------------------------------------

adult = pd.read_csv("adult_with_pii.csv")

# ---------------------------------------------------------------------------
# 1. Laplace mechanism and counting queries
# ---------------------------------------------------------------------------

def laplace_mech(v, sensitivity, epsilon, size=None):
    """
    Laplace mechanism.

    Parameters
    ----------
    v : float or np.ndarray
        True value (scalar or array).
    sensitivity : float
        Global L1 sensitivity Δf of the query.
    epsilon : float
        Privacy parameter ε (> 0).
    size : tuple or int, optional
        Shape of the noise if v is not an array and we want a specific shape.

    Returns
    -------
    v_noisy : same type as v
        Noisy output v + Laplace(0, sensitivity/epsilon).
    """
    if epsilon <= 0:
        raise ValueError("epsilon must be > 0")

    scale = sensitivity / epsilon
    noise = np.random.laplace(loc=0.0, scale=scale, size=size)
    return v + noise


# ε for the counting query
EPS_COUNT = np.log(2.0)  # epsilon = ln(2)


def dp_count_over_29(adult_df, epsilon=EPS_COUNT):
    """
    Differentially private count of people in adult_df with Age > 29.

    Parameters
    ----------
    adult_df : pd.DataFrame
        Adult dataset containing an 'Age' column.
    epsilon : float
        Privacy parameter ε. Default: ln(2).

    Returns
    -------
    noisy_count : float
        Noisy count.
    """
    # True count
    true_count = (adult_df["Age"] > 29).sum()

    # Sensitivity of counting query is 1
    sensitivity = 1.0

    noisy_count = laplace_mech(true_count, sensitivity, epsilon)
    return noisy_count


# ---------------------------------------------------------------------------
# 2. Contingency tables
# ---------------------------------------------------------------------------

def dp_contingency_table(df, col_x, col_y, epsilon):
    """
    Generate a differentially private contingency table for any dataset and
    any combination of two columns, using the Laplace mechanism.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataset.
    col_x : str
        Name of the first column.
    col_y : str
        Name of the second column.
    epsilon : float
        Privacy parameter ε for the *entire* table.

    Returns
    -------
    noisy_table : pd.DataFrame
        Noisy contingency table with Laplace noise added to each cell.
    """
    # True contingency table (2D histogram)
    true_table = pd.crosstab(df[col_x], df[col_y])

    # Sensitivity (add/remove adjacency): one person affects exactly one cell
    sensitivity = 1.0

    # Add Laplace noise to each cell at once (vector-valued query)
    noisy_values = laplace_mech(
        true_table.values.astype(float),
        sensitivity,
        epsilon,
        size=true_table.shape
    )

    noisy_table = pd.DataFrame(
        noisy_values,
        index=true_table.index,
        columns=true_table.columns
    )

    # Optional: clip negatives to 0 to avoid negative counts
    noisy_table = noisy_table.clip(lower=0.0)

    return noisy_table


def dp_contingency_relationship_race(adult_df, epsilon=0.3):
    """
    Generate a differentially private contingency table for the 'Relationship'
    and 'Race' columns of the adult dataset, with total privacy cost ε=0.3.

    Parameters
    ----------
    adult_df : pd.DataFrame
        Adult dataset.
    epsilon : float
        Privacy parameter ε. Default: 0.3.

    Returns
    -------
    noisy_table : pd.DataFrame
        Noisy contingency table for (Relationship, Race).
    """
    return dp_contingency_table(adult_df, "Relationship", "Race", epsilon)


# ---------------------------------------------------------------------------
# 3. Differentially private selections from sets
# ---------------------------------------------------------------------------

def score(adult_df, occupation):
    """
    Scoring function for an occupation: number of people with that occupation.

    Parameters
    ----------
    adult_df : pd.DataFrame
        Adult dataset with an 'Occupation' column.
    occupation : str
        Occupation value to score.

    Returns
    -------
    s : int
        Score: count of people with the given occupation.
    """
    return (adult_df["Occupation"] == occupation).sum()


def most_common_occupation(adult_df, epsilon):
    """
    Differentially private computation of the most common occupation,
    using the Laplace mechanism on the occupation counts.

    Parameters
    ----------
    adult_df : pd.DataFrame
        Adult dataset with an 'Occupation' column.
    epsilon : float
        Privacy parameter ε for the entire selection.

    Returns
    -------
    best_occupation : str
        Occupation selected in a DP way as the most common.
    best_true_score : float
        True count for the selected occupation.
    best_noisy_score : float
        Noisy score used for the selection (post-processed).
    """
    # All unique occupations
    occupations = adult_df["Occupation"].dropna().unique()

    # True scores (counts) for each occupation
    true_scores = np.array(
        [score(adult_df, occ) for occ in occupations],
        dtype=float
    )

    # Sensitivity of each count query is 1
    sensitivity = 1.0

    # Add Laplace noise to all scores at once
    noisy_scores = laplace_mech(
        true_scores,
        sensitivity,
        epsilon,
        size=true_scores.shape
    )

    # Choose the occupation with maximum noisy score (post-processing)
    best_index = np.argmax(noisy_scores)
    best_occupation = occupations[best_index]
    best_true_score = true_scores[best_index]
    best_noisy_score = noisy_scores[best_index]

    return best_occupation, best_true_score, best_noisy_score


# ---------------------------------------------------------------------------
# 4. Differentially private sums (Capital Gain)
# ---------------------------------------------------------------------------

# Clipping threshold for Capital Gain (trade-off between sensitivity and utility)
CLIP_CAPGAIN = 50000.0


def dp_sum_capgain(adult_df, epsilon, clip_value=CLIP_CAPGAIN):
    """
    Differentially private sum of the 'Capital Gain' column.

    Parameters
    ----------
    adult_df : pd.DataFrame
        Adult dataset with 'Capital Gain' column.
    epsilon : float
        Privacy parameter ε (total privacy cost of this function).
    clip_value : float
        Clipping threshold C: each individual's capital gain is clipped to [0, C].

    Returns
    -------
    noisy_sum : float
        Noisy sum of clipped capital gains.
    """
    # Extract capital gains and clip them
    cap_gain = adult_df["Capital Gain"].fillna(0).to_numpy(dtype=float)
    cap_gain_clipped = np.clip(cap_gain, 0.0, clip_value)

    # True sum (after clipping)
    true_sum = cap_gain_clipped.sum()

    # Sensitivity: one individual contributes at most clip_value to the sum
    sensitivity = clip_value

    noisy_sum = laplace_mech(true_sum, sensitivity, epsilon)
    return noisy_sum


# ---------------------------------------------------------------------------
# 5. Sensitivity and DP differencing attack
# ---------------------------------------------------------------------------

def differencing_attack(adult_df):
    """
    Non-private differencing attack on a specific individual 'Karrie Trusslove'.

    Returns
    -------
    result : float
        q1 - q2 where q1 is sum of all ages,
        and q2 is sum of ages excluding 'Karrie Trusslove'.
    """
    q1 = adult_df["Age"].sum()
    q2 = adult_df[adult_df["Name"] != "Karrie Trusslove"]["Age"].sum()
    return q1 - q2


def dp_differencing_attack(adult_df, epsilon, age_max=100.0):
    """
    Differentially private version of the differencing attack.

    Parameters
    ----------
    adult_df : pd.DataFrame
        Adult dataset with 'Age' and 'Name' columns.
    epsilon : float
        Privacy parameter ε.
    age_max : float
        Assumed maximum possible age (bound for sensitivity).

    Returns
    -------
    noisy_result : float
        Noisy result of the differencing attack query.
    """
    # True differencing attack result
    true_result = differencing_attack(adult_df)

    # Sensitivity: changing presence of Karrie changes result by at most age_max
    sensitivity = age_max

    noisy_result = laplace_mech(true_result, sensitivity, epsilon)
    return noisy_result


# ---------------------------------------------------------------------------
# Main block: example calls required by the exercise
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 1. Laplace mechanism and counting queries
    print("=== 1. DP count Age > 29 (ε = ln 2) ===")
    dp_count = dp_count_over_29(adult, epsilon=EPS_COUNT)
    print("DP count (Age > 29):", dp_count)

    # 2. Contingency tables for Relationship and Race with ε = 0.3
    print("\n=== 2. DP contingency table (Relationship, Race), ε = 0.3 ===")
    dp_table_rr = dp_contingency_relationship_race(adult, epsilon=0.3)
    print(dp_table_rr)

    # 3. DP most common occupation with ε = 0.05
    print("\n=== 3. DP most common occupation, ε = 0.05 ===")
    best_occ, best_true, best_noisy = most_common_occupation(adult, epsilon=0.05)
    print("DP most common occupation:", best_occ)
    print("True count for that occupation:", best_true)
    print("Noisy score used for selection:", best_noisy)

    # 4. DP sum of Capital Gain with ε = 0.04
    print("\n=== 4. DP sum of Capital Gain, ε = 0.04 ===")
    noisy_capgain_sum = dp_sum_capgain(adult, epsilon=0.04, clip_value=CLIP_CAPGAIN)
    print("DP sum of Capital Gain:", noisy_capgain_sum)

    # 5. Non-private vs DP differencing attack
    print("\n=== 5. Differencing attack (non-private and DP) ===")
    non_private = differencing_attack(adult)
    print("Non-private differencing attack result:", non_private)

    dp_attack = dp_differencing_attack(adult, epsilon=0.5, age_max=100.0)
    print("DP differencing attack result (ε = 0.5, age_max = 100):", dp_attack)
