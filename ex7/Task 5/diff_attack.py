import numpy as np
import pandas as pd

def laplace_mech(v, sensitivity, epsilon):
    scale = sensitivity / epsilon
    return v + np.random.laplace(0, scale)


def dp_differencing_attack(df, epsilon, clip_value):
    """
    Differentially private version of the differencing attack.
    Uses clipping to ensure bounded sensitivity.
    """

    # clip Age so one person cannot dominate the result
    clipped = df["Age"].clip(0, clip_value)

    # Q1: full sum
    q1 = clipped.sum()

    # Q2: sum without the targeted person
    q2 = clipped[df["Name"] != "Karrie Trusslove"].sum()

    true_diff = q1 - q2

    # sensitivity = clip_value, since diff equals (clipped) age of this person
    sensitivity = clip_value

    return laplace_mech(true_diff, sensitivity, epsilon)


if __name__ == "__main__":
    adult = pd.read_csv("adult_with_pii.csv")
    epsilon = 0.1
    clip_value = 90  # example bound for age

    result = dp_differencing_attack(adult, epsilon, clip_value)
    print("DP-safe differencing attack result:", result)
