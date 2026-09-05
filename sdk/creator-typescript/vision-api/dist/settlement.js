"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.simulatePayout = simulatePayout;
function simulatePayout(amountCents) {
    // 99% creator, 1% platform
    const platform = Math.round(amountCents * 0.01);
    const creator = amountCents - platform;
    return { creator, platform };
}
//# sourceMappingURL=settlement.js.map