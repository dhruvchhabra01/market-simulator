# Agent-Based Market Microstructure Simulator

A simplified limit order book simulator where autonomous LLM-powered agents trade against each other. Built to explore how market microstructure, order matching, and agent-based modeling work together.

## What it does

The simulator creates a central limit order book (CLOB) and drops three AI agents into it, each with a different trading personality:

- **Market Maker** — quotes on both sides of the spread to earn the bid-ask difference
- **Momentum Trader** — reads recent trade history and chases the trend
- **Noise Trader** — simulates retail flow with random-ish orders, sometimes crossing the spread

Each "tick" of the simulation, one agent is randomly selected. It inspects the current market state (best bid, best ask, recent trades) and decides whether to place an order. If orders cross the spread, trades execute immediately with partial fill support. After all ticks complete, the price and spread data is plotted.

## Project structure

```
├── order_book.py      # standalone LOB with partial fills (no dependencies)
├── main.py            # quick manual test — Alice, Bob, Charlie
├── simulator.py       # full simulation with AI agents + visualization
├── requirements.txt
└── .gitignore
```

- **`order_book.py`** is a self-contained order book you can import and use anywhere. It uses plain Python lists.
- **`simulator.py`** contains a second, more optimized LOB implementation using `collections.deque` for O(1) queue operations, plus all the agent orchestration and charting logic.
- **`main.py`** is a minimal script to test the order book manually without needing an API key.

## Setup

```bash
pip install -r requirements.txt
```

You'll need a Gemini API key for the agent simulation (free at [Google AI Studio](https://aistudio.google.com/app/api-keys)):

```bash
export GEMINI_API_KEY='your-key-here'
```

## Running

**Manual order book test** (no API key needed):
```bash
python main.py
```

**Full agent simulation**:
```bash
python simulator.py
```

The simulation runs 15 ticks with a cooldown between each to stay within free-tier rate limits (~5 min total). It saves a `market_simulation.png` chart at the end.

## How the order book works

1. An incoming order checks if it can match against the opposite side (buy vs. existing sells, or vice versa).
2. If the incoming price crosses the spread, the matching engine walks through resting orders at the best price, filling as much quantity as possible.
3. Partial fills are handled — if you buy 5 shares but the cheapest seller only has 3, those 3 trade and your remaining 2 keep matching or rest in the book.
4. Trades always execute at the resting (maker) order's price.

## Output

The simulation prints each agent's reasoning and trading decisions to the terminal, then generates a two-panel chart:

- **Top panel**: Mid-price, best bid, and best ask over time
- **Bottom panel**: Bid-ask spread over time