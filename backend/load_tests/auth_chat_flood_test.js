import http from 'k6/http'
import { check, sleep } from 'k6'
import { Counter, Rate } from 'k6/metrics'

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000'
const NORMAL_USERNAME = __ENV.AUTH_USERNAME || 'admin@bssn.go.id'
const NORMAL_PASSWORD = __ENV.AUTH_PASSWORD || 'password123'
const ATTACK_USERNAME = __ENV.ATTACK_USERNAME || 'attacker@bssn.go.id'
const ATTACK_PASSWORD = __ENV.ATTACK_PASSWORD || 'wrongpassword'

export const authRateLimited = new Rate('auth_rate_limited')
export const chatRejectedOrLimited = new Rate('chat_rejected_or_limited')
export const normalLoginSucceeded = new Rate('normal_login_succeeded')
export const bruteForceRejected = new Rate('brute_force_rejected')
export const authorizedChatHandled = new Rate('authorized_chat_handled')
export const unauthorizedChatRejected = new Rate('unauthorized_chat_rejected')
export const status429Count = new Counter('status_429_count')
export const errorStatusCount = new Counter('error_status_count')

export const options = {
  scenarios: {
    // Realistic baseline: a small number of legitimate users log in periodically.
    normal_user_login: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.NORMAL_LOGIN_RPS || 1),
      timeUnit: '1s',
      duration: __ENV.NORMAL_LOGIN_DURATION || '1m',
      preAllocatedVUs: 2,
      maxVUs: 10,
      exec: 'normalUserLogin',
    },

    // Attack simulation: repeated bad passwords against one username/IP should become 429.
    brute_force_login_attack: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.ATTACK_RPS || 3),
      timeUnit: '1s',
      duration: __ENV.ATTACK_DURATION || '1m',
      preAllocatedVUs: 5,
      maxVUs: 30,
      exec: 'bruteForceLoginAttack',
    },

    // Realistic authenticated use: a logged-in user sends chatbot requests to an existing session.
    authorized_chat_usage: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.AUTHORIZED_CHAT_RPS || 2),
      timeUnit: '1s',
      duration: __ENV.AUTHORIZED_CHAT_DURATION || '1m',
      preAllocatedVUs: 5,
      maxVUs: 30,
      exec: 'authorizedChatUsage',
    },

    // Probe simulation: unauthenticated requests to protected chatbot endpoint must be rejected.
    unauthorized_chat_probe: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.UNAUTHORIZED_CHAT_RPS || 1),
      timeUnit: '1s',
      duration: __ENV.UNAUTHORIZED_CHAT_DURATION || '1m',
      preAllocatedVUs: 2,
      maxVUs: 10,
      exec: 'unauthorizedChatProbe',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.20'],
    normal_login_succeeded: ['rate>0.95'],
    brute_force_rejected: ['rate>0.95'],
    authorized_chat_handled: ['rate>0.95'],
    unauthorized_chat_rejected: ['rate>0.95'],
    auth_rate_limited: ['rate>0.01'],
  },
}

export function setup() {
  const login = http.post(
    `${BASE_URL}/api/auth/login`,
    { username: NORMAL_USERNAME, password: NORMAL_PASSWORD },
    { tags: { endpoint: 'setup_login' } },
  )

  const accessToken = login.status === 200 ? login.json('access_token') : ''
  let sessionId = ''

  if (accessToken) {
    const session = http.post(
      `${BASE_URL}/api/sessions/`,
      JSON.stringify({ user_id: 1, title: `k6 security evaluation ${Date.now()}` }),
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
        tags: { endpoint: 'setup_session' },
      },
    )
    if (session.status === 200) {
      sessionId = session.json('id') || ''
    }
  }

  return { accessToken, sessionId }
}

export function normalUserLogin() {
  const res = http.post(
    `${BASE_URL}/api/auth/login`,
    { username: NORMAL_USERNAME, password: NORMAL_PASSWORD },
    { tags: { endpoint: 'auth_login_normal' } },
  )

  normalLoginSucceeded.add(res.status === 200)
  recordStatusCounters(res)
  check(res, {
    'normal user login succeeds': r => r.status === 200 && Boolean(r.json('access_token')),
  })
  sleep(1)
}

export function bruteForceLoginAttack() {
  const res = http.post(
    `${BASE_URL}/api/auth/login`,
    { username: ATTACK_USERNAME, password: ATTACK_PASSWORD },
    { tags: { endpoint: 'auth_login_attack' } },
  )

  const rejectedOrLimited = res.status === 401 || res.status === 429
  bruteForceRejected.add(rejectedOrLimited)
  authRateLimited.add(res.status === 429)
  recordStatusCounters(res)
  check(res, {
    'failed login is rejected or rate-limited': () => rejectedOrLimited,
    'rate-limited response has Retry-After': r => r.status !== 429 || Boolean(r.headers['Retry-After']),
  })
  sleep(0.3)
}

export function authorizedChatUsage(data) {
  const payload = JSON.stringify({
    session_id: data.sessionId || 'missing-session',
    message: 'Apa ringkasan kewajiban keamanan SPBE?',
    use_rag: false,
    max_tokens: 128,
  })
  const res = http.post(`${BASE_URL}/api/chat/`, payload, {
    headers: {
      Authorization: `Bearer ${data.accessToken || 'missing-token'}`,
      'Content-Type': 'application/json',
    },
    tags: { endpoint: 'chat_authorized' },
  })

  const handled = res.status === 200 || res.status === 404 || res.status === 429
  authorizedChatHandled.add(handled)
  chatRejectedOrLimited.add(res.status === 401 || res.status === 429)
  recordStatusCounters(res)
  check(res, {
    'chat request is handled according to auth/rate-limit policy': () => handled,
    'authorized chat rate-limited response has Retry-After': r => r.status !== 429 || Boolean(r.headers['Retry-After']),
  })
  sleep(0.5)
}

export function unauthorizedChatProbe() {
  const payload = JSON.stringify({
    session_id: null,
    message: 'Probe tanpa token',
    use_rag: false,
    max_tokens: 64,
  })
  const res = http.post(`${BASE_URL}/api/chat/`, payload, {
    headers: { 'Content-Type': 'application/json' },
    tags: { endpoint: 'chat_unauthorized' },
  })

  const rejected = res.status === 401 || res.status === 429
  unauthorizedChatRejected.add(rejected)
  chatRejectedOrLimited.add(rejected)
  recordStatusCounters(res)
  check(res, {
    'unauthorized chat request is rejected or rate-limited': () => rejected,
  })
  sleep(0.5)
}

function recordStatusCounters(res) {
  if (res.status === 429) status429Count.add(1)
  if (res.status >= 500) errorStatusCount.add(1)
}
