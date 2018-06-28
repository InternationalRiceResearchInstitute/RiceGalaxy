"""
Migration script to modify the 'file_path' field type in 'sample_dataset' table
to 'TEXT' so that it can support large file paths exceeding 255 characters
"""
from __future__ import print_function

import logging

from sqlalchemy import Column, MetaData, Table, TEXT
from sqlalchemy.exc import NoSuchTableError

log = logging.getLogger(__name__)
metadata = MetaData()


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print(__doc__)
    metadata.reflect()
    try:
        SampleDataset_table = Table("sample_dataset", metadata, autoload=True)
    except NoSuchTableError:
        SampleDataset_table = None
        log.debug("Failed loading table 'sample_dataset'")

    if SampleDataset_table is not None:
        cmd = "SELECT id, file_path FROM sample_dataset"
        result = migrate_engine.execute(cmd)
        filepath_dict = {}
        for r in result:
            id = int(r[0])
            filepath_dict[id] = r[1]
        # remove the 'file_path' column
        try:
            SampleDataset_table.c.file_path.drop()
        except Exception:
            log.exception("Deleting column 'file_path' from the 'sample_dataset' table failed.")
        # create the column again
        try:
            col = Column("file_path", TEXT)
            col.create(SampleDataset_table)
            assert col is SampleDataset_table.c.file_path
        except Exception:
            log.exception("Creating column 'file_path' in the 'sample_dataset' table failed.")

        for id, file_path in filepath_dict.items():
            cmd = "update sample_dataset set file_path='%s' where id=%i" % (file_path, id)
            migrate_engine.execute(cmd)


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    pass
