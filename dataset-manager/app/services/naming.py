"""
Shared Cassandra naming helpers.

`dataset_table_name` was duplicated independently in DatasetService and
BatchService (Normal #11 in docs/code_review1.md) — a naming-scheme change
had to be made in both or the two services would disagree on which physical
table to touch. One helper now, used by both.
"""

from uuid import UUID


def dataset_table_name(dataset_id: UUID) -> str:
    """Generate the per-dataset row-storage table name from a dataset ID.

    Cassandra table names must be alphanumeric/underscore; UUIDs are safe
    once hyphens are replaced.
    """
    return f"ds_rows_{str(dataset_id).replace('-', '_')}"
