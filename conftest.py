from collections.abc import Iterator
import freezegun
import mwapi  # type: ignore
import os
import pymysql
import pytest
import random
import re
import string
from typing import Any


@pytest.fixture
def frozen_time() -> Iterator[Any]:
    with freezegun.freeze_time() as frozen_time:
        yield frozen_time


@pytest.fixture
def internet_connection() -> Iterator[None]:
    """No-value fixture to skip tests if no internet connection is available."""
    try:
        yield
    except mwapi.errors.ConnectionError:
        pytest.skip('no internet connection')


@pytest.fixture(scope="module")
def fresh_database_connection_params() -> Iterator[dict]:
    if 'MARIADB_ROOT_PASSWORD' not in os.environ:
        pytest.skip('MariaDB credentials not provided')
    host = os.environ.get('MARIADB_HOST', 'localhost')
    port = int(os.environ.get('MARIADB_PORT', 0))
    connection = pymysql.connect(host=host,
                                 port=port,
                                 user='root',
                                 password=os.environ['MARIADB_ROOT_PASSWORD'])
    database_name = 'quickcategories_test_' + ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(16))
    user_name = 'quickcategories_test_user_' + ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(16))
    user_password = 'quickcategories_test_password_' + ''.join(random.choice(string.ascii_lowercase + string.digits) for i in range(16))
    try:
        with connection.cursor() as cursor:
            cursor.execute('CREATE DATABASE `%s`' % database_name)
            cursor.execute('GRANT ALL PRIVILEGES ON `%s`.* TO `%s` IDENTIFIED BY %%s' % (database_name, user_name), (user_password,))
            cursor.execute('USE `%s`' % database_name)
            with open('tables.sql') as tables:
                queries = tables.read()
                # PyMySQL does not support multiple queries in execute(), so we have to split
                for query in queries.split(';'):
                    query = query.strip()
                    if query:
                        cursor.execute(query)
        connection.commit()
        yield {'host': host, 'port': port, 'user': user_name, 'password': user_password, 'db': database_name}
    finally:
        with connection.cursor() as cursor:
            cursor.execute('DROP DATABASE IF EXISTS `%s`' % database_name)
            cursor.execute('DROP USER IF EXISTS `%s`' % user_name)
            connection.commit()
        connection.close()


@pytest.fixture
def database_connection_params(fresh_database_connection_params: dict) -> Iterator[dict]:
    connection = pymysql.connect(**fresh_database_connection_params)
    try:
        with open('tables.sql') as tables:
            queries = tables.read()
        with connection.cursor() as cursor:
            for table in re.findall(r'CREATE TABLE ([^ ]+) ', queries):
                cursor.execute('DELETE FROM `%s`' % table)  # more efficient than TRUNCATE TABLE on my system :/
                # cursor.execute('ALTER TABLE `%s` AUTO_INCREMENT = 1' % table)  # currently not necessary
        connection.commit()
    finally:
        connection.close()
    yield fresh_database_connection_params
