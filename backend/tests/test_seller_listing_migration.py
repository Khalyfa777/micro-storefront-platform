from contextlib import contextmanager
from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "a7c9e2f4b6d8_add_seller_listing_indexes.py"
)


def load_migration():
    spec = spec_from_file_location(
        "seller_listing_index_migration",
        MIGRATION_PATH,
    )

    assert spec is not None
    assert spec.loader is not None

    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


class FakeContext:
    def __init__(self):
        self.autocommit_entries = 0

    @contextmanager
    def autocommit_block(self):
        self.autocommit_entries += 1
        yield


class FakeOp:
    def __init__(self):
        self.context = FakeContext()
        self.statements: list[str] = []

    def get_context(self):
        return self.context

    def execute(self, statement: str):
        self.statements.append(
            " ".join(statement.split())
        )


def test_upgrade_creates_all_indexes_concurrently():
    migration = load_migration()
    fake_op = FakeOp()
    migration.op = fake_op

    migration.upgrade()

    assert fake_op.context.autocommit_entries == 1
    assert len(fake_op.statements) == 3

    expected_names = {
        "ix_users_merchants_created_at_id_desc",
        "ix_stores_owner_created_at_id_desc",
        (
            "ix_seller_invitations_"
            "user_created_at_id_desc"
        ),
    }

    for statement in fake_op.statements:
        assert statement.startswith(
            "CREATE INDEX CONCURRENTLY "
        )

    for index_name in expected_names:
        assert any(
            index_name in statement
            for statement in fake_op.statements
        )


def test_downgrade_drops_all_indexes_concurrently():
    migration = load_migration()
    fake_op = FakeOp()
    migration.op = fake_op

    migration.downgrade()

    assert fake_op.context.autocommit_entries == 1
    assert len(fake_op.statements) == 3

    for statement in fake_op.statements:
        assert statement.startswith(
            "DROP INDEX CONCURRENTLY "
        )


def test_migration_chain_is_unchanged():
    migration = load_migration()

    assert migration.revision == "a7c9e2f4b6d8"
    assert (
        migration.down_revision
        == "d2a4c6e8f901"
    )