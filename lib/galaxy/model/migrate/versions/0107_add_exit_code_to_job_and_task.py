"""
Add the exit_code column to the Job and Task tables.
"""
from __future__ import print_function

import logging

from sqlalchemy import Column, Integer, MetaData, Table

log = logging.getLogger(__name__)
metadata = MetaData()

# There was a bug when only one column was used for both tables,
# so create separate columns.
exit_code_job_col = Column("exit_code", Integer, nullable=True)
exit_code_task_col = Column("exit_code", Integer, nullable=True)


def upgrade(migrate_engine):
    print(__doc__)
    metadata.bind = migrate_engine
    metadata.reflect()

    # Add the exit_code column to the Job table.
    try:
        job_table = Table("job", metadata, autoload=True)
        exit_code_job_col.create(job_table)
        assert exit_code_job_col is job_table.c.exit_code
    except Exception:
        log.exception("Adding column 'exit_code' to job table failed.")

    # Add the exit_code column to the Task table.
    try:
        task_table = Table("task", metadata, autoload=True)
        exit_code_task_col.create(task_table)
        assert exit_code_task_col is task_table.c.exit_code
    except Exception:
        log.exception("Adding column 'exit_code' to task table failed.")


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()

    # Drop the Job table's exit_code column.
    try:
        job_table = Table("job", metadata, autoload=True)
        exit_code_col = job_table.c.exit_code
        exit_code_col.drop()
    except Exception:
        log.exception("Dropping 'exit_code' column from job table failed.")

    # Drop the Job table's exit_code column.
    try:
        task_table = Table("task", metadata, autoload=True)
        exit_code_col = task_table.c.exit_code
        exit_code_col.drop()
    except Exception:
        log.exception("Dropping 'exit_code' column from task table failed.")
