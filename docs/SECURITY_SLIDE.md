# Vendly.lk — Web Application Security Architecture

> **Presentation Slide Resource**: This document provides the layout, content, visual design structure, and speaker notes for a dedicated slide on **Security Architecture** to include in the Vendly.lk presentation slideshow.

---

## Slide Title & Subtitle

# Multi-Layered Enterprise Security & Threat Defense
### Protecting Merchants, Customers, and Data with Zero-Trust Controls

---

## Visual Slide Layout (Grid / 5-Pillar Architecture)

```
+---------------------------------------------------------------------------------------------------+
|                           VENDLY.LK MULTI-LAYERED SECURITY ARCHITECTURE                           |
+-------------------+--------------------+--------------------+--------------------+----------------+
|  FILE & MEDIA     |   SEARCH & XSS     |   AUTHENTICATION   |     ENTERPRISE     |   PERIMETER    |
|    IMMUNITY       |      DEFENSE       |    & REVOCATION    |        RBAC        |    DEFENSE     |
+-------------------+--------------------+--------------------+--------------------+----------------+
| * Magic Byte      | * HTML / Script    | * Cryptographic    | * Strict Role-     | * Global Rate  |
|   Binary Check    |   Tag Stripping    |   JWT Tokens       |   Based Access     |   Limiting     |
| * Script Payload  | * Null & Control   | * Immediate Token  | * Owner-Protected  | * Clickjacking |
|   Neutralization  |   Byte Removal     |   Revocation       |   Admin Hierarchy  |   Shield (DENY)|
| * Disguised File  | * ReDoS-Immune     | * Account Ban      | * Strict Tenant    | * MIME Sniff   |
|   Rejection       |   Linear Bounds    |   Instant Cut-Off  |   Data Isolation   |   Prevention   |
| * Isolated Cloud  | * Query Length     | * Verified Email   | * Least Privilege  | * HSTS & SSL   |
|   Storage & CDN   |   Hard Caps (80ch) |   Enforcement      |   Enforcement      |   Enforcement  |
+-------------------+--------------------+--------------------+--------------------+----------------+
```

---

## Slide Content (Copy-Paste Ready for Slideshow)

### Pillar 1: Deep File Inspection & Script Immunity
- **Binary Magic-Byte Validation**: File headers are cryptographically inspected (`FF D8 FF`, `89 PNG`, `RIFF...WEBP`, `ftyp`). Attackers cannot rename a malicious executable or script (`.php`, `.sh`, `.exe`, `.js`) to `.jpg` or `.png` to bypass checks.
- **Embedded Script Signature Prohibition**: Files containing `<script>`, `<?php`, `<html`, or `<svg` onload handlers are rejected at the gate.
- **Isolated Cloud Storage**: All media files are hosted on dedicated media CDNs (Cloudinary / Firebase Storage) rather than executed from the application host server.

### Pillar 2: Search Sanitization & Injection Defense
- **Cross-Site Scripting (XSS) Shield**: Search queries strip all HTML tag boundaries (`<... >`) and script patterns before processing.
- **Control Character Neutralization**: Strips unprintable bytes, NULL terminators (`\x00`), and terminal escape characters.
- **ReDoS (Regex Denial of Service) Immunity**: Capped at 80 characters with O(N) case-insensitive substring containment, preventing CPU-exhaustion denial-of-service attacks.

### Pillar 3: Zero-Trust Authentication & Session Revocation
- **Live Session Revocation (`check_revoked=True`)**: Unlike standard JWT implementations that stay valid until expiration, tokens are checked for revocation in real-time. Password changes, logouts, or admin suspensions immediately terminate active sessions.
- **Email Verification Guard**: Passwords accounts require verified email ownership before store management actions can be taken.

### Pillar 4: Hardened Multi-Tenant RBAC
- **Granular Staff Permissions**: Distinct permissions for Admins, Order Managers, Inventory Managers, Support Staff, and Viewers.
- **Anti-Privilege Escalation**: Store owners are permanently immutable; peer admins cannot demote, disable, or create new admins without verified store owner authorization.
- **Tenant Isolation**: Strict Firestore tenant scoping ensures merchants can never read or mutate data outside their business domain.

### Pillar 5: Perimeter Defense & HTTP Security Headers
- **Global & Tiered Rate Limiting**: Enforces global request limits (120 req/min) alongside sensitive per-endpoint limits on logins, exports, AI queries, and payments to defend against brute force and DDoS.
- **Modern Security Headers**:
  - `X-Content-Type-Options: nosniff`: Prevents browsers from MIME-sniffing away from declared content types.
  - `X-Frame-Options: DENY`: Blocks Clickjacking attacks by forbidding iframe embedding.
  - `Strict-Transport-Security`: Enforces HTTPS transport.
  - `Referrer-Policy: strict-origin-when-cross-origin`: Shields internal routes from external leakages.

---

## Speaker Notes (1-2 Minute Presentation Script)

> *"Security in Vendly.lk is designed with a defense-in-depth, zero-trust mindset across all five layers of our architecture.*
> 
> *First, for file uploads and media handling, we never trust client-provided file extensions or MIME headers. We implement deep binary magic-byte inspection and proactively strip dangerous script signatures, ensuring disguised scripts or malicious SVGs can never execute. Files are stored in isolated cloud object storage.*
> 
> *Second, we hardened all search and data-entry points against injection and ReDoS attacks. Queries are sanitized, stripped of control and HTML characters, and bounded to prevent catastrophic CPU denial-of-service.*
> 
> *Third, our identity layer uses cryptographically verified Firebase tokens backed by real-time revocation checks. If an account is suspended or a password is changed, sessions are cut off immediately—no zombie JWTs.*
> 
> *Fourth, our Role-Based Access Control protects store owners: peer admins cannot hijack administrative control or escalate permissions.*
> 
> *Finally, our perimeter is shielded with global rate limiting and enterprise HTTP security headers including Clickjacking defense and strict MIME-sniffing prevention.*
> 
> *This makes Vendly.lk secure, reliable, and trustworthy for Sri Lankan businesses and their customers."*
