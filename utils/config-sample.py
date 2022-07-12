
class Config:
    bot_name = 'FeyiTechTradeBot'
    personal_website= 'https://feyitech.com'
    company_website= 'https://softbaker.com'
    personal_email= 'hello@feyitech.com'
    company_email= 'hello@softbaker.com'
    phone_number= '+234-9024-500-275'
    twitter= 'https://twitter.com/feyi_tech'
    telegram= 'https://t.me/feyitech'
    is_test = True
    update_messages = False
    fetch_interval_seconds = 10
    max_leverage = 100
    max_positions_per_chart = 1000
    timeframe = '1m'
    timeframe_in_seconds = 60
    market_info_update_interval_seconds = 86400 # 1 day
    base_assets_whitelist = []
    base_assets_blacklist = []
    quote_assets_whitelist = ['USDT', 'BUSD']
    quote_assets_blacklist = []
    time_format = '%b, %d %Y - %I:%M:%S %p'
    # the percentage of users profits the bot takes as profit when users make profits
    bot_fee_profit_percentage = 0
    # the ERC20 address the bot's fee should be withdrawn to when users make profits
    bot_fee_profit_destination = None 
    class secrets:
        telegram_token = '' # enter your Telegram Bot token
        admin_chat_id = '' # enter your chat ID/user ID to prevent other users to use the bot
    class Binance:
        key = ""
        secret = ""