#!/bin/bash

# Source conda.sh to enable conda commands in script
source "$(conda info --base)/etc/profile.d/conda.sh"

# Activate the conda environment
conda activate spdr_env

# Run the Python script
python curious_surfer.py