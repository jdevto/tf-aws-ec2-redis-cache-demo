"""
Lua scripts for atomic Redis operations.
"""
from typing import Dict, Optional

# Script to add or update cart item with validation
ADD_ITEM_SCRIPT = """
local cart_key = KEYS[1]
local product_id = ARGV[1]
local quantity = tonumber(ARGV[2])
local price_snapshot = ARGV[3]
local variant = ARGV[4]
local max_items = tonumber(ARGV[5])
local max_quantity = tonumber(ARGV[6])
local ttl = tonumber(ARGV[7])

-- Get current cart item count
local item_count = redis.call('HLEN', cart_key)

-- Get existing quantity for this product
local existing_item = redis.call('HGET', cart_key, product_id)
local existing_qty = 0
if existing_item then
    local existing_data = cjson.decode(existing_item)
    existing_qty = tonumber(existing_data['quantity']) or 0
end

-- Calculate new quantity
local new_qty = existing_qty + quantity

-- Validate max quantity per item
if new_qty > max_quantity then
    return {err = 'MAX_QUANTITY_EXCEEDED', max = max_quantity, requested = new_qty}
end

-- Validate max items per cart (only if adding new item)
if existing_qty == 0 and item_count >= max_items then
    return {err = 'MAX_ITEMS_EXCEEDED', max = max_items, current = item_count}
end

-- Create/update item data
local item_data = {
    quantity = new_qty,
    price_snapshot = price_snapshot,
    variant = variant or ''
}

-- Set the item
redis.call('HSET', cart_key, product_id, cjson.encode(item_data))

-- Refresh TTL
redis.call('EXPIRE', cart_key, ttl)

-- Return result as table (not empty)
local result = {}
result['ok'] = true
result['quantity'] = new_qty
result['is_new'] = (existing_qty == 0)
return result
"""

# Script to update quantity with validation
UPDATE_QUANTITY_SCRIPT = """
local cart_key = KEYS[1]
local product_id = ARGV[1]
local quantity = tonumber(ARGV[2])
local max_quantity = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])

-- Get existing item
local existing_item = redis.call('HGET', cart_key, product_id)
if not existing_item then
    return {err = 'PRODUCT_NOT_FOUND'}
end

-- Validate quantity
if quantity < 0 then
    return {err = 'INVALID_QUANTITY', quantity = quantity}
end

if quantity > max_quantity then
    return {err = 'MAX_QUANTITY_EXCEEDED', max = max_quantity, requested = quantity}
end

-- Parse existing data
local existing_data = cjson.decode(existing_item)
local price_snapshot = existing_data['price_snapshot']
local variant = existing_data['variant'] or ''

if quantity == 0 then
    -- Remove item if quantity is 0
    redis.call('HDEL', cart_key, product_id)
    local item_count = redis.call('HLEN', cart_key)
    if item_count > 0 then
        redis.call('EXPIRE', cart_key, ttl)
    else
        -- Delete cart if empty
        redis.call('DEL', cart_key)
    end
    return {ok = true, quantity = 0, removed = true}
else
    -- Update item
    local item_data = {
        quantity = quantity,
        price_snapshot = price_snapshot,
        variant = variant
    }
    redis.call('HSET', cart_key, product_id, cjson.encode(item_data))
    redis.call('EXPIRE', cart_key, ttl)
    return {ok = true, quantity = quantity, removed = false}
end
"""

