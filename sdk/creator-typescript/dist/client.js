"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CapsuleClient = void 0;
const settlement_1 = require("./settlement");
class CapsuleClient {
    constructor(baseUrl, apiKey) {
        this.baseUrl = baseUrl.replace(/\/$/, '');
        this.apiKey = apiKey;
    }
    headers() {
        return {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${this.apiKey}`,
        };
    }
    async govern(input) {
        const response = await fetch(`${this.baseUrl}/v1/govern`, {
            method: 'POST',
            headers: this.headers(),
            body: JSON.stringify({ input }),
        });
        if (!response.ok) {
            throw new Error(`govern failed: ${response.status} ${response.statusText}`);
        }
        return response.json();
    }
    async fetchLedger(creatorId) {
        const response = await fetch(`${this.baseUrl}/v1/ledger?creator_id=${encodeURIComponent(creatorId)}`, { method: 'GET', headers: this.headers() });
        if (!response.ok) {
            throw new Error(`fetchLedger failed: ${response.status} ${response.statusText}`);
        }
        return response.json();
    }
    async simulatePayout(amount) {
        return (0, settlement_1.simulatePayout)(amount);
    }
}
exports.CapsuleClient = CapsuleClient;
//# sourceMappingURL=client.js.map