from pricing.cart import Cart
from pricing.coupons import CouponBook
from pricing.discount import apply_discount


def test_small_discount_unchanged():
    assert apply_discount(1000, 1000) == 900


def test_discount_at_cap():
    assert apply_discount(1000, 5000) == 500


def test_discount_above_cap_is_capped():
    assert apply_discount(2000, 8000) == 1000


def test_large_coupon():
    assert apply_discount(1000, 7000) == 300


def test_cart_with_coupon():
    book = CouponBook()
    book.add("spring", 2000)
    cart = Cart(book).add("pen", 250, 4)
    cart.apply_coupon("SPRING")
    assert cart.total_cents() == 800
