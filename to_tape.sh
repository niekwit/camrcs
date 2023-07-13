#!/usr/bin/env bash

WORK_DIR=$(pwd)
ACCOUNT=$1

#function to upload directory to RCS 
data_to_tape() {
	
	#get variables
	ARCHIVE=$1 #tar.gz file name
	DIR=$2 #parent directory of target directory
	TARGET=$3 #target directory
	EXCLUDE=$5 #parse nothing if nothing should be exluded
	CHUNKS=$4 #SIZE bytes per output file
	
	#check if split archive files have already been made (in case of file transfer failure)
	#archive creating can take a very long time with very large directories
	if [ -f $ARCHIVE.split.done ]
	then
		echo "$ARCHIVE has been created/split before..."
	else
		#create archive
		echo "Creating archive for $DIR/$TARGET..."
		tar -vczW $EXCLUDE "$DIR/$TARGET" | pigz > $ARCHIVE
		
		#calculate sha256sum
		echo "Calculating sha256sum of archive..."
		echo $(date) uploaded $(sha256sum $ARCHIVE) >> "$WORK_DIR/sha256.txt"
		
		#split files
		echo "Splitting archive in chuncks of $CHUNKS..."
		split -b $CHUNKS $ARCHIVE "$ARCHIVE.part-"
		
		if [ $? == 0 ]
		then
			rm $ARCHIVE
		else
			echo "File splitting has failed..."
			exit 1
		fi
	fi
	
	#rsync to RCS
	echo "Transferring split archive to RCS..."
	rsync -v -h --progress $(ls $ARCHIVE.part-*) $ACCOUNT@rcs.uis.cam.ac.uk:rcs-jan33-cold_data/$TARGET
	
	#remove (un)split archives (only when transfer was completed successfully)
	if [ $? == 0 ]
	then
		echo "Transfer completed..."
		echo "Removing (un)split archive files"
		rm -r $ARCHIVE.part-*
	elif [ $? == 255 ]
	then
		echo "Transfer has failed, most likely due to timeout (i.e. password prompt was left for some time)"
		echo "Keeping split archive files"
		echo "Please run this script again..."
		exit 1
	else
		echo "Transfer has failed, keeping split archive files"
		echo "Please run this script again..."
		touch $ARCHIVE.split.done
		exit 1
	fi
}

#LMB data Niek
#data_to_tape /mnt/4TB_SSD/LMB_data.tar.gz "/media/niek/Niek\ backup" LMB_data 30G --exclude=LMB_data/Results/Microscopy

#LC-MS data JW
#data_to_tape /mnt/4TB_SSD/LC-MS_data_JW.tar.gz /mnt/20TB_raid1 LC-MS_data_JW 12G 

#CITIID HDAC3 data Niek
data_to_tape /mnt/4TB_SSD/HDAC3_data_CITIID_NIEK.tar.gz /mnt/20TB_raid1/udrive/Data CITIID_HDAC3_data 2G






