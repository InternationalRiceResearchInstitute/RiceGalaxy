#!/usr/bin/env python
"""
Export a history to an archive file using attribute files.

usage: %prog history_attrs dataset_attrs job_attrs out_file
    -G, --gzip: gzip archive file
"""
from __future__ import print_function

import optparse
import os
import sys
import tarfile
from json import dumps, loads

from galaxy.util import FILENAME_VALID_CHARS


def get_dataset_filename(name, ext, hid):
    """
    Builds a filename for a dataset using its name an extension.
    """
    base = ''.join(c in FILENAME_VALID_CHARS and c or '_' for c in name)
    return base + "_%s.%s" % (hid, ext)


def create_archive(history_attrs_file, datasets_attrs_file, jobs_attrs_file, out_file, gzip=False):
    """ Create archive from the given attribute/metadata files and save it to out_file. """
    tarfile_mode = "w"
    if gzip:
        tarfile_mode += ":gz"
    try:

        history_archive = tarfile.open(out_file, tarfile_mode)

        # Read datasets attributes from file.
        datasets_attr_in = open(datasets_attrs_file, 'rb')
        datasets_attr_str = ''
        buffsize = 1048576
        try:
            while True:
                datasets_attr_str += datasets_attr_in.read(buffsize)
                if not datasets_attr_str or len(datasets_attr_str) % buffsize != 0:
                    break
        except OverflowError:
            pass
        datasets_attr_in.close()
        datasets_attrs = loads(datasets_attr_str)

        # Add datasets to archive and update dataset attributes.
        # TODO: security check to ensure that files added are in Galaxy dataset directory?
        for dataset_attrs in datasets_attrs:
            if dataset_attrs['exported']:
                dataset_file_name = dataset_attrs['file_name']  # Full file name.
                dataset_hid = dataset_attrs['hid']
                dataset_archive_name = os.path.join('datasets',
                                                    get_dataset_filename(dataset_attrs['name'], dataset_attrs['extension'], dataset_hid))
                history_archive.add(dataset_file_name, arcname=dataset_archive_name)

                # Include additional files for example, files/images included in HTML output.
                extra_files_path = dataset_attrs['extra_files_path']
                if extra_files_path:
                    try:
                        file_list = os.listdir(extra_files_path)
                    except OSError:
                        file_list = []

                    if len(file_list):
                        dataset_extra_files_path = 'datasets/extra_files_path_%s' % dataset_hid
                        for fname in file_list:
                            history_archive.add(os.path.join(extra_files_path, fname),
                                                arcname=(os.path.join(dataset_extra_files_path, fname)))
                        dataset_attrs['extra_files_path'] = dataset_extra_files_path
                    else:
                        dataset_attrs['extra_files_path'] = ''

                # Update dataset filename to be archive name.
                dataset_attrs['file_name'] = dataset_archive_name

        # Rewrite dataset attributes file.
        datasets_attrs_out = open(datasets_attrs_file, 'w')
        datasets_attrs_out.write(dumps(datasets_attrs))
        datasets_attrs_out.close()

        # Finish archive.
        history_archive.add(history_attrs_file, arcname="history_attrs.txt")
        history_archive.add(datasets_attrs_file, arcname="datasets_attrs.txt")
        if os.path.exists(datasets_attrs_file + ".provenance"):
            history_archive.add(datasets_attrs_file + ".provenance", arcname="datasets_attrs.txt.provenance")
        history_archive.add(jobs_attrs_file, arcname="jobs_attrs.txt")
        history_archive.close()

        # Status.
        return 'Created history archive.'
    except Exception as e:
        return 'Error creating history archive: %s' % str(e), sys.stderr


def main():
    # Parse command line.
    parser = optparse.OptionParser()
    parser.add_option('-G', '--gzip', dest='gzip', action="store_true", help='Compress archive using gzip.')
    (options, args) = parser.parse_args()
    gzip = bool(options.gzip)
    history_attrs, dataset_attrs, job_attrs, out_file = args

    # Create archive.
    status = create_archive(history_attrs, dataset_attrs, job_attrs, out_file, gzip)
    print(status)


if __name__ == "__main__":
    main()
