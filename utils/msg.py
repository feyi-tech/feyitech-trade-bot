
from utils.config import Config
from utils.constants import Constants


class MSG:
    trade_exists_error = '⛔️ A trade with this symbol already exist. Cancel the trade first or edit it instead.'
    input_error = '⛔️ An input error occurred. Check your input and try again.'
    no_trade_info = f'ℹ️ You currently have no trade. \n\n To add a trade, use the <a href="/{Constants.Commands.addtrade}">/{Constants.Commands.addtrade}</a> command.'
    no_user_found = f'No User Found!'
    log_files = f'Below are the bot actions log files and database file:'
    about = f'Welcome to {Config.bot_name}!\n\n' \
            + 'This bot uses quantitative analysis to predict the market direction so you can hop on it for maximum profits.\n\n' \
            + 'Once a trade between two assets is added, The bot starts analysing the market quantitatively in the form of ADX indicator to detect a trend and how strong it is, 3 supertrends to detect the direction of the trend and reduce false positives, vwap to further reduce false positives, and finally order book bids and asks to peep into the future a little bit... yummy😋\n\n'\
            + "The kind of supertrend used is an improvised one I call volume weighted supertrend(VWS). It\'s very likely some individuals have also volumely🙄 improvised on supertrend before, since it looks tempting to do! If that's the case, I bet they've also increased their profits a bunch.\n\n"\
            + "The volumes and prices in the asks and bids of the market's order book are continually weighted, and comparisons are made between the corresponding weights of the asks and bids for a particular period of time. The results of these comparisons are further used to enhance the bot's trading decision.\n\n"\
            + "Risk management is at the core of this bot. It primarily base its risk management on stop loss(sl) and take profit(tp).\n"\
            + "The sl and tp are calculated based on how confident the bot is on its prediction.\n\n"\
            + "It also base its risk management on your margin/capital, which is always a percentage of your futures or spot wallet balance/PNL.\n\n"\
            + "This percentage used is the one you provide when you add a trade or update the settings of a trade. In a futures trade, you also contribute to the risk management by the leverage provided when you add a trade of update a trade's settings\n\n"\
            + "As you make profits and your wallet balance inceases in turn, the bot keeps trading on with the percentage of the margin/capital set. This means your margin/capital size increases overtime, and so your profits.\n\n"\
            +"This looks like a game changer? No. You still shouldn't sell all your goats and fowls to feed this bot into making you a billionaire. It works really great, but untill we can see the future clearly, You should stick to the risk management that works great for you."
    dev=f"I'm Feyijinmi Adegoke. I'm a software developer. I started learning to be one in 2013.\n\n"\
        + "My thirst to build something that could help me cook, do the launderies, dishes, peel melon seeds, cut ewedu leaves, and write my school notes back in secondary school got me interested in computers with the terminator movie.\n\n"\
        + "This sounds lazy, yes; or no... I'm not sure tbh. I just don't like repeating things. Repetitive tasks just bore me out. Why should you bore yourself with repetitions 365 <i>X</i> ? days when a computer will be willing to do it forever?🤔🤷‍♀️\n\n"\
        + "<b>If you have something you want me to work on for you or with you, contact me with the information below:</b>\n\n"\
        + f"<b>My Personal Website:</b> {Config.personal_website}\n"\
        + f"<b>My Company Website:</b> {Config.company_website}\n"\
        + f"<b>My Personal Email:</b> {Config.personal_email}\n"\
        + f"<b>My Company Email:</b> {Config.company_email}\n"\
        + f"<b>Phone Number:</b> {Config.phone_number}\n"\
        + f"<b>Telegram:</b> {Config.telegram}\n"\
        + f"<b>Twitter:</b> {Config.twitter}\n"