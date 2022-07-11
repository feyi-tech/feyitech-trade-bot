

import sqlalchemy
from utils.constants import Constants


def filelog(filepath, content):
    with open(filepath, 'a+') as f:
        f.write(content)


def chartlog(chart):
    db = sqlalchemy.create_engine(f'sqlite:///{Constants.log_dir_name}/{Constants.chart_log_db_filename}')
    chart.to_sql(Constants.chart_log_table_name, db, if_exists='replace', index=False)