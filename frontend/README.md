# Frontend — RailDoc

This is the **React + TypeScript + Vite** UI for RailDoc.

It connects to the Python FastAPI backend through `/api` and provides:

- login and JWT-based session handling
- role-based navigation and permissions
- a live clock and date in the header
- dashboard, queue, timeline, block plan, explainability, simulation, comparison, user management, and audit screens

---

## Project Structure

```
frontend/
├── public/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── index.css
│   ├── api/
│   │   ├── client.ts
│   │   ├── AuthContext.tsx
│   │   └── DataContext.tsx
│   ├── components/
│   │   ├── Login.tsx
│   │   ├── Dashboard.tsx
│   │   ├── MaintenanceQueue.tsx
│   │   ├── CorridorTimeline.tsx
│   │   ├── BlockPlan.tsx
│   │   ├── Explainability.tsx
│   │   ├── WhatIfSimulator.tsx
│   │   ├── BeforeAfter.tsx
│   │   ├── UserManagement.tsx
│   │   └── AuditLog.tsx
│   └── types/
│       └── index.ts
├── index.html
├── vite.config.ts
├── package.json
├── nginx.conf
└── README.md
```

---

## Stack

- React
- TypeScript
- Vite
- Tailwind CSS
- Recharts
- Axios for API calls

---

## Getting Started

### Install

```bash
cd frontend
npm install
```

### Run in development

```bash
npm run dev
```

By default the dev server runs on **http://localhost:5173** and proxies `/api` requests to the backend.

### Build

```bash
npm run build
```

### Preview a production build

```bash
npm run preview
```

---

## How it connects to the backend

The app expects the backend to be available under `/api`.

In local development, `vite.config.ts` proxies that path to the backend. In deployed setups, nginx is used to forward `/api` traffic to the backend container.

Authentication tokens are stored in the browser and attached to API requests automatically. If a request fails with `401`, the app tries to refresh the token silently.

---

## Auth and roles

The frontend does not define users itself. It logs in through the backend and then renders screens based on the user's roles.

Demo users are configured in the backend, not in the frontend.

---

## Main screens

- **Login**
- **Dashboard**
- **Maintenance Queue**
- **Corridor Timeline**
- **Block Plan**
- **Explainability**
- **What-If Simulator**
- **Before/After**
- **User Management**
- **Audit Log**

---

## State

The frontend uses two main contexts:

- `AuthContext` for login, logout, tokens, and the current user
- `DataContext` for assets, tasks, trains, corridors, block windows, blocks, dashboard data, comparison data, and optimization progress

---

## Notes for developers

- Tailwind v4 is used with the Vite plugin in this project
- TypeScript typecheck and Vite build both run cleanly in the current setup
- The header includes a live clock and date formatted for IST
- Navigation between screens is handled inside `App.tsx`
- API calls live in `src/api/client.ts`
- Shared types live in `src/types/index.ts`
