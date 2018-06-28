"""
File format detector
"""
from __future__ import absolute_import

import codecs
import gzip
import logging
import os
import re
import shutil
import sys
import tempfile
import zipfile

from six import text_type

from galaxy import util
from galaxy.datatypes.binary import Binary
from galaxy.util import (
    compression_utils,
    multi_byte,
    unicodify
)
from galaxy.util.checkers import (
    check_binary,
    check_html,
    is_bz2,
    is_gzip
)

if sys.version_info < (3, 3):
    import bz2file as bz2
else:
    import bz2

log = logging.getLogger(__name__)


def get_test_fname(fname):
    """Returns test data filename"""
    path, name = os.path.split(__file__)
    full_path = os.path.join(path, 'test', fname)
    return full_path


def stream_to_open_named_file(stream, fd, filename, source_encoding=None, source_error='strict', target_encoding=None, target_error='strict'):
    """Writes a stream to the provided file descriptor, returns the file's name and bool( is_multi_byte ). Closes file descriptor"""
    # signature and behavor is somewhat odd, due to backwards compatibility, but this can/should be done better
    CHUNK_SIZE = 1048576
    data_checked = False
    is_compressed = False
    is_binary = False
    is_multi_byte = False
    try:
        codecs.lookup(target_encoding)
    except:
        target_encoding = util.DEFAULT_ENCODING  # utf-8
    if not source_encoding:
        source_encoding = util.DEFAULT_ENCODING  # sys.getdefaultencoding() would mimic old behavior (defaults to ascii)
    while True:
        chunk = stream.read(CHUNK_SIZE)
        if not chunk:
            break
        if not data_checked:
            # See if we're uploading a compressed file
            if zipfile.is_zipfile(filename):
                is_compressed = True
            else:
                try:
                    if text_type(chunk[:2]) == text_type(util.gzip_magic):
                        is_compressed = True
                except:
                    pass
            if not is_compressed:
                # See if we have a multi-byte character file
                chars = chunk[:100]
                is_multi_byte = multi_byte.is_multi_byte(chars)
                if not is_multi_byte:
                    is_binary = util.is_binary(chunk)
            data_checked = True
        if not is_compressed and not is_binary:
            if not isinstance(chunk, text_type):
                chunk = chunk.decode(source_encoding, source_error)
            os.write(fd, chunk.encode(target_encoding, target_error))
        else:
            # Compressed files must be encoded after they are uncompressed in the upload utility,
            # while binary files should not be encoded at all.
            os.write(fd, chunk)
    os.close(fd)
    return filename, is_multi_byte


def stream_to_file(stream, suffix='', prefix='', dir=None, text=False, **kwd):
    """Writes a stream to a temporary file, returns the temporary file's name"""
    fd, temp_name = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir, text=text)
    return stream_to_open_named_file(stream, fd, temp_name, **kwd)


def check_newlines(fname, bytes_to_read=52428800):
    """
    Determines if there are any non-POSIX newlines in the first
    number_of_bytes (by default, 50MB) of the file.
    """
    CHUNK_SIZE = 2 ** 20
    f = open(fname, 'r')
    for chunk in f.read(CHUNK_SIZE):
        if f.tell() > bytes_to_read:
            break
        if chunk.count('\r'):
            f.close()
            return True
    f.close()
    return False


def convert_newlines(fname, in_place=True, tmp_dir=None, tmp_prefix=None):
    """
    Converts in place a file from universal line endings
    to Posix line endings.

    >>> fname = get_test_fname('temp.txt')
    >>> open(fname, 'wt').write("1 2\\r3 4")
    >>> convert_newlines(fname, tmp_prefix="gxtest", tmp_dir=tempfile.gettempdir())
    (2, None)
    >>> open(fname).read()
    '1 2\\n3 4\\n'
    """
    fd, temp_name = tempfile.mkstemp(prefix=tmp_prefix, dir=tmp_dir)
    fp = os.fdopen(fd, "wt")
    i = None
    for i, line in enumerate(open(fname, "U")):
        fp.write("%s\n" % line.rstrip("\r\n"))
    fp.close()
    if i is None:
        i = 0
    else:
        i += 1
    if in_place:
        shutil.move(temp_name, fname)
        # Return number of lines in file.
        return (i, None)
    else:
        return (i, temp_name)


