import os
import re
import sqlite3
import sys
import json

import logging

F_STATE_SEEN = 0
F_STATE_SYNCED = 10
F_STATE_PROCESSED = 20

RE_IMG_ID = re.compile(r'^([^0-9]*)([0-9]+)([^0-9]*)')

def open_db(path):
    db_dir = os.path.dirname(path)
    if not os.path.isdir(db_dir):
        os.makedirs(db_dir)
    conn = sqlite3.connect(path)
    create_schema(conn)
    return conn

        

def has_file(cur, f_name, state=F_STATE_SEEN):
    cur.execute('SELECT id FROM file WHERE name=? AND processed >= ?', (f_name, state))
    res = cur.fetchone()
    if res:
        return res[0]
    else:
        return res

def set_image_handled(cur, image):
    cur.execute(
            ''' SELECT 
                    file.id 
                FROM 
                    file 
                    JOIN image ON file.image=image.id
                WHERE 
                    image.name = ?
            ''', (image,))
    for fid in cur.fetchall():
        cur.execute(
                'UPDATE file SET processed=? WHERE id=?',
                (F_STATE_PROCESSED, fid[0]))


def add_file(cur, exif, f_name, f_type):
    log = logging.getLogger()

    i_name = f_name.rsplit('.', 1)[0].lower()
    i_info = re.match(RE_IMG_ID, i_name)
    seq = 1
    if i_info:
        i_prefix = i_info.group(1)
        i_nr = i_info.group(2)
        i_suffix = i_info.group(3)
        if 'Release Mode' in exif \
                and 'Sequence Image Number' in exif:
            seq = int(exif['Sequence Image Number'])
            i_nr_int = int(i_nr)
            if exif['Release Mode'] == 'Exposure Bracketing':
                i_nr_int -= seq-1

            i_nr = format(i_nr_int, '0{}d'.format(len(i_nr)))
        i_name = "{}{}{}".format(i_prefix, i_nr, i_suffix)


    log.debug('{}: image {}'.format(f_name, i_name))
    cur.execute('SELECT id FROM image WHERE name=?', (i_name,))
    res = cur.fetchone()
    if not res:
        cur.execute(
                ''' INSERT INTO
                        image
                    (
                        name
                    ) VALUES (
                        ?
                    )
                ''', (i_name,))
        cur.execute('SELECT id FROM image WHERE name=?', (i_name,))
        res = cur.fetchone()
    i_id = res[0]
    if has_file(cur, f_name) is None:
        cur.execute(
                ''' INSERT INTO
                        file
                    (
                        name,
                        type,
                        processed,
                        seq,
                        image
                    ) VALUES (
                        ?,
                        ?,
                        0,
                        ?,
                        ?
                    )
                ''', (f_name, f_type, seq, i_id))
    
def get_files_for_image(cur, img_name):
    cur.execute(
            ''' SELECT
                    file.*
                FROM
                    file
                    JOIN image on file.image=image.id
                WHERE
                    image.name = ?
            ''', (img_name,))
    colnames = [x[0] for x in cur.description]
    res = [dict(zip(colnames, x)) for x in cur.fetchall()]
    ret = {}
    for r in res:
        ret[r['name']] = r

    return ret

def get_unprocessed_images(cur):
    cur.execute(
            ''' SELECT DISTINCT
                    image.name
                FROM
                    image
                    JOIN file ON image.id=file.image
                WHERE
                    file.processed < ?
            ''', (F_STATE_PROCESSED,))
    return [x[0] for x in cur.fetchall()]


def create_schema(conn):
    cur = conn.cursor()
    cur.execute('''
            CREATE TABLE IF NOT EXISTS 
                file (
                    id INTEGER PRIMARY KEY, 
                    name TEXT UNIQUE,
                    type TEXT,
                    seq INTEGER,
                    release_mode TEXT,
                    processed INTEGER,
                    image INTEGER
                    )
            ''')
    cur.execute('''
            CREATE TABLE IF NOT EXISTS
                image (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE
                    )
            ''')
    conn.commit()

