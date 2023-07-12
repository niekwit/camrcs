#!/usr/bin/env bash

WORK_DIR=$(pwd)

DIR=$1 #dir name
ARCHIVE=$2 #archive name
DOWNLOAD_DIR=$3

#get data from RCS
rsync -v -h --progress nw416@login.hpc.cam.ac.uk:$DIR/$ARCHIVE.part-* $DOWNLOAD_DIR ###from HPC for testing

#put things back together
cat $(ls $DOWNLOAD_DIR/$ARCHIVE.part-*) > $DOWNLOAD_DIR/$ARCHIVE

#check if sha256 matches
echo "Calculating sha256sum of downloaded data..."
sleep 2
echo $(date) $(sha256sum $DOWNLOAD_DIR/$ARCHIVE) >> "$WORK_DIR/sha256.txt"
echo "Comparing sha256sum with uploaded data..."
sleep 2
grep $ARCHIVE "$WORK_DIR/sha256.txt" | awk '{print $7}' | xargs | awk '{if ($1==$2) {print "SHA256sum correct!"} else {print "SHA256sum incorrect... Download data again!"} }'