def sep2tabs(fname, in_place=True, patt="\\s+"):
    """
    Transforms in place a 'sep' separated file to a tab separated one

    >>> fname = get_test_fname('temp.txt')
    >>> open(fname, 'wt').write("1 2\\n3 4\\n")
    >>> sep2tabs(fname)
    (2, None)
    >>> open(fname).read()
    '1\\t2\\n3\\t4\\n'
    """
    regexp = re.compile(patt)
    fd, temp_name = tempfile.mkstemp()
    fp = os.fdopen(fd, "wt")
    i = None
    for i, line in enumerate(open(fname)):
        line = line.rstrip('\r\n')
        elems = regexp.split(line)
        fp.write("%s\n" % '\t'.join(elems))
    fp.close()
    if i is None:
        i = 0
    else:
        i += 1
    if in_place:
        shutil.move(temp_name, fname)
        # Return number of lines in file.
        return (i, None)
    else:
        return (i, temp_name)


def convert_newlines_sep2tabs(fname, in_place=True, patt="\\s+", tmp_dir=None, tmp_prefix=None):
    """
    Combines above methods: convert_newlines() and sep2tabs()
    so that files do not need to be read twice

    >>> fname = get_test_fname('temp.txt')
    >>> open(fname, 'wt').write("1 2\\r3 4")
    >>> convert_newlines_sep2tabs(fname, tmp_prefix="gxtest", tmp_dir=tempfile.gettempdir())
    (2, None)
    >>> open(fname).read()
    '1\\t2\\n3\\t4\\n'
    """
    regexp = re.compile(patt)
    fd, temp_name = tempfile.mkstemp(prefix=tmp_prefix, dir=tmp_dir)
    fp = os.fdopen(fd, "wt")
    for i, line in enumerate(open(fname, "U")):
        line = line.rstrip('\r\n')
        elems = regexp.split(line)
        fp.write("%s\n" % '\t'.join(elems))
    fp.close()
    if in_place:
        shutil.move(temp_name, fname)
        # Return number of lines in file.
        return (i + 1, None)
    else:
        return (i + 1, temp_name)


def iter_headers(fname, sep, count=60, is_multi_byte=False, comment_designator=None):
    with compression_utils.get_fileobj(fname) as in_file:
        idx = 0
        for line in in_file:
            line = line.rstrip('\n\r')
            if is_multi_byte:
                # TODO: fix this - sep is never found in line
                line = unicodify(line, 'utf-8')
                sep = sep.encode('utf-8')
                if comment_designator is not None and comment_designator != '':
                    comment_designator = comment_designator.encode('utf-8')
            if comment_designator is not None and comment_designator != '' and line.startswith(comment_designator):
                continue
            yield line.split(sep)
            idx += 1
            if idx == count:
                break


def get_headers(fname, sep, count=60, is_multi_byte=False, comment_designator=None):
    """
    Returns a list with the first 'count' lines split by 'sep', ignoring lines
    starting with 'comment_designator'

    >>> fname = get_test_fname('complete.bed')
    >>> get_headers(fname,'\\t')
    [['chr7', '127475281', '127491632', 'NM_000230', '0', '+', '127486022', '127488767', '0', '3', '29,172,3225,', '0,10713,13126,'], ['chr7', '127486011', '127488900', 'D49487', '0', '+', '127486022', '127488767', '0', '2', '155,490,', '0,2399']]
    >>> fname = get_test_fname('test.gff')
    >>> get_headers(fname, '\\t', count=5, comment_designator='#')
    [[''], ['chr7', 'bed2gff', 'AR', '26731313', '26731437', '.', '+', '.', 'score'], ['chr7', 'bed2gff', 'AR', '26731491', '26731536', '.', '+', '.', 'score'], ['chr7', 'bed2gff', 'AR', '26731541', '26731649', '.', '+', '.', 'score'], ['chr7', 'bed2gff', 'AR', '26731659', '26731841', '.', '+', '.', 'score']]
    """
    return list(iter_headers(fname=fname, sep=sep, count=count, is_multi_byte=is_multi_byte, comment_designator=comment_designator))


