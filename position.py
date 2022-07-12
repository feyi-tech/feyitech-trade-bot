from loguru import logger
from utils.constants import Constants
from utils.trade_logger import filelog

class Position:
    TP = 'tp'
    SL = 'sl'

    def __init__(self, parent, entry_price, entry_time, volume, leverage, order_type, tp_sl_rate):
        self.parent = parent

        self.volume = volume
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.amount = 0
        self.mark_price = 0
        self.liq_price = 0
        self.leverage = leverage
        self.unrealised_profit = 0
        self.isolated_margin = 0
        self.isolated_wallet = 0
        self.notional = 0
        self.max_notional = 0
        self.margin_type = None

        self.tp = 0
        self.sl = 0

        self.trigger_exit_price = None
        self.exit_price = 0
        self.exit_time = None
        self.profit = 0
        self.is_closed = False

        self.orderId = None
        self.clientOrderId = None
        self.orderFilled = False

        self.tpOrderId = None
        self.tpClientOrderId = None
        self.slOrderId = None
        self.slClientOrderId = None

        
        self.tp_sl_rate = tp_sl_rate
        self.order_type = order_type
        self.update_tp_sl()

    def update_tp_sl(self):
        if self.order_type == 'buy':
            self.tp = self.parent.get_precise_price(self.entry_price + self.tp_sl_rate)
            self.sl = self.parent.get_precise_price(self.entry_price - self.tp_sl_rate)
        else:
            self.tp = self.parent.get_precise_price(self.entry_price - self.tp_sl_rate)
            self.sl = self.parent.get_precise_price(self.entry_price + self.tp_sl_rate)


    def update_profit(self):
        self.profit = (self.exit_price - self.entry_price) * self.volume if self.order_type == 'buy' \
                                                    else (self.entry_price - self.exit_price) * self.volume

    def close_position(self, action=None, trigger_exit_price=None):
        if trigger_exit_price is not None:
            self.trigger_exit_price = trigger_exit_price

        current_price = self.parent.get_current_price()
        change = (current_price * 0.5) / 100 # 0.5%

        price_up = self.parent.get_precise_price(current_price + change)
        price_down = self.parent.get_precise_price(current_price - change)

        action_validation = None
        if (current_price <= float(self.sl) and self.order_type == 'buy'):
            self.sl = price_down
            action_validation = Position.SL
        elif (current_price >= float(self.sl) and self.order_type == 'sell'):
            self.sl = price_up
            action_validation = Position.SL
        elif (current_price >= float(self.tp) and self.order_type == 'buy'):
            self.tp = price_up
            action_validation = Position.TP
        elif (current_price <= float(self.tp) and self.order_type == 'sell'):
            self.tp = price_down
            action_validation = Position.TP

        # action will be None if a panic close was called.
        # Example is when an uknown exception is thrown, the current position is closed
        # to avoid loss of profits due to possible failure of the bot to access data needed due to the error.

        # action will not be None when the last close triggers the take profit or stop loss
        # in case it is not None, we have to make sure the current price makes the same trigger 
        # before take profit and stop loss order is sent to the exchange
        if action is None or action == action_validation:
            self.parent.take_profit(self)
            self.parent.stop_loss(self)
        else:
            logger.warning(f'closeCalledFalsePositive: {self.asdict()}')
            filelog(
                f'{Constants.log_dir_name}/{Constants.warning_log_filename}', 
                f'--closeCalledFalsePositive--\n {self.asdict()}' + 
                Constants.log_text_nl
            )

    def asdict(self):
        return {
            'volume': self.volume,	
            'entry_price': self.entry_price,	
            'entry_time': self.entry_time,	
            'amount': self.amount,	
            'mark_price': self.mark_price,	
            'liq_price': self.liq_price,	
            'leverage': self.leverage,	
            'unrealised_profit': self.unrealised_profit,	
            'isolated_margin': self.isolated_margin,	
            'isolated_wallet': self.isolated_wallet,	
            'notional': self.notional,	
            'max_notional': self.max_notional,	
            'margin_type': self.margin_type,	

            'tp': self.tp,	
            'sl': self.sl,	

            'trigger_exit_price': self.trigger_exit_price,	
            'exit_price': self.exit_price,	
            'exit_time': self.exit_time,	
            'profit': self.profit,	
            'is_closed': self.is_closed,	

            'orderId': self.orderId,	
            'clientOrderId': self.clientOrderId,	
            'orderFilled': self.orderFilled,	

            'tpOrderId': self.tpOrderId,	
            'tpClientOrderId': self.tpClientOrderId,	
            'slOrderId': self.slOrderId,	
            'slClientOrderId': self.slClientOrderId,	

            
            'tp_sl_rate': self.tp_sl_rate,	
            'order_type': self.order_type,	
        }