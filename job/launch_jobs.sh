#!/bin/bash

# JOB=NEW_PSF
JOB=NEW_S1_LT

mkdir $JOB
cd $JOB
cp ../${JOB}_job.sh .

sbatch --array=1-500 ${JOB}_job.sh