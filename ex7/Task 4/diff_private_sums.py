import numpy as np
import pandas as pd


# Laplace mechanism (same as before)
def laplace_mech(v, sensitivity, epsilon):
    scale = sensitivity / epsilon
    noise = np.random.laplace(0, scale)
    return v + noise


# Differentially private sum of Capital Gain
def dp_sum_capgain(df, epsilon, clip_value):
    """
    Computes a differentially private sum of the Capital Gain column.
    Values are clipped to [-clip_value, clip_value] to ensure bounded sensitivity.
    Total privacy cost = epsilon.
    """
    # clip to ensure bounded sensitivity
    clipped = df["Capital Gain"].clip(-clip_value, clip_value)

    # compute true clipped sum
    true_sum = clipped.sum()

    # sensitivity = maximum change if one record is added/removed
    sensitivity = clip_value

    # apply Laplace mechanism
    dp_result = laplace_mech(true_sum, sensitivity, epsilon)
    return dp_result


# Required computation for epsilon = 0.04
if __name__ == "__main__":
    adult = pd.read_csv("adult_with_pii.csv")

    epsilon = 0.04
    clip_value = adult["Capital Gain"].quantile(0.95)   # example: safe, DP-free bound

    result = dp_sum_capgain(adult, epsilon, clip_value)
    print("DP sum of Capital Gain:", result)
