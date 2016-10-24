#!/usr/bin/env python3

import multiprocessing
import os
import sqlite3
import shutil
import sys
import logging

import lib.db as db
import lib.img as img
import lib.exif
import lib.config as config

def archive_files(db_conn, source, target):

    log = logging.getLogger()
    cur = db_conn.cursor()
    for root, dirs, files in os.walk(source):
        for f in files:
            f_info = f.rsplit('.', 1)
            f_type = f_info[1].lower()
            target_dir = os.path.join(target, f_type)
            target_file = os.path.join(target_dir, f)

            if f_type not in config.FT_IMG:
                log.debug("Skipping {}: file type {} not supported".format(f, f_type))
                continue

            if db.has_file(cur, f, db.F_STATE_SYNCED):
                log.debug("Skipping {}: file already in db".format(f))
                continue

            if not os.path.isdir(target_dir):
                os.makedirs(target_dir)
            
            if os.path.isfile(target_file):
                log.debug("Skipping {}: file already synced".format(f))
                continue

            log.info("Copying {} to archive...".format(f))
            shutil.copyfile(os.path.join(root, f), target_file)
            shutil.copystat(os.path.join(root, f), target_file)
            log.debug("{} archived".format(f))
    cur.close()
    db_conn.commit()

def process_images(db_url, archive_dir, tmp_dir, outdir):
    conn = db.open_db(db_url)
    cur = conn.cursor()
    images = db.get_unprocessed_images(cur)
    cur.close()
    conn.commit()
    conn.close()
    processes = []
    cpus = multiprocessing.cpu_count()
    if len(images) < cpus:
        proc = img.ImageProcessor(images)
        proc.start()
        processes = [proc]
    else:
        chunk = int(len(images)/cpus)+1
        for i in range(1, cpus+1):
            proc = img.ImageProcessor(images[chunk*(i-1):chunk*i])
            proc.start()
            processes.append(proc)

    for proc in processes:
        proc.join()


def main():


    source = config.get_path('source')
    archive = config.get_path('archive')
    tmp_dir = config.get_path('tmp')
    db_url = config.get_path('db')
    outdir = config.get_path('outdir')
    conn = db.open_db(db_url)

    log = logging.getLogger()
    log.addHandler(logging.StreamHandler(stream=sys.stdout))
    log.setLevel(logging.INFO)
    
    log.info("Searching for new files to archive")
    archive_files(conn, source, archive)

    log.info("Searching archive content for unprocessed items")
    cur = conn.cursor()
    for root, dirs, files in os.walk(archive):
        for f in files:
            f_info = f.rsplit('.', 1)
            f_type = f_info[1].lower()
            if db.has_file(cur, f) is not None:
                continue
            if f_type in config.FT_IMG:
                exif = lib.exif.get_exif(os.path.join(root, f))
                db.add_file(cur, exif, f, f_type)
    conn.commit()
    conn.close()
    log.info("Processing images")
    process_images(db_url, archive, tmp_dir, outdir)
    log.info("All images processed")
    sys.exit(0)
     
    


if __name__ == '__main__':
    main()
