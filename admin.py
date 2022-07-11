import pandas as pd
from utils.core import get_db
from utils.constants import Constants

user_db = get_db(Constants.accounts_db_name)
settings_db = get_db(Constants.settings_db_name)

def update_settings(
    use_trailing_sl_tp, weak_trend, strong_trend, very_strong_trend, extremely_strong_trend
):
    df = pd.DataFrame([use_trailing_sl_tp, weak_trend, strong_trend, very_strong_trend, extremely_strong_trend])
    df.to_sql(settings_db_name, settings_db, if_exists='replace', index=False)

def add_user(username, password, api_key, api_secret):
    df = pd.DataFrame([username, password, api_key, api_secret])

update_settings(
    True,
    2.0, 2.5, 3.0, 4.0
)