import json
import os
import re
import sys
import shutil
import logging

from . import provenance
from . import config

def checkOccamLib():
    occamlib = config.get_occamlib_path()
    if occamlib is None  or not os.path.exists(occamlib):
        sys.stderr.write('The occam library was not found. RTFM.\n')
        return False
    return True


def get_flag(flags, flag, default=None):
    for (x, y) in flags:
        if x == '--{0}'.format(flag):
            return y
    return default

def get_work_dir(flags):
    d = get_flag(flags, 'work-dir')
    if d is None:
        return os.getcwd()
    return os.path.abspath(d)


def get_manifest(args):
    manifest = None
    if not args:
        sys.stderr.write('\nNo manifest file specified\n\n')
        return manifest
    try:
        manifest_file = args[0]
        if not os.path.exists(manifest_file):
            sys.stderr.write('\nManifest file {0} not found\n\n'.format(manifest_file))
        elif  not os.path.isfile(manifest_file):
            sys.stderr.write('\nManifest file {0} not a file\n\n'.format(manifest_file))
        else:
            manifest = json.load(open(manifest_file, 'r'))
    except Exception:
        sys.stderr.write('\nReading and parsing the manifest file {0} failed\n\n'.format(args[0]))
    return manifest


def make_work_dir(d):
    if not os.path.exists(d):
        sys.stderr.write('making working directory... "{0}"\n'.format(d))
        os.mkdir(d)
    if not os.path.isdir(d):
        sys.stderr.write('working directory  "{0}" is not a directory\n'.format(d))
        return False
    else:
        return True


def sanity_check_manifest(manifest):
    """ Nurse maid the users.
    """
    manifest_keys = ['ldflags', 'args', 'name', 'native_libs', 'binary', 'modules']

    old_manifest_keys = ['modules', 'libs', 'search', 'shared']

    new_manifest_keys = ['main', 'binary']

    dodo_manifest_keys = ['watch']

    replaces = {'modules': 'main', 'libs': 'modules', 'search': 'ldflags'}

    warnings = [False]

    def cr(warnings):
        """ I like my warnings to stand out.
        """
        if not warnings[0]:
            warnings[0] = True
            sys.stderr.write('\n')

    if manifest is None:
        sys.stderr.write('\nManifest is None.\n')
        return False

    if not isinstance(manifest, dict):
        sys.stderr.write('\nManifest is not a dictionary: {0}.\n'.format(type(manifest)))
        return False

    for key in manifest:
        if key in manifest_keys:
            continue

        if key in dodo_manifest_keys:
            cr(warnings)
            sys.stderr.write('Warning: "{0}" is no longer supported; ignoring.\n'.format(key))
            continue


        if key in old_manifest_keys:
            cr(warnings)
            sys.stderr.write('Warning: old style key "{0}" is DEPRECATED, use {1}.\n'.format(key, replaces[key]), )
            continue

        if not key in new_manifest_keys:
            cr(warnings)
            sys.stderr.write('Warning: "{0}" is not a recognized key; ignoring.\n'.format(key))
            continue

    return True

def check_manifest(manifest):

    ok = sanity_check_manifest(manifest)

    if not ok:
        return (False, )

    main = manifest.get('main')
    if main is None:
        sys.stderr.write('No modules in manifest\n')
        return (False, )

    binary = manifest.get('binary')
    if binary is None:
        sys.stderr.write('No binary in manifest\n')
        return (False, )

    modules = manifest.get('modules')
    if modules is None:
        sys.stderr.write('No libs in manifest\n')
        modules = []

    native_libs = manifest.get('native_libs')
    if native_libs is None:
        native_libs = []

    ldflags = manifest.get('ldflags')
    if ldflags is None:
        ldflags = []


    args = manifest.get('args')

    name = manifest.get('name')
    if name is None:
        sys.stderr.write('No name in manifest\n')
        return (False, )

    return (True, main, binary, modules, native_libs, ldflags, args, name)


#iam: used to be just os.path.basename; but now when we are processing trees
# the leaf names are not necessarily unique.
def prevent_collisions(x):
    folders = []
    path = x
    while 1:
        path, folder = os.path.split(path)

        if folder != "":
            folders.append(folder)

        if path == "" or path == os.sep:
            break

    folders.reverse()
    return "_".join(folders)

bit_code_pattern = re.compile(r'\.bc$', re.IGNORECASE)


def populate_work_dir(module, libs, work_dir):
    files = {}

    for x in [module] + libs:
        if bit_code_pattern.search(x):
            bn = prevent_collisions(x)
            target = os.path.join(work_dir, bn)
            if os.path.abspath(x) != target:
                shutil.copyfile(x, target)
            idx = target.rfind('.bc')
            files[x] = provenance.FileStream(target[:idx], 'bc')
        else:
            sys.stderr.write('Ignoring {0}\n'.format(x))


    return files


def makeLogfile(logfile):
    if not os.path.exists(logfile):
        _, path_filename = os.path.splitdrive(logfile)
        path, _ = os.path.split(path_filename)
        if not os.path.exists(path):
            os.mkdir(path)

def setLogger():
    logfile = config.get_logfile()
    logger = logging.getLogger()

    makeLogfile(os.path.realpath(logfile))

    hdlr = logging.FileHandler(logfile)
    hdlr.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(hdlr)

    levels = {'CRITICAL' : logging.CRITICAL,
              'ERROR'    : logging.ERROR,
              'WARNING'  : logging.WARNING,
              'INFO'     : logging.INFO,
              'DEBUG'    : logging.DEBUG}

    level = None
    if os.environ.has_key('OCCAM_LOGLEVEL'):
        level = levels[os.environ['OCCAM_LOGLEVEL']]
    if level is None:
        level = logging.WARNING
    logger.setLevel(level)
    logger.info(">> %s\n", ' '.join(sys.argv))
