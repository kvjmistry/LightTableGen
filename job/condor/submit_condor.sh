#!/bin/bash

JOB=NEXT100_S2_LT_FakeGrid

# Create the folder to put all the output files
mkdir -p /protected/krishan.mistry/job/${JOB}

# Edit the submit file
sed -i "s#.*jobname=.*#jobname=${JOB}#" lt.sub

condor_submit lt.sub



