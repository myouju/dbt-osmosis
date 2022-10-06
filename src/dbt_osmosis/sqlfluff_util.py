import logging
import os
from contextlib import closing
from pathlib import Path
from typing import Dict, Optional, Union

from sqlfluff.cli.commands import get_linter_and_formatter
from sqlfluff.cli.outputstream import FileOutput
from sqlfluff.core.config import ConfigLoader, FluffConfig


def get_config(
    dbt_project_root: Path,
    extra_config_path: Optional[Path] = None,
    ignore_local_config: bool = False,
    require_dialect: bool = True,
    **kwargs,
) -> FluffConfig:
    """Similar to the get_config() function used by SQLFluff command line.

    The main difference (an important one!) is that it loads configuration
    starting from the dbt_project_root, rather than the current working
    directory.
    """
    overrides = {k: kwargs[k] for k in kwargs if kwargs[k] is not None}
    loader = ConfigLoader.get_global()
    c = loader.load_config_up_to_path(
        path=str(dbt_project_root),
        extra_config_path=str(extra_config_path) if extra_config_path else None,
        ignore_local_config=ignore_local_config,
    )
    return FluffConfig(
        configs=c,
        extra_config_path=str(extra_config_path) if extra_config_path else None,
        ignore_local_config=ignore_local_config,
        overrides=overrides,
        require_dialect=require_dialect,
    )


def lint_command(
    project_root: Path,
    sql: Union[Path, str],
    extra_config_path: Optional[Path] = None,
    ignore_local_config: bool = False,
) -> Dict:
    """Lint specified file or SQL string.

    This is essentially a streamlined version of the SQLFluff command-line lint
    function, sqlfluff.cli.commands.lint().

    This function uses a few SQLFluff internals, but it should be relatively
    stable. The initial plan was to use the public API, but that was not
    behaving well initially. Small details about how SQLFluff handles .sqlfluff
    and dbt_project.yaml file locations and overrides generate lots of support
    questions, so it seems better to use this approach for now.

    Eventually, we can look at using SQLFluff's public, high-level APIs,
    but for now this should provide maximum compatibility with the command-line
    tool. We can also propose changes to SQLFluff to make this easier.
    """
    # TODO: Should get_config() be called one time only, when the dbt project
    # is registered?
    config = get_config(
        project_root, extra_config_path, ignore_local_config, require_dialect=False, nocolor=True
    )
    with closing(FileOutput(config, os.devnull)) as output_stream:
        lnt, formatter = get_linter_and_formatter(config, output_stream)

        if isinstance(sql, str):
            # Lint SQL passed in as a string
            result = lnt.lint_string_wrapped(sql)
        else:
            # Lint a SQL file
            result = lnt.lint_paths(
                tuple([str(sql)]),
                ignore_files=False,
            )
    records = result.as_records()
    assert len(records) == 1
    return records[0]


def test_lint_command():
    """Quick and dirty functional test for lint_command().

    Handy for seeing SQLFluff logs if something goes wrong. The automated tests
    make it difficult to see the logs.
    """
    logging.basicConfig(level=logging.INFO)
    from dbt_osmosis.core.server_v2 import app

    dbt = app.state.dbt_project_container
    dbt.add_project(
        name_override="dbt_project",
        project_dir="tests/sqlfluff_templater/fixtures/dbt/dbt_project",
        profiles_dir="tests/sqlfluff_templater/fixtures/dbt/profiles_yml",
        target="dev",
    )
    sql_path = Path(
        "tests/sqlfluff_templater/fixtures/dbt/dbt_project/models/my_new_project/issue_1608.sql"
    )
    result = lint_command(
        sql=sql_path,
        # sql=sql_path.read_text(),
        extra_config_path="tests/sqlfluff_templater/fixtures/dbt/dbt_project/.sqlfluff",
    )
    print(f"{'*'*40} Lint result {'*'*40}")
    print(result)
    print(f"{'*'*40} Lint result {'*'*40}")


if __name__ == "__main__":
    test_lint_command()
