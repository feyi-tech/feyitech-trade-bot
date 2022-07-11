'''
{
    "symbol": "BTCUSDT",
    "pair": "BTCUSDT",
    "contractType": "PERPETUAL",
    "deliveryDate": 4133404800000,
    "onboardDate": 1569398400000,
    "status": "TRADING",
    "maintMarginPercent": "2.5000",
    "requiredMarginPercent": "5.0000",
    "baseAsset": "BTC", # Note
    "quoteAsset": "USDT", # Note
    "marginAsset": "USDT", # Note
    "pricePrecision": 2, # Note
    "quantityPrecision": 3, # Note
    "baseAssetPrecision": 8, # Note
    "quotePrecision": 8, # Note
    ...
}
'''

class SymbolInfo:

    def __init__(self,
    name, type, status, is_futures, requiredMarginPercent, baseAsset, quoteAsset, marginAsset, 
    pricePrecision, quantityPrecision, baseAssetPrecision, quotePrecision
    ):
        self.name = name
        self.type = type
        self.status = status,
        self.is_futures = is_futures
        self.requiredMarginPercent = requiredMarginPercent
        self.baseAsset = baseAsset
        self.quoteAsset = quoteAsset
        self.marginAsset = marginAsset
        self.pricePrecision = pricePrecision
        self.quantityPrecision = quantityPrecision
        self.baseAssetPrecision = baseAssetPrecision
        self.quotePrecision = quotePrecision
    
    def from_dict(dict):
        name = dict['symbol']
        is_futures = 'contractType' in dict
        status = dict['status'],
        requiredMarginPercent = None if 'requiredMarginPercent' not in dict else dict['requiredMarginPercent']
        baseAsset = None if 'baseAsset' not in dict else dict['baseAsset']
        quoteAsset = None if 'quoteAsset' not in dict else dict['quoteAsset']
        marginAsset = None if 'marginAsset' not in dict else dict['marginAsset']
        pricePrecision = None if 'pricePrecision' not in dict else dict['pricePrecision']
        quantityPrecision = None if 'quantityPrecision' not in dict else dict['quantityPrecision']
        baseAssetPrecision = None if 'baseAssetPrecision' not in dict else dict['baseAssetPrecision']
        quotePrecision = None if 'quotePrecision' not in dict else dict['quotePrecision']

        return SymbolInfo(
            name=name, type=type, status=status, is_futures=is_futures, requiredMarginPercent=requiredMarginPercent, 
            baseAsset=baseAsset, quoteAsset=quoteAsset, marginAsset=marginAsset, 
            pricePrecision=pricePrecision, quantityPrecision=quantityPrecision, 
            baseAssetPrecision=baseAssetPrecision, quotePrecision=quotePrecision
        )
        

