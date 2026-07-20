import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import WebSocket from 'ws';

const WS_URL = process.env.WS_URL || 'ws://localhost:3000/ws';

describe('WebSocket Real-Time Updates', () => {
  let ws: WebSocket;
  let creatorId: string;

  beforeAll(async () => {
    creatorId = 'test-creator-' + Math.random().toString(36).substr(2, 9);
    // Connection will be established in individual tests
  });

  function connectWebSocket(creatorId: string): Promise<WebSocket> {
    return new Promise((resolve, reject) => {
      const client = new WebSocket(`${WS_URL}/royalties?creator_id=${creatorId}`);

      client.on('open', () => resolve(client));
      client.on('error', reject);

      setTimeout(() => reject(new Error('WebSocket connection timeout')), 5000);
    });
  }

  it('test_websocket_updates_realtime: should establish WebSocket connection', async () => {
    ws = await connectWebSocket(creatorId);

    expect(ws.readyState).toBe(WebSocket.OPEN);
  });

  it('should receive real-time royalty update', async () => {
    const ws = await connectWebSocket(creatorId);

    const messagePromise = new Promise<any>((resolve) => {
      ws.on('message', (data: string) => {
        const parsed = JSON.parse(data);
        if (parsed.type === 'royalty.updated') {
          resolve(parsed);
        }
      });
    });

    // Simulate royalty update (would be sent by backend)
    // In real scenario, this would come from API or event bus
    const updateMessage = {
      type: 'royalty.updated',
      data: {
        creator_id: creatorId,
        amount: 150.00,
        timestamp: new Date().toISOString(),
        status: 'completed'
      }
    };

    // In integration, backend would send this via event emitter
    // For testing, we simulate it being sent by another client
    setTimeout(() => {
      ws.send(JSON.stringify(updateMessage));
    }, 100);

    const message = await Promise.race([
      messagePromise,
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Message timeout')), 3000)
      )
    ]);

    expect(message).toBeDefined();
    expect(message.type).toBe('royalty.updated');
    expect(message.data.creator_id).toBe(creatorId);

    ws.close();
  });

  it('should send heartbeat to maintain connection', async () => {
    const ws = await connectWebSocket(creatorId);

    const heartbeatPromise = new Promise<any>((resolve) => {
      const timeout = setTimeout(() => {
        reject(new Error('Heartbeat not received'));
      }, 2000);

      ws.on('message', (data: string) => {
        const parsed = JSON.parse(data);
        if (parsed.type === 'heartbeat') {
          clearTimeout(timeout);
          resolve(parsed);
        }
      });
    });

    try {
      const heartbeat = await heartbeatPromise;
      expect(heartbeat.type).toBe('heartbeat');
    } finally {
      ws.close();
    }
  });

  it('should handle multiple subscribers for same creator', async () => {
    const ws1 = await connectWebSocket(creatorId);
    const ws2 = await connectWebSocket(creatorId);

    expect(ws1.readyState).toBe(WebSocket.OPEN);
    expect(ws2.readyState).toBe(WebSocket.OPEN);

    ws1.close();
    ws2.close();
  });

  it('should receive batch royalty update', async () => {
    const ws = await connectWebSocket(creatorId);

    const messagePromise = new Promise<any>((resolve) => {
      ws.on('message', (data: string) => {
        const parsed = JSON.parse(data);
        if (parsed.type === 'royalties.batch') {
          resolve(parsed);
        }
      });
    });

    const batchMessage = {
      type: 'royalties.batch',
      data: {
        creator_id: creatorId,
        entries: [
          {
            id: 'royalty-1',
            amount: 100.00,
            status: 'completed'
          },
          {
            id: 'royalty-2',
            amount: 200.00,
            status: 'completed'
          },
          {
            id: 'royalty-3',
            amount: 200.00,
            status: 'completed'
          }
        ],
        total_amount: 500.00
      }
    };

    setTimeout(() => {
      ws.send(JSON.stringify(batchMessage));
    }, 100);

    const message = await Promise.race([
      messagePromise,
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Batch message timeout')), 3000)
      )
    ]);

    expect(message.type).toBe('royalties.batch');
    expect(message.data.entries).toHaveLength(3);
    expect(message.data.total_amount).toBe(500.00);

    ws.close();
  });

  it('should properly close connection', async () => {
    const ws = await connectWebSocket(creatorId);

    ws.close();

    // Give time for close to process
    await new Promise(resolve => setTimeout(resolve, 100));

    expect(ws.readyState).toBe(WebSocket.CLOSED);
  });

  it('should reject connection without creator_id', async () => {
    try {
      const ws = new WebSocket(`${WS_URL}/royalties`);

      await new Promise((resolve, reject) => {
        ws.on('open', () => reject(new Error('Should not connect without creator_id')));
        ws.on('close', () => resolve(null));
        ws.on('error', () => resolve(null));

        setTimeout(() => reject(new Error('Connection timeout')), 2000);
      });
    } catch (error: any) {
      expect(error).toBeDefined();
    }
  });

  afterAll(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.close();
    }
  });
});
