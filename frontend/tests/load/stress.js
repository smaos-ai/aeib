import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m30s', target: 50 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  let res = http.get('http://127.0.0.1:5173');
  
  check(res, {
    'status is 200': (r) => r.status === 200,
    'page loads': (r) => r.body.includes('Governance'),
  });
  
  sleep(1);
}
