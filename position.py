from loguru import logger
from traderstatus import TraderStatus

class Position:
    TP = 'tp'
    SL = 'sl'

    def __init__(self, parent, open_price, open_time, volume, leverage, order_type, tp_sl_rate):
        self.parent = parent
        self.open_price = open_price
        self.open_time = open_time
        self.volume = volume
        self.leverage = leverage
        self.tp_sl_rate = tp_sl_rate
        self.order_type = order_type
        self.close_price = 0
        self.close_time = None
        self.profit = 0
        self.is_closed = False

        self.orderId = None
        self.clientOrderId = None
        self.orderFilled = False

        self.tpOrderId = None
        self.tpClientOrderId = None
        self.slOrderId = None
        self.slClientOrderId = None

        self.trigger_close_price = None
        self.update_tp_sl()

    def update_tp_sl(self):
        if self.order_type == 'buy':
            self.tp = self.parent.get_precise_price(self.open_price + self.tp_sl_rate)
            self.sl = self.parent.get_precise_price(self.open_price - self.tp_sl_rate)
        else:
            self.tp = self.parent.get_precise_price(self.open_price - self.tp_sl_rate)
            self.sl = self.parent.get_precise_price(self.open_price + self.tp_sl_rate)


    def update_profit(self):
        self.profit = (self.close_price - self.open_price) * self.volume if self.order_type == 'buy' \
                                                    else (self.open_price - self.close_price) * self.volume

    def close_position(self, action=None, trigger_close_price=None):
        if trigger_close_price is not None:
            self.trigger_close_price = trigger_close_price

        #current_price = float(self.parent.client.futures_mark_price(symbol=self.parent.symbol)['markPrice'])
        current_price = float(self.parent.client.futures_symbol_ticker(symbol=self.parent.symbol)['price'])
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

    def asdict(self):
        return {
            'open_price': self.open_price,
            'open_time': self.open_time,
            'trigger_close_price': self.trigger_close_price,
            'close_price': self.close_price,
            'close_time': self.close_time,
            'profit': self.profit,
            'is_closed': self.is_closed,
            'volume': self.volume,
            'leverage': self.leverage,
            'sl': self.sl,
            'tp': self.tp,
            'tp_sl_rate': self.tp_sl_rate,
            'order_type': self.order_type,
            'orderId': self.orderId,
            'clientOrderId': self.clientOrderId,
            'orderFilled:': self.orderFilled,
            'tpOrderId': self.tpOrderId,
            'tpClientOrderId': self.tpClientOrderId,
            'slOrderId': self.slOrderId,
            'slClientOrderId': self.slClientOrderId
        }