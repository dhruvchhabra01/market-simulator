class LimitOrderBook:
    """Simple limit order book with list-based price levels and partial fill support."""

    def __init__(self):
        self.bids = []
        self.asks = []
        self.trade_history = []

    def submit_order(self, agent_id, side, price, quantity):
        order = {'agent_id': agent_id, 'price': price, 'quantity': quantity}

        if side == 'buy':
            if self.asks and price >= min(ask['price'] for ask in self.asks):
                self.execute_trade(order, side)
            else:
                self.bids.append(order)
                print(f"[{agent_id}] placed BUY order for {quantity} @ ${price}")

        elif side == 'sell':
            if self.bids and price <= max(bid['price'] for bid in self.bids):
                self.execute_trade(order, side)
            else:
                self.asks.append(order)
                print(f"[{agent_id}] placed SELL order for {quantity} @ ${price}")

    def execute_trade(self, incoming_order, side):
        """Match incoming order against resting orders. Handles partial fills
        and trades at the resting (maker) order's price."""
        remaining_qty = incoming_order['quantity']

        if side == 'buy':
            self.asks.sort(key=lambda o: o['price'])
            resting_orders = self.asks
        else:
            self.bids.sort(key=lambda o: o['price'], reverse=True)
            resting_orders = self.bids

        i = 0
        while remaining_qty > 0 and i < len(resting_orders):
            resting = resting_orders[i]

            if side == 'buy' and incoming_order['price'] < resting['price']:
                break
            if side == 'sell' and incoming_order['price'] > resting['price']:
                break

            fill_qty = min(remaining_qty, resting['quantity'])
            fill_price = resting['price']

            print(
                f"*** TRADE EXECUTED: {fill_qty} shares @ ${fill_price} "
                f"| buyer: {'incoming' if side == 'buy' else resting['agent_id']} "
                f"| seller: {'incoming' if side == 'sell' else resting['agent_id']} ***"
            )

            self.trade_history.append({
                'price': fill_price,
                'quantity': fill_qty,
                'buyer': incoming_order['agent_id'] if side == 'buy' else resting['agent_id'],
                'seller': incoming_order['agent_id'] if side == 'sell' else resting['agent_id'],
            })

            remaining_qty -= fill_qty
            resting['quantity'] -= fill_qty

            if resting['quantity'] == 0:
                resting_orders.pop(i)
            else:
                i += 1

        # leftover quantity rests in the book
        if remaining_qty > 0:
            leftover = {
                'agent_id': incoming_order['agent_id'],
                'price': incoming_order['price'],
                'quantity': remaining_qty,
            }
            if side == 'buy':
                self.bids.append(leftover)
                print(f"[{incoming_order['agent_id']}] BUY partially filled — "
                      f"{remaining_qty} remaining @ ${incoming_order['price']}")
            else:
                self.asks.append(leftover)
                print(f"[{incoming_order['agent_id']}] SELL partially filled — "
                      f"{remaining_qty} remaining @ ${incoming_order['price']}")

    def get_market_state(self):
        best_bid = max(b['price'] for b in self.bids) if self.bids else None
        best_ask = min(a['price'] for a in self.asks) if self.asks else None

        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "last_trades": self.trade_history[-3:],
        }