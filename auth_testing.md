# Auth Testing Playbook — LA Tracker

## Admin credentials (seeded on startup)
- Email: `admin@la-tracker.com`
- Password: `admin123`

## Steps

### 1) MongoDB Verification
```
mongosh
use test_database
db.users.find({role: "admin"}).pretty()
db.users.findOne({role: "admin"}, {password_hash: 1})
```
- Verify: bcrypt hash starts with `$2b$`
- Indexes: `users.email` unique, `login_attempts.identifier`, `password_reset_tokens.expires_at` TTL

### 2) API Testing
```
curl -c cookies.txt -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@la-tracker.com","password":"admin123"}'
cat cookies.txt
curl -b cookies.txt http://localhost:8001/api/auth/me
```
- `login` returns user object, sets `access_token` + `refresh_token` cookies
- `/me` returns the same user via cookies

### 3) RBAC (roles: admin | operator | viewer)
- Admin can access `/api/users`
- Operator can create/update workorders but NOT manage users
- Viewer can only GET workorders/dashboard
