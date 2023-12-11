#!/bin/bash

# JOB=NEW_PSF
# JOB=NEW_S1_LT
JOB=NEW_S2_LT

mkdir $JOB
cd $JOB
cp ../${JOB}_job.sh .

sbatch --array=1-5000 ${JOB}_job.sh