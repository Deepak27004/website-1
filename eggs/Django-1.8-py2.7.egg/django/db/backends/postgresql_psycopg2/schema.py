import psycopg2

from django.db.backends.base.schema import BaseDatabaseSchemaEditor


class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):

    sql_create_sequence = "CREATE SEQUENCE %(sequence)s"
    sql_delete_sequence = "DROP SEQUENCE IF EXISTS %(sequence)s CASCADE"
    sql_set_sequence_max = "SELECT setval('%(sequence)s', MAX(%(column)s)) FROM %(table)s"
    sql_create_varchar_index = "CREATE INDEX %(name)s ON %(table)s (%(columns)s varchar_pattern_ops)%(extra)s"
    sql_create_text_index = "CREATE INDEX %(name)s ON %(table)s (%(columns)s text_pattern_ops)%(extra)s"

    def quote_value(self, value):
        return psycopg2.extensions.adapt(value)

    def _model_indexes_sql(self, model):
        output = super(DatabaseSchemaEditor, self)._model_indexes_sql(model)
        if not model._meta.managed or model._meta.proxy or model._meta.swapped:
            return output

        for field in model._meta.local_fields:
            db_type = field.db_type(connection=self.connection)
            if db_type is not None and (field.db_index or field.unique):
                # Fields with database column types of `varchar` and `text` need
                # a second index that specifies their operator class, which is
                # needed when performing correct LIKE queries outside the
                # C locale. See #12234.
                if db_type.startswith('varchar'):
                    output.append(
                        self._create_index_sql(
                            model,
                            [field],
                            suffix='_like',
                            sql=self.sql_create_varchar_index))
                elif db_type.startswith('text'):
                    output.append(
                        self._create_index_sql(
                            model,
                            [field],
                            suffix='_like',
                            sql=self.sql_create_text_index))
        return output

    def _alter_column_type_sql(self, table, column, type):
        """
        Makes ALTER TYPE with SERIAL make sense.
        """
        if type.lower() == "serial":
            sequence_name = "%s_%s_seq" % (table, column)
            return (
                (
                    self.sql_alter_column_type % {
                        "column": self.quote_name(column),
                        "type": "integer",
                    },
                    [],
                ),
                [
                    (
                        self.sql_delete_sequence % {
                            "sequence": sequence_name,
                        },
                        [],
                    ),
                    (
                        self.sql_create_sequence % {
                            "sequence": sequence_name,
                        },
                        [],
                    ),
                    (
                        self.sql_alter_column % {
                            "table": table,
                            "changes": self.sql_alter_column_default % {
                                "column": column,
                                "default": "nextval('%s')" % sequence_name,
                            }
                        },
                        [],
                    ),
                    (
                        self.sql_set_sequence_max % {
                            "table": table,
                            "column": column,
                            "sequence": sequence_name,
                        },
                        [],
                    ),
                ],
            )
        else:
            return super(
                DatabaseSchemaEditor,
                self)._alter_column_type_sql(
                table,
                column,
                type)
