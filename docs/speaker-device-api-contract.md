# Speaker Device API Contract

This contract keeps the Jetson speaker, Android app, web app, and backend aligned.

## Authentication

### App And Web

App and web clients authenticate as users.

```text
Authorization: Bearer {user_access_token}
```

### Jetson Speaker

The device uses a device token after pairing.

```text
Authorization: Bearer {device_access_token}
X-Device-Id: {device_id}
```

The current MVP can continue using:

```text
X-API-Key: {api_key}
```

## Pairing

### Create Pairing Code

Called by the Jetson when it is not linked to an account.

```text
POST /api/devices/pairing-code
```

Request:

```json
{
  "device_id": "jetson-nano-dev-001",
  "device_name": "Living Room Jinu",
  "device_type": "jetson_nano_speaker"
}
```

Response:

```json
{
  "pairing_code": "482913",
  "expires_in_seconds": 600
}
```

The speaker reads:

```text
Pairing code is 482913.
```

### Claim Pairing Code

Called by Android or web after the user logs in.

```text
POST /api/devices/claim
Authorization: Bearer {user_access_token}
```

Request:

```json
{
  "pairing_code": "482913",
  "device_name": "Living Room Jinu",
  "user_id": "user@example.com",
  "user_name": "User Name"
}
```

Response:

```json
{
  "device_id": "jetson-nano-dev-001",
  "device_name": "Living Room Jinu",
  "linked": true
}
```

### Complete Pairing

Called by Jetson while polling after a pairing code was created.

```text
POST /api/devices/pairing-status
```

Request:

```json
{
  "device_id": "jetson-nano-dev-001",
  "pairing_code": "482913"
}
```

Response before claim:

```json
{
  "linked": false
}
```

Response after claim:

```json
{
  "linked": true,
  "device_access_token": "device-token",
  "user_id": "user-id"
}
```

## Speaker Analysis

The MVP already maps to the current Android upload endpoint.

```text
POST /api/stt-analyze
Authorization: Bearer {device_access_token}
X-Device-Id: {device_id}
Content-Type: multipart/form-data
```

Fields:

```text
audio: wav/m4a audio file
audiostt_result: same audio file for backward compatibility
device_id: string
session_id: user or device session id
```

Response:

```json
{
  "stt": "오늘 기분이 좀 이상해",
  "answer": "오늘은 컨디션을 조금 더 살펴보면 좋겠어요.",
  "session_score": 82,
  "risk_level": "주의",
  "reason": "반복 표현과 시간 혼란이 약하게 감지되었습니다.",
  "score_repeat": 10,
  "score_memory": 5,
  "score_time": 20,
  "score_incoherence": 3,
  "score_total": 82
}
```

## App And Web History

```text
GET /api/devices
GET /api/devices/{device_id}/events
GET /api/sessions?device_id={device_id}
GET /api/sessions/{session_id}
```

The Android app can keep using `api/get_history` during MVP, then migrate to the session endpoints when the backend is ready.
