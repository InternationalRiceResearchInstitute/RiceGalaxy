#!/usr/bin/env python
from __future__ import print_function

import os
import sys

from common import submit

try:
    assert sys.argv[3]
    data = {}
    data['from_ld_id'] = sys.argv[3]
except IndexError:
    print('usage: %s key url library_file_id' % os.path.basename(sys.argv[0]))
    print('    library_file_id is from /api/libraries/<library_id>/contents/<library_file_id>')
    sys.exit(1)

submit(sys.argv[1], sys.argv[2], data)
