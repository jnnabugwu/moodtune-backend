# MoodTune Backend - Test Plan

## Overview

This document outlines the testing strategy for the MoodTune Backend API, including both manual testing with curl commands and frontend integration testing.

## Prerequisites

### Environment Setup

1. **Environment Variables** - Ensure `.env` file contains:

   ```bash
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_KEY=your_anon_key
   SUPABASE_SERVICE_KEY=your_service_role_key
   DATABASE_URL=postgresql+asyncpg://postgres:password@db.xxxxx.supabase.co:5432/postgres
   SPOTIFY_CLIENT_ID=your_client_id
   SPOTIFY_CLIENT_SECRET=your_client_secret
   SPOTIFY_REDIRECT_URI=http://localhost:8000/api/v1/spotify/callback
   ```

2. **Database Tables** - Ensure Supabase tables are created:
   - `spotify_connections`
   - `playlist_analyses`

3. **Start Server**:

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

4. **Get Supabase JWT Token**:
   - Use Supabase Auth in frontend to authenticate
   - Extract JWT token from Authorization header
   - For testing, you can use Supabase Dashboard or create a test user

---

## Test Categories

### 1. Authentication Tests

### 2. Spotify Integration Tests

### 3. Analysis Tests

### 4. Error Handling Tests

### 5. Frontend Integration Tests

---

## 1. Authentication Tests

### Test 1.1: Verify Supabase JWT Token (Valid Token)

**Purpose**: Verify that valid Supabase JWT tokens are accepted

**Curl Command**:

```bash
curl -X GET "http://localhost:8000/api/v1/spotify/status" \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response**:

- Status: `200 OK`
- Body: `{"connected": false}` or `{"connected": true, "spotify_user_id": "..."}`

**Frontend Test**:

```javascript
// In your frontend (React/Vue/etc)
const response = await fetch('http://localhost:8000/api/v1/spotify/status', {
  headers: {
    'Authorization': `Bearer ${supabaseToken}`,
    'Content-Type': 'application/json'
  }
});
const data = await response.json();
console.log('Status:', data);
```

---

### Test 1.2: Verify Invalid Token Rejection

**Purpose**: Ensure invalid tokens are rejected with 401

**Curl Command**:

```bash
curl -X GET "http://localhost:8000/api/v1/spotify/status" \
  -H "Authorization: Bearer invalid_token_here" \
  -H "Content-Type: application/json"
```

**Expected Response**:

- Status: `401 Unauthorized`
- Body: `{"detail": "Invalid authentication: ..."}`

**Frontend Test**:

```javascript
try {
  const response = await fetch('http://localhost:8000/api/v1/spotify/status', {
    headers: {
      'Authorization': 'Bearer invalid_token',
      'Content-Type': 'application/json'
    }
  });
  if (!response.ok) {
    console.log('Expected 401:', response.status);
  }
} catch (error) {
  console.error('Error:', error);
}
```

---

### Test 1.3: Missing Authorization Header

**Purpose**: Ensure missing auth header returns 403

**Curl Command**:

```bash
curl -X GET "http://localhost:8000/api/v1/spotify/status" \
  -H "Content-Type: application/json"
```

**Expected Response**:

- Status: `403 Forbidden`
- Body: `{"detail": "Not authenticated"}`

---

## 2. Spotify Integration Tests

### Test 2.1: Get Spotify Authorization URL

**Purpose**: Verify OAuth flow initiation

**Curl Command**:

```bash
curl -X GET "http://localhost:8000/api/v1/spotify/authorize" \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response**:

- Status: `200 OK`
- Body: `{"authorize_url": "https://accounts.spotify.com/authorize?...", "state": "..."}`

**Frontend Test**:

```javascript
const response = await fetch('http://localhost:8000/api/v1/spotify/authorize', {
  headers: {
    'Authorization': `Bearer ${supabaseToken}`,
    'Content-Type': 'application/json'
  }
});
const { authorize_url, state } = await response.json();
// Store state for verification
localStorage.setItem('spotify_oauth_state', state);
// Redirect user to authorize_url
window.location.href = authorize_url;
```

**Manual Steps**:

1. Copy `authorize_url` from response
2. Open in browser
3. Authorize with Spotify
4. Note the `code` and `state` from callback URL

---

### Test 2.2: Handle Spotify OAuth Callback

**Purpose**: Complete OAuth flow and store tokens

**Curl Command**:

