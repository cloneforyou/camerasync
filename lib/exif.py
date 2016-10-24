import subprocess

def get_exif(path):

    proc = subprocess.Popen(
            [
                '/usr/bin/exiftool',
                path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    out, err = proc.communicate()
    ret = {}
    for line in out.decode('utf-8').splitlines():
        line_info = line.split(':', 1)
        key = line_info[0].strip(' ')
        val = line_info[1].strip(' ')
        ret[key] = val
    return ret


