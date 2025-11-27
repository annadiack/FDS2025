#!/bin/bash
#
# Task 1: simple Slurm job that prints the hostname
#

#SBATCH --job-name=task1_hostname      # Name of the job
#SBATCH --partition=xeon              # Use the xeon partition
#SBATCH --nodes=1                     # One node
#SBATCH --ntasks-per-node=1           # One task (process)
#SBATCH --cpus-per-task=1             # One CPU for that task
#SBATCH --time=00:02:00               # Max runtime (hh:mm:ss)
#SBATCH --hint=nomultithread          # Disable hyperthreading
#SBATCH --exclusive                   # Exclusive use of the node (not strictly required here)

# The actual command that runs on the compute node:
srun hostname
