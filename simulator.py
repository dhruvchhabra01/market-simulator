import os
import collections
import random
import asyncio
from contextlib import AsyncExitStack

import pandas as pd
import matplotlib.pyplot as plt

from google.antigravity import Agent, LocalAgentConfig


class LimitOrderBook:
    """Central Limit Order Book using dict → deque mapping for O(1) queue ops."""

    def __init__(self):
        # price → deque of orders (FIFO at each level)
        self.bids = collections.defaultdict(collections.deque)
        self.asks = collections.defaultdict(collections.deque)
        self.best_bid = None
        self.best_ask = None
        self.trade_history = collections.deque(maxlen=3)

    def _update_best_bid(self):
        valid = [p for p, q in self.bids.items() if q]
        self.best_bid = max(valid) if valid else None

    def _update_best_ask(self):
        valid = [p for p, q in self.asks.items() if q]
        self.best_ask = min(valid) if valid else None

    def submit_order(self, agent_id, side, price, quantity):
        order = {'agent_id': agent_id, 'price': price, 'quantity': quantity}
        remaining = quantity

        if side == 'buy':
            # buy crosses spread when price >= cheapest seller
            while remaining > 0 and self.best_ask is not None and price >= self.best_ask:
                queue = self.asks[self.best_ask]
                while remaining > 0 and queue:
                    resting = queue[0]
                    fill = min(remaining, resting['quantity'])
                    trade_price = self.best_ask

                    print(f"*** TRADE: {fill} shares @ ${trade_price} "
                          f"| {agent_id} buys from {resting['agent_id']} ***")
                    self.trade_history.append({
                        'price': trade_price, 'quantity': fill,
                        'buyer': agent_id, 'seller': resting['agent_id']
                    })

                    remaining -= fill
                    resting['quantity'] -= fill
                    if resting['quantity'] == 0:
                        queue.popleft()

                if not queue:
                    del self.asks[self.best_ask]
                    self._update_best_ask()

            if remaining > 0:
                order['quantity'] = remaining
                self.bids[price].append(order)
                if self.best_bid is None or price > self.best_bid:
                    self.best_bid = price

        elif side == 'sell':
            # sell crosses spread when price <= highest buyer
            while remaining > 0 and self.best_bid is not None and price <= self.best_bid:
                queue = self.bids[self.best_bid]
                while remaining > 0 and queue:
                    resting = queue[0]
                    fill = min(remaining, resting['quantity'])
                    trade_price = self.best_bid

                    print(f"*** TRADE: {fill} shares @ ${trade_price} "
                          f"| {resting['agent_id']} buys from {agent_id} ***")
                    self.trade_history.append({
                        'price': trade_price, 'quantity': fill,
                        'buyer': resting['agent_id'], 'seller': agent_id
                    })

                    remaining -= fill
                    resting['quantity'] -= fill
                    if resting['quantity'] == 0:
                        queue.popleft()

                if not queue:
                    del self.bids[self.best_bid]
                    self._update_best_bid()

            if remaining > 0:
                order['quantity'] = remaining
                self.asks[price].append(order)
                if self.best_ask is None or price < self.best_ask:
                    self.best_ask = price

    def get_market_state(self):
        mid = None
        if self.best_bid is not None and self.best_ask is not None:
            mid = (self.best_bid + self.best_ask) / 2.0
        return {
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "mid_price": mid,
            "last_trades": list(self.trade_history)
        }


# -- agent tools --------------------------------------------------------

def make_tools(market, agent_id):
    """Build the view_market and place_order tools for a given agent."""

    def view_market() -> dict:
        """Returns best bid, best ask, mid-price, and recent trades."""
        return market.get_market_state()

    def place_order(side: str, price: float, quantity: int) -> str:
        """Places a limit order in the market.

        Args:
            side: 'buy' or 'sell'
            price: The limit price
            quantity: Number of shares
        """
        market.submit_order(agent_id, side, float(price), int(quantity))
        return f"Order placed: {side} {quantity} @ ${price}"

    return [view_market, place_order]


# -- agent prompts -------------------------------------------------------

PROMPTS = {
    "MarketMaker": (
        "You are a Market Maker. Provide liquidity on both sides of the spread. "
        "View the market, then place buy orders slightly below mid-price and sell "
        "orders slightly above it to capture the spread. You should usually place "
        "orders, but may pass if the spread is too tight to profit. "
        "Reply with your reasoning."
    ),
    "MomentumTrader": (
        "You are a Momentum Trader. View the market and analyze last_trades. "
        "If the most recent trade price is higher than the earliest, the price is "
        "rising — buy aggressively at or above the best_ask. If it is lower, sell "
        "aggressively at or below the best_bid. If the market is flat or there are "
        "no trades, you may pass. Trade 5-15 shares. Reply with your reasoning."
    ),
    "NoiseTrader": (
        "You are a Noise Trader simulating retail liquidity. View the market. "
        "You should usually trade. Sometimes place aggressive orders that cross "
        "the spread to trigger immediate execution; other times, place passive "
        "limit orders near the mid-price. Trade 1-20 shares. "
        "Reply with your reasoning."
    ),
}


