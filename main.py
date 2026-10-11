from order_book import LimitOrderBook

market = LimitOrderBook()

print("--- Market Opens ---")
market.submit_order(agent_id="Alice", side="buy", price=100.0, quantity=10)
market.submit_order(agent_id="Bob", side="sell", price=105.0, quantity=10)

print("\nCurrent Market State:")
print(market.get_market_state())

# Charlie sells at a price Alice is willing to pay → triggers a trade
print("\n--- Charlie Enters ---")
market.submit_order(agent_id="Charlie", side="sell", price=99.0, quantity=10)