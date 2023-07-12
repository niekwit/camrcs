#!/usr/bin/env bash

WORK_DIR=$(pwd)

#function to upload dirctory to RCS 
data_to_tape() {
	#get variables
	ARCHIVE=$1 #tar.gz file name
	DIR=$2 #parent directory of target directory
	TARGET=$3 #target directory
	EXCLUDE=$5 #parse nothing if nothing should be exluded
	CHUNKS=$4 #SIZE bytes per output file
	
	#create archive
	tar -czf $ARCHIVE -C $DIR $EXCLUDE $TARGET
	
	#calculate sha256sum
	echo $(date) $(sha256sum $ARCHIVE)  >> "$WORK_DIR/sha256.txt"
	
	#split files
	split -b $CHUNKS $ARCHIVE "$ARCHIVE.part-"
	
	#rsync to RCS
	#rsync -v -h --progress $(ls $ARCHIVE.part-*) nw416@rcs.uis.cam.ac.uk:rcs-jan33-archive-jan33/$TARGET
	rsync -v -h --progress $(ls $ARCHIVE.part-*) nw416@login.hpc.cam.ac.uk:~/$TARGET ###to HPC for testing
	
	#remove (un)split archives
	rm -r $ARCHIVE $ARCHIVE.part-*
	
}

#test
data_to_tape ~/Desktop/test.tar.gz ~/Dropbox/scripts/ pycrispr/ 100K 

#LMB data Niek
data_to_tape /mnt/4TB_SSD/LMB_data.tar.gz "/media/niek/Niek backup" LMB_data 30G --exclude=LMB_data/Results/Microscopy



