#!/usr/bin/env node
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const url = require('url');
const { exec } = require('child_process');

const gmailConfigDir = path.join(process.env.HOME, '.gmail-mcp');
const keysPath = path.join(gmailConfigDir, 'gcp-oauth.keys.json');
const credentialsPath = path.join(gmailConfigDir, 'credentials.json');

// Read OAuth keys
const keys = JSON.parse(fs.readFileSync(keysPath, 'utf8')).installed;
const clientId = keys.client_id;
const clientSecret = keys.client_secret;
const redirectUri = 'http://localhost:3000/oauth2callback';

// Step 1: Create auth URL
const authUrl = new URL('https://accounts.google.com/o/oauth2/v2/auth');
authUrl.searchParams.append('access_type', 'offline');
authUrl.searchParams.append('scope', 'https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/gmail.settings.basic');
authUrl.searchParams.append('response_type', 'code');
authUrl.searchParams.append('client_id', clientId);
authUrl.searchParams.append('redirect_uri', redirectUri);

console.log('\n✅ AUTH URL (click this in browser):');
console.log(authUrl.toString());
console.log('\n⏳ Waiting for authorization...\n');

// Step 2: Start local server to catch redirect
const server = http.createServer((req, res) => {
  const parsedUrl = url.parse(req.url, true);
  const code = parsedUrl.query.code;
  const error = parsedUrl.query.error;

  if (error) {
    res.writeHead(400, { 'Content-Type': 'text/plain' });
    res.end(`❌ Authorization failed: ${error}\n${parsedUrl.query.error_description || ''}`);
    server.close();
    process.exit(1);
  }

  if (code) {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('✅ Authorization successful! Exchanging code for token...');

    // Step 3: Exchange code for token
    const tokenData = new URLSearchParams({
      code: code,
      client_id: clientId,
      client_secret: clientSecret,
      redirect_uri: redirectUri,
      grant_type: 'authorization_code'
    });

    const options = {
      hostname: 'oauth2.googleapis.com',
      path: '/token',
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': tokenData.toString().length
      }
    };

    const tokenReq = https.request(options, (tokenRes) => {
      let data = '';
      tokenRes.on('data', chunk => data += chunk);
      tokenRes.on('end', () => {
        try {
          const tokens = JSON.parse(data);
          if (tokens.error) {
            console.error('❌ Token exchange failed:', tokens.error_description);
            server.close();
            process.exit(1);
          }

          // Step 4: Save credentials
          fs.writeFileSync(credentialsPath, JSON.stringify(tokens, null, 2));
          console.log('\n✅ Credentials saved to:', credentialsPath);
          console.log('✅ Gmail MCP is ready to use!\n');

          server.close();
          process.exit(0);
        } catch (e) {
          console.error('❌ Failed to parse token response:', e.message);
          server.close();
          process.exit(1);
        }
      });
    });

    tokenReq.on('error', (e) => {
      console.error('❌ Token request failed:', e.message);
      server.close();
      process.exit(1);
    });

    tokenReq.write(tokenData.toString());
    tokenReq.end();
  }
});

server.listen(3000, () => {
  console.log('🚀 Local auth server running on port 3000');
  // Open browser automatically on macOS
  exec(`open "${authUrl.toString()}"`, (err) => {
    if (err) console.log('📲 Browser not opened automatically. Copy the URL above and paste it manually.');
  });
});

server.on('error', (e) => {
  console.error('❌ Server error:', e.message);
  if (e.code === 'EADDRINUSE') {
    console.error('Port 3000 already in use. Kill it with: lsof -ti:3000 | xargs kill -9');
  }
  process.exit(1);
});

process.on('SIGINT', () => {
  console.log('\n⏹️  Auth cancelled');
  server.close();
  process.exit(0);
});
