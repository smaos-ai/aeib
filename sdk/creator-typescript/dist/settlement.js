"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.simulatePayout = simulatePayout;
exports.verifyPayout = verifyPayout;
function simulatePayout(amountCents) {
    const platform = Math.round(amountCents * 0.01);
    const creator = amountCents - platform;
    return { creator, platform };
}
function verifyPayout(record) {
    const { creator, platform } = simulatePayout(record.amount_cents);
    return (record.creator_payout_cents === creator &&
        record.platform_fee_cents === platform);
}
//# sourceMappingURL=settlement.js.map