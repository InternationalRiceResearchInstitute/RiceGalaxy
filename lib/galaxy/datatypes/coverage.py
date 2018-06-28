"""
Coverage datatypes

"""

import logging
import math

from galaxy.datatypes import metadata
from galaxy.datatypes.metadata import MetadataElement
from galaxy.datatypes.tabular import Tabular

log = logging.getLogger(__name__)


class LastzCoverage(Tabular):
    file_ext = "coverage"

    MetadataElement(name="chromCol", default=1, desc="Chrom column", param=metadata.ColumnParameter)
    MetadataElement(name="positionCol", default=2, desc="Position column", param=metadata.ColumnParameter)
    MetadataElement(name="forwardCol", default=3, desc="Forward or aggregate read column", param=metadata.ColumnParameter)
    MetadataElement(name="reverseCol", desc="Optional reverse read column", param=metadata.ColumnParameter, optional=True, no_value=0)
    MetadataElement(name="columns", default=3, desc="Number of columns", readonly=True, visible=False)

    def get_track_resolution(self, dataset, start, end):
        range = end - start
        # Determine appropriate resolution to plot ~1000 points
        resolution = math.ceil(10 ** math.ceil(math.log10(range / 1000)))
        # Restrict to valid range
        resolution = min(resolution, 10000)
        resolution = max(resolution, 1)
        return resolution