```bash
# After getting code from Spotify callback
curl -X GET "http://localhost:8000/api/v1/spotify/callback?code=SPOTIFY_AUTH_CODE&state=STATE_VALUE" \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response**:

- Status: `200 OK`
- Body: `{"message": "Spotify connected successfully", "spotify_user_id": "..."}`

**Frontend Test**:

```javascript
// In your OAuth callback handler
const urlParams = new URLSearchParams(window.location.search);
const code = urlParams.get('code');
const state = urlParams.get('state');

// Verify state matches stored state
const storedState = localStorage.getItem('spotify_oauth_state');
if (state !== storedState) {
  console.error('State mismatch - possible CSRF attack');
  return;
}

const response = await fetch(
  `http://localhost:8000/api/v1/spotify/callback?code=${code}&state=${state}`,
  {
    headers: {
      'Authorization': `Bearer ${supabaseToken}`,
      'Content-Type': 'application/json'
    }
  }
);
const data = await response.json();
console.log('Connected:', data);
```

---

### Test 2.3: Check Spotify Connection Status

**Purpose**: Verify connection status endpoint

**Curl Command**:

```bash
curl -X GET "http://localhost:8000/api/v1/spotify/status" \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response** (Connected):

- Status: `200 OK`
- Body: `{"connected": true, "spotify_user_id": "user123"}`

**Expected Response** (Not Connected):

- Status: `200 OK`
- Body: `{"connected": false, "spotify_user_id": null}`

**Frontend Test**:

```javascript
const checkConnection = async () => {
  const response = await fetch('http://localhost:8000/api/v1/spotify/status', {
    headers: {
      'Authorization': `Bearer ${supabaseToken}`,
      'Content-Type': 'application/json'
    }
  });
  const status = await response.json();
  
  if (status.connected) {
    console.log('Spotify connected:', status.spotify_user_id);
    // Show "Connected" UI
  } else {
    console.log('Spotify not connected');
    // Show "Connect Spotify" button
  }
};
```

---

### Test 2.4: Get User's Playlists

**Purpose**: Fetch user's Spotify playlists

**Curl Command**:

```bash
curl -X GET "http://localhost:8000/api/v1/spotify/playlists?limit=20&offset=0" \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response**:

- Status: `200 OK`
- Body:

```json
{
  "playlists": [
    {
      "id": "playlist_id_1",
      "name": "My Playlist",
      "description": "Description",
      "tracks_count": 50,
      "image_url": "https://..."
    }
  ],
  "total": 10
}
```

**Frontend Test**:

```javascript
const fetchPlaylists = async (limit = 20, offset = 0) => {
  const response = await fetch(
    `http://localhost:8000/api/v1/spotify/playlists?limit=${limit}&offset=${offset}`,
    {
      headers: {
        'Authorization': `Bearer ${supabaseToken}`,
        'Content-Type': 'application/json'
      }
    }
  );
  const data = await response.json();
  console.log('Playlists:', data.playlists);
  console.log('Total:', data.total);
  return data;
};
```

**Test Cases**:

- ✅ Default pagination (limit=50, offset=0)
- ✅ Custom pagination (limit=10, offset=20)
- ✅ Edge case: limit=1
- ✅ Edge case: offset beyond total

---

### Test 2.5: Disconnect Spotify

**Purpose**: Remove Spotify connection

**Curl Command**:

```bash
curl -X POST "http://localhost:8000/api/v1/spotify/disconnect" \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response**:

- Status: `200 OK`
- Body: `{"message": "Spotify disconnected successfully"}`

**Frontend Test**:

```javascript
const disconnectSpotify = async () => {
  const response = await fetch('http://localhost:8000/api/v1/spotify/disconnect', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${supabaseToken}`,
      'Content-Type': 'application/json'
    }
  });
  const data = await response.json();
  console.log('Disconnected:', data.message);
  // Update UI to show "Connect Spotify" button
};
```

**Error Case** (No connection):

- Status: `404 Not Found`
- Body: `{"detail": "No Spotify connection found"}`

---

### Test 2.6: Token Auto-Refresh

**Purpose**: Verify expired tokens are automatically refreshed

**Manual Test Steps**:

1. Connect Spotify (Test 2.2)
2. Manually update `expires_at` in database to past time:

   ```sql
   UPDATE spotify_connections 
   SET expires_at = NOW() - INTERVAL '1 hour'
   WHERE user_id = 'YOUR_USER_ID';
   ```

3. Call any Spotify endpoint (e.g., get playlists)
4. Verify token was refreshed in database
5. Verify API call succeeded

**Curl Command** (After manual expiration):

```bash
curl -X GET "http://localhost:8000/api/v1/spotify/playlists" \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected**: Should succeed and refresh token automatically