# -- simulation loop -----------------------------------------------------

async def main():
    market = LimitOrderBook()

    # seed the book with resting liquidity
    print("Seeding initial liquidity...\n")
    market.submit_order("Init", "buy",  95.0, 100)
    market.submit_order("Init", "buy",  98.0, 100)
    market.submit_order("Init", "sell", 102.0, 100)
    market.submit_order("Init", "sell", 105.0, 100)

    # kick off a couple of crossing trades so agents have trade history
    market.submit_order("Seed", "buy",  102.0, 5)
    market.submit_order("Seed", "sell",  98.0, 3)

    # configure agents
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit(
            "Set GEMINI_API_KEY first.\n"
            "  export GEMINI_API_KEY='your-key-here'\n"
            "Get one free at https://aistudio.google.com/app/api-keys"
        )

    model = "gemini-3.5-flash-lite"
    configs = {
        name: LocalAgentConfig(
            model=model,
            api_key=api_key,
            system_instructions=prompt,
            tools=make_tools(market, name),
        )
        for name, prompt in PROMPTS.items()
    }

    tick_data = []
    num_ticks = 15
    delay = 15          # seconds between ticks (free-tier: 15 req/min)
    max_retries = 3

    async with AsyncExitStack() as stack:
        agents = {}
        for name, cfg in configs.items():
            agents[name] = await stack.enter_async_context(Agent(cfg))

        names = list(agents.keys())
        print(f"\nRunning {num_ticks} ticks (with {delay}s cooldown between each)\n")

        for tick in range(1, num_ticks + 1):
            chosen = random.choice(names)
            agent = agents[chosen]
            print(f"--- tick {tick}/{num_ticks}  [{chosen}] ---")

            msg = ("It is your turn. Use view_market() to observe the state, "
                   "then place_order() if you want to trade. Otherwise say 'I pass'.")

            ok = False
            for attempt in range(1, max_retries + 1):
                try:
                    resp = await agent.chat(msg)
                    print(f"  {chosen}: {await resp.text()}")
                    ok = True
                    break
                except Exception as e:
                    err = str(e)
                    if "429" in err or "quota" in err.lower():
                        wait = 60 * attempt
                        print(f"  rate-limited, waiting {wait}s (attempt {attempt})...")
                        await asyncio.sleep(wait)
                    elif "503" in err:
                        wait = 30 * attempt
                        print(f"  server busy, waiting {wait}s (attempt {attempt})...")
                        await asyncio.sleep(wait)
                    else:
                        print(f"  error: {err}")
                        break

            if not ok:
                print(f"  skipped tick {tick}")

            state = market.get_market_state()
            print(f"  bid={state['best_bid']}  ask={state['best_ask']}  mid={state['mid_price']}\n")
            tick_data.append({
                "Tick": tick,
                "Mid-Price": state["mid_price"],
                "Best Bid": state["best_bid"],
                "Best Ask": state["best_ask"],
            })

            if tick < num_ticks:
                await asyncio.sleep(delay)

    # -- plot results ----------------------------------------------------
    print("Generating chart...")
    df = pd.DataFrame(tick_data)
    df.ffill(inplace=True)
    df["Spread"] = df["Best Ask"] - df["Best Bid"]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    ax1.plot(df["Tick"], df["Mid-Price"], marker='o', color='tab:blue', label='Mid-Price')
    ax1.plot(df["Tick"], df["Best Bid"], '--', alpha=.5, color='tab:green', label='Best Bid')
    ax1.plot(df["Tick"], df["Best Ask"], '--', alpha=.5, color='tab:red', label='Best Ask')
    ax1.set_title("Price Evolution")
    ax1.set_ylabel("Price ($)")
    ax1.grid(True, ls=':', alpha=.6)
    ax1.legend()

    ax2.plot(df["Tick"], df["Spread"], marker='x', color='tab:purple', label='Spread')
    ax2.set_title("Bid-Ask Spread")
    ax2.set_xlabel("Tick")
    ax2.set_ylabel("Spread ($)")
    ax2.grid(True, ls=':', alpha=.6)
    ax2.legend()

    plt.tight_layout()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "market_simulation.png")
    plt.savefig(out)
    print(f"Saved to {out}")


if __name__ == "__main__":
    asyncio.run(main())
