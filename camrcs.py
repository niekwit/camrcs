import click
import os
import sys
import os.path
from os import path
import pandas as pd
import numpy as np
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime
import time
import timeit
import glob

VERSION = "0.7.1"

#get current working dir
cdir = os.getcwd()
 

####Python functions####

def md5(file):
    '''Calculates MD5sum of input file
    '''
    
    hash_md5 = hashlib.md5()
    
    with open(file, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    
    return(hash_md5.hexdigest())


def run(command):
    '''Runs shell commands with exception handling
    '''
    
    try:
        
        command = subprocess.run(command,
                                 shell=True,
                                 executable='/bin/bash', #process substitution does not work in all shells
                                 check=True)
        
        click.echo("Done...")
        
        return True
                            
    except subprocess.CalledProcessError as error:
        
        click.secho(error, fg="red")
        
        sys.exit()


def update_csv(csv):
    '''Updates data.csv
    '''
    
    #overwrite csv with md5 hash/date
    click.echo("Updating data.csv...")
    csv.to_csv("data.csv")  


def total_run_time(start):
    '''Print total run time
    '''
    
    stop = timeit.default_timer()
    total_time = stop - start
    
    #format time
    ty_res = time.gmtime(total_time)
    res = time.strftime("%H:%M:%S",ty_res)
    
    click.echo(f"Total run time: {res}")


#adapted from https://stackoverflow.com/questions/2104080/how-do-i-check-file-size-in-python#2104083
def convert_bytes(num):
    '''this function will convert bytes to MB.... GB... etc
    '''
    
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        
        if num < 1024.0:
            
            return f'{num:.1f} {x}'
        
        num /= 1024.0


def file_size(archive):
    '''calculates total size of split archive files
    '''
    
    #calculate total size of list of files
    file_list = glob.glob(f"{archive}.part-*")
    size =  sum(os.path.getsize(f) for f in file_list if os.path.isfile(f))
    
    return convert_bytes(size)



####command line parser####
@click.group()

def cli():
    '''Management of data backups to/from Cambridge University Research Cold Storage (RCS)
    '''



#define subparser for uploading data to RCS        
@click.command(name="up")

@click.option("-k","--keep", 
              is_flag=True,
              help="Keep split archive files of target dir")

@click.option("-c","--csv", 
              is_flag=True,
              help="Create empty data.csv file in current directory")


def up(csv,keep):
    '''Upload data to RCS
    '''
    
    #start total run timer
    start = timeit.default_timer()
    
    #create empty data.csv if requested        
    if csv:
        
        click.secho("Creating new data.csv", fg="green")
        
        header = "id,crsid,project_dir,date_up,date_down,temp_path,target_dir,remote_dest_dir,chunk_size,exclude_dir,md5sum_up,md5sum_down,archive_size,download_dir,version"

        #write to file
        with open(os.path.join(cdir,"data.csv"), "w") as text_file:
            
            print(header, file=text_file)
            
        return
        
    #open data.csv
    csv = pd.read_csv(os.path.join(cdir,"data.csv"))
    csv = csv.set_index("id")

    #get directories that have to be uploaded (no date for upload)
    csv_up = csv[csv["date_up"].isnull()]

    #total number of archives to upload
    total = len(csv_up)
    
    #exit if all directories have been uploaded already to RCS
    if total == 0:
        
        sys.exit("Nothing to upload to RCS!")
    
    #upload data
    for index,row in csv_up.iterrows():
        
        #get info
        crsid = row["crsid"]
        project_dir = row["project_dir"]
        temp_path = row["temp_path"]
        target_dir = row["target_dir"]
        remote_dest_dir = row["remote_dest_dir"]
        chunk_size = row["chunk_size"]
        exclude = row["exclude_dir"]
        
                        
        if type(exclude) == float or exclude == np.nan:
            
            exclude = ""
        
        else:
            
            exclude = f"--exclude={exclude}"

        #check if target directory exists
        if not path.exists(target_dir):
            
            click.secho(f"ERROR: target_dir ({target_dir}) does not exist!", fg="red")
            
            continue #go to next dir if any
        
        #tar file name
        archive = os.path.join(temp_path,f"{os.path.basename(target_dir)}.tar.gz")
        
        click.secho(f"Creating archive for {target_dir} at RCS...", fg="green")
        
        
        #check if archive has been split before
        if not os.path.exists(f"{archive}.split.done"):
            
            #create archive
            click.echo(f"Creating split {archive} ...")
            
            target_base = os.path.dirname(target_dir)
            target_name = os.path.basename(target_dir)
            
            md5sum_file = os.path.join(temp_path,f"md5sum_{os.path.basename(target_dir)}.txt")
            
            tar = f'tar -vc -C {target_base} {exclude} {target_name} | pigz | tee >(md5sum > "{md5sum_file}") | split -b {chunk_size} - {archive}.part-'
            
            time.sleep(5)
            
            #get md5sum from text file
            if run(tar):
                
                Path(os.path.join(f"{archive}.split.done")).touch()
                
                with open(md5sum_file) as f:
                    md5sum_up = f.readline().split("  ")[0]
                
                #remove md5sum file
                os.remove(md5sum_file)
                    
        else:
            
            click.echo(f"{archive} has been created and split before...")
            
        #wait for user input (otherwise rsync can timeout if user does not promptly enter password)
        click.echo("Transferring split archive files to RCS...")
        
        input("Press Enter to continue...") 
        
        rsync = f"rsync -v -h --progress $(ls {archive}.part-*) {crsid}@rcs.uis.cam.ac.uk:{project_dir}/{remote_dest_dir}" 
               
        if run(rsync):
            
            #update csv
            csv.at[index,"md5sum_up"] = md5sum_up
            csv.at[index,"date_up"] = str(datetime.now().astimezone())
            
            try: #these columns might not exist if data.csv was created with older version of camrcs
                
                csv.at[index,"version"] = VERSION
                csv.at[index,"archive_size"] = file_size(archive)
            
            except KeyError: #just print to console
                
                click.echo(f"Total archive size is {file_size(archive)}")
                      
        
        #update csv with md5sum hash/date
        update_csv(csv)
                
    #remove archive and split archive files
    if not keep:
    
        click.echo("Removing all archive files...")
        remove = f"rm -r {archive}*"
    
    else:
    
        click.echo("Keeping all split archive files...")
    
    if run(remove):
        
        click.echo("Finished!")

    #display total run time
    total_run_time(start)
    


#define subparser for retrieving data from RCS
@click.command(name="down")

@click.option("-k","--keep", 
              is_flag=True,
              help="Keep split archive files of target dir")

@click.option("-t","--target", 
              type=int,
              help="Target archive (id) to retrieve from RCS")


def down(keep,target):
    '''Retrieve data from RCS
    '''
    #start run timer
    start = timeit.default_timer()
    
    #open data.csv
    csv = pd.read_csv(os.path.join(cdir,"data.csv"))
    csv = csv.set_index("id")
    
    #select row with relevant information
    row = csv.loc[target]
    
    #get info
    crsid = row["crsid"]
    project_dir = row["project_dir"]
    target_dir = row["target_dir"]
    download_dir = row["download_dir"]
    remote_dest_dir = row["remote_dest_dir"]
    md5sum_up = row["md5sum_up"]
    
    click.secho(f"Retrieving archive {os.path.join(project_dir,remote_dest_dir)} from RCS...", fg="green")
    
    #perform some checks
    if type(download_dir) != str:
        
        click.secho("ERROR: download_dir is not a valid path (no value in data.csv?)...", fg="red")
        sys.exit()
        
    #create rsync command
    archive = f"{os.path.basename(target_dir)}.tar.gz.part-*"
    archive = f"{os.path.join(project_dir,remote_dest_dir,archive)}"
    rsync = f"rsync -v -h {crsid}@rcs.uis.cam.ac.uk:{archive} {download_dir}"
    
    if run(rsync):
        
        csv.at[target,"date_down"] = str(datetime.now().astimezone())

    
    click.echo("Concatenating archive parts...")
        
    archive = os.path.join(download_dir,os.path.basename(target_dir)) + ".tar.gz"
    parts = f"{archive}.part-*"
    cat = f"cat $(ls {parts}) > {archive}"
    
    if run(cat):
        
        click.echo(f"Calculating md5sum for retrieved archive...")
        
        csv.at[target,"md5sum_down"] = md5(archive)
        
        click.echo("Done...")
    
    
    click.echo("Removing archive parts...")
    remove = f"rm {parts}"
    
    if run(remove):
        
        click.echo(f"Comparing md5sum of uploaded archive vs retrieved archive...")
    
        
    if csv.at[target,"md5sum_down"] == md5sum_up:
        
        click.echo("Retrieved archive correct...")
                    
    else:
        
        click.secho(f"Retrieved archive incorrect...\nRun camrcs again!", fg="red")
        
        sys.exit()
    
    click.echo("Unpacking retrieved archive...")
        
    #unzipping/unpacking in seperate commands
    #https://superuser.com/questions/841865/extracting-a-tar-gz-file-returns-this-does-not-look-like-a-tar-archive
    unzip_archive = os.path.basename(archive.replace(".gz",""))
    
    if keep:
        
        untar = f"pigz -dk {archive} ; cd {download_dir}; tar -xvf {unzip_archive}; rm {unzip_archive}"
    
    else:
        
        os.makedirs(download_dir, exist_ok=True)
        untar = f"pigz -d {archive} ; cd {download_dir}; tar -xvf {unzip_archive}; rm {unzip_archive}"
        
    if run(untar): 
        
        #update csv with md5 hash/date
        update_csv(csv)
        
        click.echo("Finished!")
    
    #display total run time
    total_run_time(start)
    
    

@click.command(name="version")

def version():
    '''Print version and quit
    '''

    click.secho(f"camrcs v{VERSION}", fg="green")



#add subparsers
cli.add_command(up)
cli.add_command(down)
cli.add_command(version)






