# Campux Landing Page

A modern, mobile-first landing page for the Campux campus super‑app, plus a lightweight local admin console powered by LocalStorage.

## Features
- WhatsApp‑green visual theme and bold UI sections
- Responsive layout for mobile and desktop
- Marketplace section with real image cards
- Waitlist + Contact forms stored in LocalStorage
- Admin console for waitlist, contacts, and announcements
- Live announcements displayed on the landing page

## Project Structure
- `index.html` — Main landing page
- `admin.html` — Admin console (LocalStorage‑based)
- `icon.jpg` — App logo
- `kenny.jfif` — Developer photo
- `mac.jpg`, `graphic.jpg`, `campus.jpg`, `sam.jpg` — Marketplace images

## How To Run
Just open `index.html` in a browser.

To access the admin console:
- Open `admin.html`
- Passcode: `197012`

## LocalStorage Keys
These keys are used for the admin system:
- `campux_waitlist`
- `campux_contacts`
- `campux_announcements`
- `campux_admin_note`
- `campux_admin_auth`

## Notes
- The admin console is local‑only and uses LocalStorage (no server).
- Announcements created in `admin.html` appear automatically on the landing page.
