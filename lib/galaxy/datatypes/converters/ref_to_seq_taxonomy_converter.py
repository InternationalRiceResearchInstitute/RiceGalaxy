#!/usr/bin/env python
"""
convert a ref.taxonomy file to a seq.taxonomy file
Usage:
%python ref_to_seq_taxonomy_converter.py <ref.taxonom> <seq.taxonomy>
"""
import re
import sys

assert sys.version_info[:2] >= (2, 4)


def __main__():
    infile_name = sys.argv[1]
    outfile = open(sys.argv[2], 'w')
    for i, line in enumerate(open(infile_name)):
        line = line.rstrip()
        if line and not line.startswith('#'):
            fields = line.split('\t')
            # make sure the 2nd field (taxonomy) ends with a ;
            outfile.write('%s\t%s;\n' % (fields[0], re.sub(';$', '', fields[1])))

    outfile.close()


if __name__ == "__main__":
    __main__()
