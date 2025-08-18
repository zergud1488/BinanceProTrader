# Overview

Веб-платформа для автоматичної торгівлі на Binance з українським інтерфейсом у стилі Binance. Система надає функціонал автоматичної торгівлі криптовалютами через API Binance з авторизацією користувачів, управлінням конфігурацією та моніторингом в реальному часі. Користувачі можуть налаштовувати параметри торгівлі, керувати ботами та відстежувати свою торгову ефективність через комплексний інтерфейс дашборду.

# User Preferences

Preferred communication style: Simple, everyday language.
Language: Ukrainian interface and text
Design theme: Binance-style dark theme with yellow/black color scheme
Admin access: User "Mustek" with password "zergud" should have admin privileges

# System Architecture

## Frontend Architecture
The client-side is built using **React with TypeScript** and follows a component-based architecture:
- **UI Framework**: Utilizes Radix UI components with shadcn/ui for consistent design system
- **Styling**: Tailwind CSS with custom Binance-themed color palette and design tokens
- **State Management**: TanStack Query (React Query) for server state management and caching
- **Routing**: Wouter for lightweight client-side routing
- **Build Tool**: Vite for fast development and optimized production builds

## Backend Architecture
The server implements a **RESTful API** using Express.js with TypeScript:
- **Framework**: Express.js with middleware for JSON parsing, CORS, and request logging
- **Authentication**: Replit OIDC integration with Passport.js strategy
- **Session Management**: Express sessions with PostgreSQL storage using connect-pg-simple
- **API Design**: RESTful endpoints organized by feature (auth, trading config, bot status, etc.)
- **Error Handling**: Centralized error middleware with structured error responses

## Data Storage Solutions
**PostgreSQL Database** with Drizzle ORM:
- **ORM**: Drizzle for type-safe database operations and schema management
- **Connection**: Neon serverless PostgreSQL with connection pooling
- **Schema**: Well-structured tables for users, trading configs, bot status, account stats, and trading history
- **Migrations**: Drizzle Kit for database schema migrations and version control

## Authentication and Authorization
**Replit OIDC Integration**:
- **Provider**: Replit's OpenID Connect for seamless authentication
- **Strategy**: Passport.js with custom OIDC strategy
- **Session Storage**: PostgreSQL-backed sessions with configurable TTL
- **Security**: HTTP-only cookies with secure flags and CSRF protection
- **Role-based Access**: Admin functionality for custom parameter management

## Key Design Patterns
- **Repository Pattern**: Storage interface abstraction for database operations
- **Middleware Chain**: Structured request processing with authentication, logging, and error handling
- **Component Composition**: React components built with composition over inheritance
- **Custom Hooks**: Reusable logic extraction for authentication, toast notifications, and API calls

# External Dependencies

## Database Services
- **Neon PostgreSQL**: Serverless PostgreSQL database for production workloads
- **Drizzle ORM**: Type-safe database toolkit with schema introspection

## Authentication Services
- **Replit OIDC**: OpenID Connect provider for user authentication and authorization

## Trading Integrations
- **Binance API**: Cryptocurrency exchange integration for trading operations (configured via user API keys)
- **Telegram Bot API**: Notification system for trading alerts and bot status updates

## UI and Styling
- **Radix UI**: Headless component library for accessible UI primitives
- **shadcn/ui**: Pre-built component library based on Radix UI
- **Tailwind CSS**: Utility-first CSS framework for styling
- **Lucide React**: Icon library for consistent iconography

## Development Tools
- **Vite**: Build tool and development server with HMR support
- **TypeScript**: Type safety across frontend and backend
- **ESBuild**: Fast JavaScript bundler for production builds
- **PostCSS**: CSS processing with Tailwind CSS integration