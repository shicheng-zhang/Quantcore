// Standalone unit test for the corrected LimitOrderBook.
// Build from project root:
//   g++ -std=c++20 -O2 -Wall -Wextra -o build/test_lob \
//       nexus/tests/test_lob.cpp -I nexus/include
#include "limit_order_book.h"

#include <cassert>
#include <cmath>
#include <iostream>

using namespace nexus;

static Event make_ev(Side side, double price, double qty) {
    Event ev{};
    ev.type = EventType::ORDER_BOOK_UPDATE;
    ev.timestamp_ns = 0;
    ev.order_id = 0;
    ev.side = side;
    ev.price = price;
    ev.quantity = qty;
    return ev;
}

int main() {
    // 1. Basic best bid / best ask.
    LimitOrderBook lob;
    lob.update(make_ev(Side::BUY, 100.0, 500));
    lob.update(make_ev(Side::BUY, 100.5, 300));
    lob.update(make_ev(Side::SELL, 101.5, 200));
    lob.update(make_ev(Side::SELL, 101.0, 400));
    assert(lob.get_best_bid() == 100.5);
    assert(lob.get_best_ask() == 101.0);

    // 2. Volume aggregates at a price; best does not move.
    lob.update(make_ev(Side::BUY, 100.5, 200));
    assert(lob.get_best_bid() == 100.5);

    // 3. Cancel the best bid -> best walks back.
    //    (Old code stayed at 100.5 forever.)
    lob.update(make_ev(Side::BUY, 100.5, 0));
    assert(lob.get_best_bid() == 100.0);

    // 4. Prices that collided under the old hash: 65000.00 and 65050.00
    //    both mapped to slot 0 of the old 5000-slot array.
    LimitOrderBook btc;
    btc.update(make_ev(Side::BUY, 65000.0, 100));
    btc.update(make_ev(Side::BUY, 65050.0, 100));
    btc.update(make_ev(Side::SELL, 65100.0, 100));
    assert(btc.get_best_bid() == 65050.0);
    btc.update(make_ev(Side::BUY, 65050.0, 0));
    assert(btc.get_best_bid() == 65000.0);

    // 5. Spread math: (101 - 99) / 99 * 10000 ~= 202.02 bps.
    LimitOrderBook spread_book;
    spread_book.update(make_ev(Side::BUY, 99.0, 100));
    spread_book.update(make_ev(Side::SELL, 101.0, 100));
    const double spread_bps = spread_book.get_spread_bps();
    assert(std::fabs(spread_bps - 202.02) < 0.5);

    // 6. Empty book is safe.
    LimitOrderBook empty;
    assert(empty.get_best_bid() == 0.0);
    assert(empty.get_spread_bps() == 0.0);

    // 7. Garbage events are ignored.
    empty.update(make_ev(Side::BUY, -5.0, 100));
    empty.update(make_ev(Side::BUY, 0.0, 100));
    assert(empty.get_best_bid() == 0.0);

    std::cout << "ALL LOB TESTS PASSED" << std::endl;
    return 0;
}
