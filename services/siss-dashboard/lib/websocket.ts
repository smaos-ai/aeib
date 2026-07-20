import { WebSocketServer, WebSocket } from 'ws';
import { Server } from 'http';

interface WebSocketClient {
  ws: WebSocket;
  creatorId: string;
  isAlive: boolean;
}

const clients: WebSocketClient[] = [];

export function initializeWebSocketServer(server: Server) {
  const wss = new WebSocketServer({ server, path: '/ws/royalties' });

  wss.on('connection', (ws: WebSocket, req) => {
    const url = new URL(req.url || '', 'http://localhost');
    const creatorId = url.searchParams.get('creator_id');

    // Reject if no creator_id
    if (!creatorId) {
      ws.close(1008, 'Missing creator_id parameter');
      return;
    }

    // Register client
    const client: WebSocketClient = {
      ws,
      creatorId,
      isAlive: true
    };

    clients.push(client);

    // Send welcome message
    ws.send(JSON.stringify({
      type: 'connected',
      data: {
        creator_id: creatorId,
        timestamp: new Date().toISOString()
      }
    }));

    // Handle incoming messages
    ws.on('message', (data: string) => {
      try {
        const message = JSON.parse(data);

        // Broadcast to other clients for same creator
        broadcastToCreator(creatorId, message, ws);
      } catch (error) {
        console.error('WebSocket message error:', error);
      }
    });

    // Handle pong (heartbeat response)
    ws.on('pong', () => {
      client.isAlive = true;
    });

    // Handle disconnect
    ws.on('close', () => {
      const index = clients.findIndex(c => c.ws === ws);
      if (index !== -1) {
        clients.splice(index, 1);
      }
    });

    // Handle errors
    ws.on('error', (error) => {
      console.error('WebSocket error:', error);
    });
  });

  // Heartbeat interval (every 30 seconds)
  const heartbeatInterval = setInterval(() => {
    clients.forEach(client => {
      if (!client.isAlive) {
        client.ws.terminate();
        const index = clients.indexOf(client);
        if (index !== -1) {
          clients.splice(index, 1);
        }
      } else {
        client.isAlive = false;
        client.ws.ping();

        // Send heartbeat message
        client.ws.send(JSON.stringify({
          type: 'heartbeat',
          timestamp: new Date().toISOString()
        }));
      }
    });
  }, 30000);

  // Cleanup on server close
  const originalClose = server.close.bind(server);
  server.close = function() {
    clearInterval(heartbeatInterval);
    wss.close();
    return originalClose();
  };

  return wss;
}

export function broadcastToCreator(
  creatorId: string,
  message: any,
  excludeWs?: WebSocket
) {
  clients.forEach(client => {
    if (client.creatorId === creatorId && client.ws.readyState === WebSocket.OPEN) {
      if (excludeWs && client.ws === excludeWs) {
        return;
      }
      try {
        client.ws.send(JSON.stringify(message));
      } catch (error) {
        console.error('Error broadcasting message:', error);
      }
    }
  });
}

export function broadcastRoyaltyUpdate(creatorId: string, royaltyData: any) {
  broadcastToCreator(creatorId, {
    type: 'royalty.updated',
    data: royaltyData,
    timestamp: new Date().toISOString()
  });
}

export function broadcastBatchRoyalties(creatorId: string, entries: any[]) {
  const totalAmount = entries.reduce((sum, entry) => sum + entry.amount, 0);

  broadcastToCreator(creatorId, {
    type: 'royalties.batch',
    data: {
      creator_id: creatorId,
      entries,
      total_amount: totalAmount
    },
    timestamp: new Date().toISOString()
  });
}