---

## 3. Analysis Tests

### Test 3.1: Analyze Playlist Mood

**Purpose**: Analyze a playlist and store results

**Curl Command**:

```bash
curl -X POST "http://localhost:8000/api/v1/analysis/analyze/PLAYLIST_ID_HERE" \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response**:

- Status: `200 OK`
- Body:

```json
{
  "id": "uuid-here",
  "user_id": "user-uuid",
  "playlist_id": "spotify_playlist_id",
  "playlist_name": "My Playlist",
  "mood_results": {
    "primary_mood": "Happy & Energetic",
    "mood_category": "upbeat",
    "mood_descriptors": ["danceable", "fast-paced"],
    "averages": {
      "valence": 0.75,
      "energy": 0.82,
      "danceability": 0.68,
      "tempo": 125.5,
      "acousticness": 0.15,
      "instrumentalness": 0.05
    },
    "track_count": 50,
    "raw_features": [...]
  },
  "created_at": "2024-01-01T12:00:00Z"
}
```

**Frontend Test**:

```javascript
const analyzePlaylist = async (playlistId) => {
  const response = await fetch(
    `http://localhost:8000/api/v1/analysis/analyze/${playlistId}`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${supabaseToken}`,
        'Content-Type': 'application/json'
      }
    }
  );
  const analysis = await response.json();
  console.log('Analysis:', analysis);
  console.log('Mood:', analysis.mood_results.primary_mood);
  return analysis;
};
```

**Test Cases**:

- ✅ Analyze playlist with many tracks (>100)
- ✅ Analyze playlist with few tracks (<10)
- ✅ Analyze empty playlist (should fail gracefully)
- ✅ Analyze playlist with missing audio features

---

### Test 3.2: Get Analysis History

**Purpose**: Retrieve user's analysis history

**Curl Command**:

```bash
curl -X GET "http://localhost:8000/api/v1/analysis/history?limit=20&offset=0" \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response**:

- Status: `200 OK`
- Body:

```json
{
  "analyses": [
    {
      "id": "uuid-1",
      "playlist_id": "playlist_1",
      "playlist_name": "Playlist 1",
      "mood_results": {...},
      "created_at": "2024-01-01T12:00:00Z"
    }
  ],
  "total": 5
}
```

**Frontend Test**:

```javascript
const getAnalysisHistory = async (limit = 20, offset = 0) => {
  const response = await fetch(
    `http://localhost:8000/api/v1/analysis/history?limit=${limit}&offset=${offset}`,
    {
      headers: {
        'Authorization': `Bearer ${supabaseToken}`,
        'Content-Type': 'application/json'
      }
    }
  );
  const data = await response.json();
  console.log('History:', data.analyses);
  return data;
};
```

**Test Cases**:

- ✅ Empty history (new user)
- ✅ Pagination (limit=10, offset=10)
- ✅ Ordering (should be DESC by created_at)

---

### Test 3.3: Get Specific Analysis

**Purpose**: Retrieve a specific analysis by ID

**Curl Command**:

```bash
curl -X GET "http://localhost:8000/api/v1/analysis/ANALYSIS_UUID_HERE" \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response**:

- Status: `200 OK`
- Body: Same as Test 3.1 response

**Frontend Test**:

```javascript
const getAnalysis = async (analysisId) => {
  const response = await fetch(
    `http://localhost:8000/api/v1/analysis/${analysisId}`,
    {
      headers: {
        'Authorization': `Bearer ${supabaseToken}`,
        'Content-Type': 'application/json'
      }
    }
  );
  const analysis = await response.json();
  return analysis;
};
```

**Error Cases**:

- ❌ Invalid UUID format: `404 Not Found`
- ❌ Analysis doesn't exist: `404 Not Found`
- ❌ Analysis belongs to different user: `403 Forbidden`

---

## 4. Error Handling Tests

### Test 4.1: No Spotify Connection

**Purpose**: Verify graceful handling when Spotify not connected

**Curl Command**:

```bash
# Without connecting Spotify first
curl -X GET "http://localhost:8000/api/v1/spotify/playlists" \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response**:

- Status: `404 Not Found`
- Body: `{"detail": "No Spotify connection found for user"}`

---

### Test 4.2: Invalid Playlist ID

**Purpose**: Handle invalid playlist IDs gracefully

**Curl Command**:

