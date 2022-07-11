
class Constants:
    accounts_db_name = 'accounts'
    settings_db_name = 'settings'
    trade_keys_separator = '|'
    log_dir_name = 'logs'
    chart_photos_dir_name = 'chart_photos'
    logo_filename = 'assets/logo.png'
    dev_logo_filename = 'assets/dev-logo.png'
    info_log_filename = 'info.txt'
    warning_log_filename = 'warning.txt'
    error_log_filename = 'error.txt'
    chart_log_db_filename = 'chart.db'
    chart_log_table_name = 'chart'
    log_text_nl = '\n--------------------------------\n\n'
    class TradeType:
        futures = 'futures'
        spot = 'spot'
    
    class Commands:
        start = 'start'
        status = 'status'
        addtrade = 'addtrade'
        updatetrade = 'updatetrade'
        removetrade = 'stoptrade'