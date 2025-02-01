import json

class Action:
    def __init__(self, symbol, month_year):
        self.symbol = symbol
        self.month_year = month_year  # Format 'YYYY-MM'

    def to_json(self):
        return json.dumps({
            'symbol': self.symbol,
            'month_year': self.month_year
        })