```bash
curl -X POST "http://localhost:8000/api/v1/analysis/analyze/invalid_playlist_id" \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT_TOKEN" \
  -H "Content-Type: application/json"
```

**Expected Response**:

- Status: `500 Internal Server Error` or `400 Bad Request`
- Body: `{"detail": "Failed to analyze playlist: ..."}`

---

### Test 4.3: Spotify API Rate Limiting

**Purpose**: Handle 429 rate limit errors

**Manual Test**:

1. Make many rapid API calls
2. Verify error handling

**Expected Response**:

- Status: `429 Too Many Requests` or `500 Internal Server Error`
- Body: `{"detail": "Spotify API rate limit exceeded"}`

---

### Test 4.4: Expired Spotify Token (Refresh Failure)

**Purpose**: Handle refresh token expiration

**Manual Test Steps**:

1. Connect Spotify
2. Manually invalidate refresh token in database
3. Expire access token
4. Make API call

**Expected**: Should handle gracefully with appropriate error message

---

## 5. Frontend Integration Tests

### Test 5.1: Complete User Flow

**Purpose**: Test end-to-end user journey

**Steps**:

1. **User Login** (Frontend with Supabase)

   ```javascript
   const { data, error } = await supabase.auth.signInWithPassword({
     email: 'test@example.com',
     password: 'password'
   });
   const token = data.session.access_token;
   ```

2. **Check Spotify Status**

   ```javascript
   const status = await checkConnection(token);
   ```

3. **Connect Spotify** (if not connected)

   ```javascript
   const { authorize_url } = await fetch('/api/v1/spotify/authorize', {
     headers: { 'Authorization': `Bearer ${token}` }
   }).then(r => r.json());
   // Redirect to authorize_url
   ```

4. **Handle Callback**

   ```javascript
   // After Spotify redirects back
   const code = new URLSearchParams(window.location.search).get('code');
   await fetch(`/api/v1/spotify/callback?code=${code}`, {
     headers: { 'Authorization': `Bearer ${token}` }
   });
   ```

5. **Fetch Playlists**

   ```javascript
   const { playlists } = await fetchPlaylists(token);
   ```

6. **Analyze Playlist**

   ```javascript
   const analysis = await analyzePlaylist(token, playlists[0].id);
   ```

7. **View History**

   ```javascript
   const history = await getAnalysisHistory(token);
   ```

---

### Test 5.2: Error State Handling

**Purpose**: Verify frontend handles all error states

**Test Cases**:

- ✅ Network errors (offline, timeout)
- ✅ 401 errors (token expired - redirect to login)
- ✅ 404 errors (show "Not found" message)
- ✅ 500 errors (show "Server error" message)
- ✅ Loading states during API calls
- ✅ Retry mechanisms for failed requests

---

### Test 5.3: Token Refresh Flow

**Purpose**: Verify frontend handles token refresh

**Steps**:

1. User logs in, gets Supabase token
2. Token expires after 1 hour
3. Frontend should detect 401 and refresh token
4. Retry original request

**Implementation**:

```javascript
// Axios interceptor example
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Refresh Supabase token
      const { data } = await supabase.auth.refreshSession();
      const newToken = data.session.access_token;
      
      // Retry original request
      error.config.headers.Authorization = `Bearer ${newToken}`;
      return axios.request(error.config);
    }
    return Promise.reject(error);
  }
);
```

---

## 6. Performance Tests

### Test 6.1: Large Playlist Analysis

**Purpose**: Test analysis of playlists with 100+ tracks

**Steps**:

1. Find/create playlist with 200+ tracks
2. Analyze playlist
3. Verify:
   - Response time < 30 seconds
   - All tracks processed
   - Results accurate

---

### Test 6.2: Concurrent Requests

**Purpose**: Test API under load

**Curl Command** (using parallel):

```bash
# Test 10 concurrent requests
seq 1 10 | xargs -P 10 -I {} curl -X GET \
  "http://localhost:8000/api/v1/spotify/status" \
  -H "Authorization: Bearer YOUR_SUPABASE_JWT_TOKEN"
```

**Expected**: All requests should succeed

---

## 7. Security Tests

### Test 7.1: CSRF Protection

**Purpose**: Verify state parameter in OAuth flow

**Test**:

- Try to use callback with mismatched state
- Should fail or ignore request

---

### Test 7.2: User Isolation

**Purpose**: Verify users can only access their own data

**Steps**:

1. User A creates analysis
2. User B tries to access User A's analysis
3. Should return 403 Forbidden