def is_column_based(fname, sep='\t', skip=0, is_multi_byte=False):
    """
    Checks whether the file is column based with respect to a separator
    (defaults to tab separator).

    >>> fname = get_test_fname('test.gff')
    >>> is_column_based(fname)
    True
    >>> fname = get_test_fname('test_tab.bed')
    >>> is_column_based(fname)
    True
    >>> is_column_based(fname, sep=' ')
    False
    >>> fname = get_test_fname('test_space.txt')
    >>> is_column_based(fname)
    False
    >>> is_column_based(fname, sep=' ')
    True
    >>> fname = get_test_fname('test_ensembl.tab')
    >>> is_column_based(fname)
    True
    >>> fname = get_test_fname('test_tab1.tabular')
    >>> is_column_based(fname, sep=' ', skip=0)
    False
    >>> fname = get_test_fname('test_tab1.tabular')
    >>> is_column_based(fname)
    True
    """
    headers = get_headers(fname, sep, is_multi_byte=is_multi_byte)
    count = 0
    if not headers:
        return False
    for hdr in headers[skip:]:
        if hdr and hdr[0] and not hdr[0].startswith('#'):
            if len(hdr) > 1:
                count = len(hdr)
            break
    if count < 2:
        return False
    for hdr in headers[skip:]:
        if hdr and hdr[0] and not hdr[0].startswith('#'):
            if len(hdr) != count:
                return False
    return True


