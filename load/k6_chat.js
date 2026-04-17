import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  scenarios: {
    chat_load: {
      executor: 'ramping-vus',
      startVUs: 5,
      stages: [
        { duration: '2m', target: 25 },
        { duration: '3m', target: 50 },
        { duration: '3m', target: 100 },
        { duration: '2m', target: 0 },
      ],
      gracefulRampDown: '30s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.02'],
    http_req_duration: ['p(95)<2500'],
  },
};

const baseUrl = __ENV.BASE_URL || 'http://localhost:8000/v1';
const token = __ENV.AUTH_TOKEN || '';

export default function () {
  const payload = JSON.stringify({
    question: 'What is the annual leave policy?',
    collection: 'HR-docs',
  });

  const headers = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = http.post(`${baseUrl}/chat`, payload, { headers });

  check(res, {
    'status is 200': (r) => r.status === 200,
    'has answer': (r) => {
      try {
        return !!JSON.parse(r.body).answer;
      } catch {
        return false;
      }
    },
  });

  sleep(1);
}
