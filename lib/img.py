import multiprocessing
import os
import shutil
import subprocess
import logging

import lib.db as db
import lib.config as config

def create_tiff(raw_path, tmp_path):
    exe = os.path.join(config.get_path('ufraw_bindir'), 'ufraw-batch')
    args = config.get_exe_args('ufraw-batch')
    proc = subprocess.Popen(
            [exe] + args + ['--output={}'.format(tmp_path), raw_path],
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE)
    out, err = proc.communicate()

def copy_exif(fin, fout):
    exe = os.path.join(config.get_path('exiftool'), 'exiftool')
    proc = subprocess.Popen(
            [
                exe,
                '-TagsFromFile',
                fin,
                fout
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    out, err = proc.communicate()

def align_tiffs(tiffs, img_name):
    log = logging.getLogger()
    log.info("Aligning images for {}".format(img_name))
    tmp_dir = config.get_path('tmp')
    exe = os.path.join(config.get_path('hugin_bindir'), 'align_image_stack')
    pid = os.getpid()
    path = os.path.join(tmp_dir, "{}.hdr".format(img_name))
    p_out = subprocess.Popen(
            [
                exe,
                '-i',
                '-o', path
            ] + tiffs,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    out, err = p_out.communicate()
    return path

def tonemap(hdr, tmo, img_name):
    log = logging.getLogger()
    outdir = config.get_path('tmp')
    pfstools_path = config.get_path('pfstools_bindir')
    tmo_name = tmo.rsplit('_', 1)[1]
    outfile=os.path.join(outdir, "{}.{}.tiff".format(img_name, tmo_name))
    
    log.info("Tonemapping {} with algorithm {}".format(img_name, tmo_name))

    settings = config.get_tmo_options(tmo)

    p_in = subprocess.Popen(
            [
                os.path.join(pfstools_path, 'pfsin'),
                '--quiet',
                hdr
            ],
            stdout=subprocess.PIPE)
    p_tone = subprocess.Popen(
            [
                os.path.join(pfstools_path, tmo)
            ] + config.get_exe_args(tmo),
            stdin=p_in.stdout,
            stdout=subprocess.PIPE)
    if 'gamma' in settings:
        p_gamma = subprocess.Popen(
                [
                    os.path.join(pfstools_path, 'pfsgamma'),
                    '-g', settings['gamma']
                ],
                stdin=p_tone.stdout,
                stdout=subprocess.PIPE)
        outfd = p_gamma.stdout
    else:
        outfd = p_tone.stdout

    p_out = subprocess.Popen(
            [
                os.path.join(pfstools_path, 'pfsout'),
                outfile
            ],
            stdin=outfd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    p_in.stdout.close()
    p_tone.stdout.close()
    if 'gamma' in settings:
        outfd.close()
    out, err = p_out.communicate()
    return outfile

def merge_images(base_img, overlay_imgs, img_name):
    outdir=config.get_path('tmp')
    outfile = os.path.join(outdir, "{}.hdr.tiff".format(img_name))
    overlay = []
    for img, settings in overlay_imgs.items():
        args = "( {} -trim -alpha set -channel A -evaluate set {}% ) -compose overlay -composite".format(img, settings['opacity'])
        overlay += args.split(" ")
    proc = subprocess.Popen(
            [
                '/usr/bin/convert',
                base_img,
            ] + overlay + [ outfile ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    out, err = proc.communicate()
    copy_exif_data([base_img], outfile)
    return outfile
    
def remove_files(files):
    for f in files:
        os.remove(f)

def create_hdr(tiffs, img_name):
    outdir = config.get_path('outdir')
    out_settings = config.get_output_options()

    aligned = align_tiffs(tiffs, img_name)
    tonemaps = {}
    for tmo in config.get_tmos():
        tmo_name = tmo.rsplit('_', 1)[1]
        f = tonemap(aligned, tmo, img_name)
        copy_exif_data(tiffs, f)
        if out_settings.getboolean('save_tonemaps'):
            save_tiff(f, "{}.{}".format(img_name, tmo_name))
        tonemaps[f] = {'opacity': config.get_tmo_options(tmo)['opacity']}
    hdr_img = merge_images(tiffs[0], tonemaps, img_name)
    save_tiff(hdr_img, "{}.{}".format(img_name, out_settings['hdr_suffix']))
    if not out_settings.getboolean('save_tmp_files'):
        remove_files([aligned, hdr_img] + list(tonemaps.keys()))


def save_tiff(tiff, outname):
    log = logging.getLogger()
    settings = config.get_output_options()
    outfile = os.path.join(
            config.get_path('outdir'),
            "{}.{}".format(outname, settings['format']))
    log.info("saving {} as {}".format(tiff, outfile))
    exe = os.path.join(config.get_path('imagick_bindir'), 'convert')
    args = config.get_exe_args('output')
    proc = subprocess.Popen(
            [exe, tiff] + args + [outfile],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    out, err = proc.communicate()
    copy_exif_data([tiff], outfile)

def copy_exif_data(sources, target):
    source = sources[0]
    proc = subprocess.Popen(
            [
                '/usr/bin/exiftool',
                '-overwrite_original',
                '-TagsFromFile',
                source,
                target
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    out, err = proc.communicate()
    shutil.copystat(source, target)

class ImageProcessor(multiprocessing.Process):

    def __init__(self, images):
        super(ImageProcessor, self).__init__()
        self.log = logging.getLogger()
        self.images = images
        self.db_url = config.get_path('db')
        self.archive_dir = config.get_path('archive')
        self.outdir = config.get_path('outdir')
        self.tmp_dir = config.get_path('tmp')

    def copy_images(self, files):
        if not os.path.isdir(self.outdir):
            os.makedirs(self.outdir)

        for f in files:
            shutil.copyfile(f['path'], os.path.join(self.outdir, f['name']))
            shutil.copystat(f['path'], os.path.join(self.outdir, f['name']))

    def process_raws(self, files):
        num_files = len(files)
        tiffs = []
        orig_saved = False
        save_all_raws = config.get_output_options().getboolean('save_all_brackets')
        if not files:
            return

        for f in sorted(files, key=lambda x: x['name']):
            if num_files < 2 and f['processed']:
                return
            f['short_name'] = f['name'].rsplit(".", 1)[0]
            if f['seq'] and f['seq'] < 2:
                img_name = f['short_name']
            tiff = os.path.join(self.tmp_dir, "{}.tiff".format(f['short_name']))
            create_tiff(f['path'], tiff)
            shutil.copystat(f['path'], tiff)
            if save_all_raws or not orig_saved:
                save_tiff(tiff, f['short_name'])
                orig_saved = True
            tiffs.append(tiff)
        if num_files > 1:
            create_hdr(tiffs, img_name)
        if not config.get_output_options().getboolean('save_tmp_files'):
            remove_files(tiffs)


    def run(self):
        conn = db.open_db(self.db_url)
        for img in self.images:
            cur = conn.cursor()
            meta = db.get_files_for_image(cur, img)
            raws = [x for x, y in meta.items() if y['type'] in config.FT_RAW]
            non_raws = [x for x, y in meta.items() if x not in raws]
            for root, dirs, files in os.walk(self.archive_dir):
                for f in files:
                    if f in meta:
                        meta[f]['path'] = os.path.join(root, f)
            non_raws_id = [x.rsplit('.', 1)[0] for x in non_raws]
            raw_processing = []
            copy = []
            for name, attrs in meta.items():
                if name in raws:
                    if name.rsplit('.', 1)[0] in non_raws_id:
                        attrs['processed'] = True
                    else:
                        attrs['processed'] = False
                    raw_processing.append(attrs)
                else:
                    copy.append(attrs)
            self.copy_images(copy)
            self.log.info("processing {} raws for image {}".format(len(raw_processing), img))
            self.process_raws(raw_processing)
            db.set_image_handled(cur, img)
            cur.close()
            conn.commit()
            



                