def guess_ext(fname, sniff_order, is_multi_byte=False):
    """
    Returns an extension that can be used in the datatype factory to
    generate a data for the 'fname' file

    >>> from galaxy.datatypes import registry
    >>> sample_conf = os.path.join(util.galaxy_directory(), "config", "datatypes_conf.xml.sample")
    >>> datatypes_registry = registry.Registry()
    >>> datatypes_registry.load_datatypes(root_dir=util.galaxy_directory(), config=sample_conf)
    >>> sniff_order = datatypes_registry.sniff_order
    >>> fname = get_test_fname('megablast_xml_parser_test1.blastxml')
    >>> guess_ext(fname, sniff_order)
    'blastxml'
    >>> fname = get_test_fname('interval.interval')
    >>> guess_ext(fname, sniff_order)
    'interval'
    >>> fname = get_test_fname('interval1.bed')
    >>> guess_ext(fname, sniff_order)
    'bed'
    >>> fname = get_test_fname('test_tab.bed')
    >>> guess_ext(fname, sniff_order)
    'bed'
    >>> fname = get_test_fname('sequence.maf')
    >>> guess_ext(fname, sniff_order)
    'maf'
    >>> fname = get_test_fname('sequence.fasta')
    >>> guess_ext(fname, sniff_order)
    'fasta'
    >>> fname = get_test_fname('file.html')
    >>> guess_ext(fname, sniff_order)
    'html'
    >>> fname = get_test_fname('test.gtf')
    >>> guess_ext(fname, sniff_order)
    'gtf'
    >>> fname = get_test_fname('test.gff')
    >>> guess_ext(fname, sniff_order)
    'gff'
    >>> fname = get_test_fname('gff_version_3.gff')
    >>> guess_ext(fname, sniff_order)
    'gff3'
    >>> fname = get_test_fname('temp.txt')
    >>> open(fname, 'wt').write("a\\t2")
    >>> guess_ext(fname, sniff_order)
    'txt'
    >>> fname = get_test_fname('temp.txt')
    >>> open(fname, 'wt').write("a\\t2\\nc\\t1\\nd\\t0")
    >>> guess_ext(fname, sniff_order)
    'tabular'
    >>> fname = get_test_fname('temp.txt')
    >>> open(fname, 'wt').write("a 1 2 x\\nb 3 4 y\\nc 5 6 z")
    >>> guess_ext(fname, sniff_order)
    'txt'
    >>> fname = get_test_fname('test_tab1.tabular')
    >>> guess_ext(fname, sniff_order)
    'tabular'
    >>> fname = get_test_fname('alignment.lav')
    >>> guess_ext(fname, sniff_order)
    'lav'
    >>> fname = get_test_fname('1.sff')
    >>> guess_ext(fname, sniff_order)
    'sff'
    >>> fname = get_test_fname('1.bam')
    >>> guess_ext(fname, sniff_order)
    'bam'
    >>> fname = get_test_fname('3unsorted.bam')
    >>> guess_ext(fname, sniff_order)
    'bam'
    >>> fname = get_test_fname('test.idpDB')
    >>> guess_ext(fname, sniff_order)
    'idpdb'
    >>> fname = get_test_fname('test.mz5')
    >>> guess_ext(fname, sniff_order)
    'h5'
    >>> fname = get_test_fname('issue1818.tabular')
    >>> guess_ext(fname, sniff_order)
    'tabular'
    >>> fname = get_test_fname('drugbank_drugs.cml')
    >>> guess_ext(fname, sniff_order)
    'cml'
    >>> fname = get_test_fname('q.fps')
    >>> guess_ext(fname, sniff_order)
    'fps'
    >>> fname = get_test_fname('drugbank_drugs.inchi')
    >>> guess_ext(fname, sniff_order)
    'inchi'
    >>> fname = get_test_fname('drugbank_drugs.mol2')
    >>> guess_ext(fname, sniff_order)
    'mol2'
    >>> fname = get_test_fname('drugbank_drugs.sdf')
    >>> guess_ext(fname, sniff_order)
    'sdf'
    >>> fname = get_test_fname('5e5z.pdb')
    >>> guess_ext(fname, sniff_order)
    'pdb'
    >>> fname = get_test_fname('mothur_datatypetest_true.mothur.otu')
    >>> guess_ext(fname, sniff_order)
    'mothur.otu'
    >>> fname = get_test_fname('1.gg')
    >>> guess_ext(fname, sniff_order)
    'gg'
    >>> fname = get_test_fname('diamond_db.dmnd')
    >>> guess_ext(fname, sniff_order)
    'dmnd'
    >>> fname = get_test_fname('1.xls')
    >>> guess_ext(fname, sniff_order)
    'excel.xls'
    >>> fname = get_test_fname('biom2_sparse_otu_table_hdf5.biom')
    >>> guess_ext(fname, sniff_order)
    'biom2'
    """
    file_ext = None
    for datatype in sniff_order:
        """
        Some classes may not have a sniff function, which is ok.  In fact, the
        Tabular and Text classes are 2 examples of classes that should never have
        a sniff function.  Since these classes are default classes, they contain
        few rules to filter out data of other formats, so they should be called
        from this function after all other datatypes in sniff_order have not been
        successfully discovered.
        """
        try:
            if datatype.sniff(fname):
                file_ext = datatype.file_ext
                break
        except:
            pass
    # Ugly hack for tsv vs tabular sniffing, we want to prefer tabular
    # to tsv but it doesn't have a sniffer - is TSV was sniffed just check
    # if it is an okay tabular and use that instead.
    if file_ext == 'tsv':
        if is_column_based(fname, '\t', 1, is_multi_byte=is_multi_byte):
            file_ext = 'tabular'
    if file_ext is not None:
        return file_ext

    headers = get_headers(fname, None)
    is_binary = False
    if is_multi_byte:
        is_binary = False
    else:
        for hdr in headers:
            for char in hdr:
                # old behavior had 'char' possibly having length > 1,
                # need to determine when/if this occurs
                is_binary = util.is_binary(char)
                if is_binary:
                    break
            if is_binary:
                break
    if is_binary:
        return 'data'  # default binary data type file extension
    if is_column_based(fname, '\t', 1, is_multi_byte=is_multi_byte):
        return 'tabular'  # default tabular data type file extension
    return 'txt'  # default text data type file extension