**Curl Command**:

```bash
# User B trying to access User A's analysis
curl -X GET "http://localhost:8000/api/v1/analysis/USER_A_ANALYSIS_ID" \
  -H "Authorization: Bearer USER_B_JWT_TOKEN"
```

**Expected**: `403 Forbidden`

---

## Test Checklist

### Authentication

- [ ] Valid JWT token accepted
- [ ] Invalid JWT token rejected (401)
- [ ] Missing auth header rejected (403)
- [ ] Expired token handled gracefully

### Spotify Integration

- [ ] Authorization URL generated correctly
- [ ] OAuth callback processes successfully
- [ ] Connection status endpoint works
- [ ] Playlists fetched successfully
- [ ] Disconnect works correctly
- [ ] Token auto-refresh works
- [ ] Error handling for no connection

### Analysis

- [ ] Playlist analysis completes successfully
- [ ] Analysis history retrieved correctly
- [ ] Specific analysis retrieved correctly
- [ ] User ownership verified (403 for other users)
- [ ] Empty playlist handled gracefully
- [ ] Large playlists (>100 tracks) handled

### Error Handling

- [ ] 400 errors handled
- [ ] 401 errors handled
- [ ] 403 errors handled
- [ ] 404 errors handled
- [ ] 500 errors handled
- [ ] Rate limiting handled

### Frontend Integration

- [ ] Complete user flow works
- [ ] Error states displayed correctly
- [ ] Loading states shown
- [ ] Token refresh works
- [ ] Retry mechanisms work

---

## Test Data Setup

### Create Test User in Supabase

```sql
-- Use Supabase Dashboard or API to create test user
-- Or use Supabase Auth in frontend
```

### Create Test Spotify Connection

```sql
-- After OAuth flow, connection should exist
-- Or manually insert for testing:
INSERT INTO spotify_connections (
  user_id, spotify_user_id, access_token, refresh_token, expires_at
) VALUES (
  'USER_UUID',
  'spotify_user_123',
  'test_access_token',
  'test_refresh_token',
  NOW() + INTERVAL '1 hour'
);
```

### Create Test Analysis

```sql
-- After running analysis, should exist
-- Or manually insert for testing:
INSERT INTO playlist_analyses (
  user_id, playlist_id, playlist_name, mood_results
) VALUES (
  'USER_UUID',
  'test_playlist_id',
  'Test Playlist',
  '{"primary_mood": "Happy", "mood_category": "upbeat"}'::jsonb
);
```

---

## Running Tests

### Quick Test Script

```bash
#!/bin/bash

# Set your token
TOKEN="YOUR_SUPABASE_JWT_TOKEN"
BASE_URL="http://localhost:8000/api/v1"

echo "Testing Spotify Status..."
curl -X GET "$BASE_URL/spotify/status" \
  -H "Authorization: Bearer $TOKEN"

echo -e "\n\nTesting Get Playlists..."
curl -X GET "$BASE_URL/spotify/playlists" \
  -H "Authorization: Bearer $TOKEN"

echo -e "\n\nTesting Analysis History..."
curl -X GET "$BASE_URL/analysis/history" \
  -H "Authorization: Bearer $TOKEN"
```

### Automated Testing

Consider using:

- **pytest** for backend unit/integration tests
- **Postman** for API testing
- **Jest/Vitest** for frontend tests
- **Playwright/Cypress** for E2E tests

---

## Notes

- Always use valid Supabase JWT tokens for testing
- Spotify OAuth requires actual Spotify account
- Some tests require manual database manipulation
- Rate limits apply to Spotify API (use sparingly)
- Test in development environment first
- Keep test data separate from production

---

## Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check JWT token is valid
   - Verify token hasn't expired
   - Ensure Authorization header format: `Bearer TOKEN`

2. **404 Not Found**
   - Verify Spotify connection exists
   - Check playlist/analysis IDs are correct
   - Ensure database tables exist

3. **500 Internal Server Error**
   - Check server logs
   - Verify environment variables
   - Check database connection
   - Verify Spotify API credentials

4. **Token Refresh Issues**
   - Check refresh_token is valid
   - Verify expires_at is set correctly
   - Check database connection

---

## Success Criteria

All tests should pass:

- ✅ All endpoints return expected status codes
- ✅ All responses match expected schemas
- ✅ Error handling works correctly
- ✅ Frontend integration works smoothly
- ✅ Token refresh works automatically
- ✅ User isolation is enforced
- ✅ Performance is acceptable (< 5s for most endpoints)