# Script to merge carts with conflict resolution
MERGE_CART_SCRIPT = """
local source_key = KEYS[1]
local target_key = KEYS[2]
local conflict_resolution = ARGV[1] or 'sum'
local ttl = tonumber(ARGV[2])

-- Get source cart items
local source_items = redis.call('HGETALL', source_key)
if #source_items == 0 then
    return {ok = true, merged = 0, message = 'Source cart is empty'}
end

-- Get target cart items
local target_items = redis.call('HGETALL', target_key)
local target_map = {}
for i = 1, #target_items, 2 do
    local product_id = target_items[i]
    local item_data = cjson.decode(target_items[i + 1])
    target_map[product_id] = item_data
end

local merged_count = 0
local conflict_count = 0

-- Merge items from source to target
for i = 1, #source_items, 2 do
    local product_id = source_items[i]
    local source_data = cjson.decode(source_items[i + 1])
    local source_qty = tonumber(source_data['quantity']) or 0

    if target_map[product_id] then
        -- Conflict: product exists in both carts
        conflict_count = conflict_count + 1
        local target_qty = tonumber(target_map[product_id]['quantity']) or 0

        if conflict_resolution == 'sum' then
            -- Sum quantities
            local new_qty = source_qty + target_qty
            local item_data = {
                quantity = new_qty,
                price_snapshot = source_data['price_snapshot'],  -- Use source price
                variant = source_data['variant'] or ''
            }
            redis.call('HSET', target_key, product_id, cjson.encode(item_data))
        else
            -- Last write wins (use source data)
            redis.call('HSET', target_key, product_id, source_items[i + 1])
        end
        merged_count = merged_count + 1
    else
        -- No conflict: add new item
        redis.call('HSET', target_key, product_id, source_items[i + 1])
        merged_count = merged_count + 1
    end
end

-- Refresh TTL on target cart
if redis.call('EXISTS', target_key) == 1 then
    redis.call('EXPIRE', target_key, ttl)
end

-- Delete source cart after merge
redis.call('DEL', source_key)

return {
    ok = true,
    merged = merged_count,
    conflicts = conflict_count,
    resolution = conflict_resolution
}
"""

class AtomicScripts:
    """Container for Lua scripts with caching"""

    def __init__(self, redis_wrapper):
        """
        Initialize with RedisClient wrapper (not raw redis.Redis client)
        This ensures we use the wrapper's retry logic and error handling
        """
        self.redis_wrapper = redis_wrapper
        self._scripts: Dict[str, Optional[str]] = {
            "add_item": None,
            "update_quantity": None,
            "merge_cart": None
        }
        self._register_scripts()

    def _register_scripts(self):
        """Register Lua scripts with Redis"""
        try:
            # Use raw client for script registration
            self._scripts["add_item"] = self.redis_wrapper.client.register_script(ADD_ITEM_SCRIPT)
            self._scripts["update_quantity"] = self.redis_wrapper.client.register_script(UPDATE_QUANTITY_SCRIPT)
            self._scripts["merge_cart"] = self.redis_wrapper.client.register_script(MERGE_CART_SCRIPT)
        except Exception as e:
            print(f"Warning: Could not register Lua scripts: {e}")
            # Scripts will be evaluated directly if registration fails

    def add_item(
        self,
        cart_key: str,
        product_id: str,
        quantity: int,
        price_snapshot: str,
        variant: Optional[str],
        max_items: int,
        max_quantity: int,
        ttl: int
    ):
        """Execute add item script"""
        # Use wrapper's eval method which has retry logic and proper error handling
        # This is more reliable than using raw client or registered scripts
        return self.redis_wrapper.eval(
            ADD_ITEM_SCRIPT,
            1,
            cart_key,
            product_id,
            str(quantity),
            str(price_snapshot),
            variant or "",
            str(max_items),
            str(max_quantity),
            str(ttl)
        )

    def update_quantity(
        self,
        cart_key: str,
        product_id: str,
        quantity: int,
        max_quantity: int,
        ttl: int
    ):
        """Execute update quantity script"""
        return self.redis_wrapper.eval(
            UPDATE_QUANTITY_SCRIPT,
            1,
            cart_key,
            product_id,
            str(quantity),
            str(max_quantity),
            str(ttl)
        )

    def merge_cart(
        self,
        source_key: str,
        target_key: str,
        conflict_resolution: str,
        ttl: int
    ):
        """Execute merge cart script"""
        return self.redis_wrapper.eval(
            MERGE_CART_SCRIPT,
            2,
            source_key,
            target_key,
            conflict_resolution,
            str(ttl)
        )