def handle_compressed_file(filename, datatypes_registry, ext='auto'):
    CHUNK_SIZE = 2 ** 20  # 1Mb
    is_compressed = False
    compressed_type = None
    keep_compressed = False
    is_valid = False
    for compressed_type, check_compressed_function in COMPRESSION_CHECK_FUNCTIONS:
        is_compressed = check_compressed_function(filename)
        if is_compressed:
            break  # found compression type
    if is_compressed:
        if ext in AUTO_DETECT_EXTENSIONS:
            check_exts = COMPRESSION_DATATYPES[compressed_type]
        elif ext in COMPRESSED_EXTENSIONS:
            check_exts = [ext]
        else:
            check_exts = []
        for compressed_ext in check_exts:
            compressed_datatype = datatypes_registry.get_datatype_by_extension(compressed_ext)
            if compressed_datatype.sniff(filename):
                ext = compressed_ext
                keep_compressed = True
                is_valid = True
                break

    if not is_compressed:
        is_valid = True
    elif not keep_compressed:
        is_valid = True
        fd, uncompressed = tempfile.mkstemp()
        compressed_file = DECOMPRESSION_FUNCTIONS[compressed_type](filename)
        while True:
            try:
                chunk = compressed_file.read(CHUNK_SIZE)
            except IOError as e:
                os.close(fd)
                os.remove(uncompressed)
                compressed_file.close()
                raise IOError('Problem uncompressing %s data, please try retrieving the data uncompressed: %s' % (compressed_type, e))
            if not chunk:
                break
            os.write(fd, chunk)
        os.close(fd)
        compressed_file.close()
        # Replace the compressed file with the uncompressed file
        shutil.move(uncompressed, filename)
    return is_valid, ext


def handle_uploaded_dataset_file(filename, datatypes_registry, ext='auto', is_multi_byte=False):
    is_valid, ext = handle_compressed_file(filename, datatypes_registry, ext=ext)

    if not is_valid:
        raise InappropriateDatasetContentError('The compressed uploaded file contains inappropriate content.')

    if ext in AUTO_DETECT_EXTENSIONS:
        ext = guess_ext(filename, sniff_order=datatypes_registry.sniff_order, is_multi_byte=is_multi_byte)

    if check_binary(filename):
        if not Binary.is_ext_unsniffable(ext) and not datatypes_registry.get_datatype_by_extension(ext).sniff(filename):
            raise InappropriateDatasetContentError('The binary uploaded file contains inappropriate content.')
    elif check_html(filename):
        raise InappropriateDatasetContentError('The uploaded file contains inappropriate HTML content.')
    return ext


AUTO_DETECT_EXTENSIONS = ['auto']  # should 'data' also cause auto detect?
DECOMPRESSION_FUNCTIONS = dict(gzip=gzip.GzipFile, bz2=bz2.BZ2File)
COMPRESSION_CHECK_FUNCTIONS = [('gzip', is_gzip), ('bz2', is_bz2)]
COMPRESSION_DATATYPES = dict(gzip=['bam', 'fastq.gz', 'fastqsanger.gz', 'fastqillumina.gz', 'fastqsolexa.gz', 'fastqcssanger.gz'], bz2=['fastq.bz2', 'fastqsanger.bz2', 'fastqillumina.bz2', 'fastqsolexa.bz2', 'fastqcssanger.bz2'])
COMPRESSED_EXTENSIONS = []
for exts in COMPRESSION_DATATYPES.values():
    COMPRESSED_EXTENSIONS.extend(exts)


class InappropriateDatasetContentError(Exception):
    pass


if __name__ == '__main__':
    import doctest
    doctest.testmod(sys.modules[__name__])
