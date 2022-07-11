import logging
import click
from loguru import logger
from bot import TradeBot
from utils.config import Config
from utils.generic import InterceptHandler

logging.getLogger("apscheduler.executors.default").setLevel("WARNING")
logging.basicConfig(handlers=[InterceptHandler()], level=0)

@click.command()
@click.argument('config_file', required=False, default='user_data/config.yml')
def main(config_file: str) -> None:
    try:
        bot = TradeBot(config=Config)
        bot.start()
    finally:
        logger.info('Bye!')


if __name__ == '__main__':
    main()