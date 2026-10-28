from pricing.cart import Cart
from pricing.coupons import CouponBook
from pricing.receipt import render_receipt, savings_cents


def test_receipt_with_small_coupon():
    book = CouponBook()
    book.add("ten", 1000)
    cart = Cart(book).add("pen", 250, 2)
    cart.apply_coupon("ten")
    assert render_receipt(cart).splitlines()[-2:] == ["coupon TEN", "TOTAL 4.50"]
    assert savings_cents(cart) == 50
