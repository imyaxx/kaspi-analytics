# Kaspi Analytics — Web Dashboard

React + TypeScript + CSS Modules. No UI libs, no framework lock-in.

## Tech

- **Vite 5** — сборка, HMR, 200ms dev-старт
- **React 18** + **TypeScript 5.6**
- **CSS Modules** — изолированные стили без конфликтов
- **Fetch API** — без axios/swr, минимум зависимостей

## Install

```bash
cd web
npm install
```

## Dev

Запусти API (в другом терминале, из корня проекта):

```bash
uv run uvicorn kaspi_api.main:app --reload
```

Потом фронт:

```bash
cd web
npm run dev
```

Открой http://localhost:5173

Vite проксирует `/api/*` → `http://localhost:8000`, так что CORS не мешает.

## Build

```bash
npm run build
```

Готовые статики лежат в `web/dist/`. Деплой куда угодно: Vercel, Netlify, любой nginx.

## Env

Если API на другом домене в проде:

```bash
# web/.env.production
VITE_API_URL=https://api.yourdomain.kz
```

## Structure

```
web/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── src/
    ├── main.tsx              # entrypoint
    ├── App.tsx               # главный компонент
    ├── App.module.css
    ├── components/
    │   ├── Header.tsx        # статистика в шапке
    │   ├── Filters.tsx       # поиск, сортировка, фильтры
    │   ├── ProductGrid.tsx   # сетка товаров
    │   ├── ProductCard.tsx   # карточка
    │   └── Pagination.tsx
    ├── hooks/
    │   └── useProducts.ts    # хук загрузки с отменой
    ├── types/
    │   └── index.ts          # TS типы API
    ├── utils/
    │   ├── api.ts            # API client
    │   └── format.ts         # форматы цен/чисел
    └── styles/
        └── global.css        # CSS-переменные, reset
```
