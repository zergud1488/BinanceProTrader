import { sql } from 'drizzle-orm';
import {
  boolean,
  index,
  jsonb,
  pgTable,
  real,
  text,
  timestamp,
  varchar,
} from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";

// Session storage table for Replit Auth
export const sessions = pgTable(
  "sessions",
  {
    sid: varchar("sid").primaryKey(),
    sess: jsonb("sess").notNull(),
    expire: timestamp("expire").notNull(),
  },
  (table) => [index("IDX_session_expire").on(table.expire)],
);

// User storage table for Replit Auth
export const users = pgTable("users", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  email: varchar("email").unique(),
  firstName: varchar("first_name"),
  lastName: varchar("last_name"),
  profileImageUrl: varchar("profile_image_url"),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

// Trading configuration table
export const tradingConfigs = pgTable("trading_configs", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  userId: varchar("user_id").notNull().references(() => users.id, { onDelete: 'cascade' }),
  binanceApiKey: text("binance_api_key"),
  binanceSecretKey: text("binance_secret_key"),
  telegramBotToken: text("telegram_bot_token"),
  telegramChatId: varchar("telegram_chat_id"),
  candleChangePercent: real("candle_change_percent").default(2.5),
  positionSize: real("position_size").default(100),
  stopLoss: real("stop_loss").default(2.0),
  takeProfit: real("take_profit").default(4.0),
  trailingStop: real("trailing_stop").default(1.5),
  leverage: real("leverage").default(20),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

// Bot status table
export const botStatus = pgTable("bot_status", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  userId: varchar("user_id").notNull().references(() => users.id, { onDelete: 'cascade' }),
  tradingBotActive: boolean("trading_bot_active").default(false),
  riskManagementActive: boolean("risk_management_active").default(false),
  lastStarted: timestamp("last_started"),
  updatedAt: timestamp("updated_at").defaultNow(),
});

// Custom parameters table for admin constructor
export const customParameters = pgTable("custom_parameters", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  name: varchar("name").notNull(),
  type: varchar("type").notNull(), // 'number', 'percentage', 'boolean', 'select'
  description: text("description"),
  codeFragment: text("code_fragment"),
  isActive: boolean("is_active").default(true),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

// Account statistics table
export const accountStats = pgTable("account_stats", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  userId: varchar("user_id").notNull().references(() => users.id, { onDelete: 'cascade' }),
  futuresBalance: real("futures_balance").default(0),
  totalPnl: real("total_pnl").default(0),
  winRate: real("win_rate").default(0),
  openTrades: real("open_trades").default(0),
  updatedAt: timestamp("updated_at").defaultNow(),
});

// Trading history table
export const tradingHistory = pgTable("trading_history", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  userId: varchar("user_id").notNull().references(() => users.id, { onDelete: 'cascade' }),
  symbol: varchar("symbol").notNull(),
  side: varchar("side").notNull(), // 'long' or 'short'
  entryPrice: real("entry_price"),
  exitPrice: real("exit_price"),
  pnl: real("pnl"),
  pnlPercentage: real("pnl_percentage"),
  status: varchar("status").default('open'), // 'open', 'closed', 'cancelled'
  createdAt: timestamp("created_at").defaultNow(),
  closedAt: timestamp("closed_at"),
});

export type UpsertUser = typeof users.$inferInsert;
export type User = typeof users.$inferSelect;
export type TradingConfig = typeof tradingConfigs.$inferSelect;
export type InsertTradingConfig = typeof tradingConfigs.$inferInsert;
export type BotStatus = typeof botStatus.$inferSelect;
export type InsertBotStatus = typeof botStatus.$inferInsert;
export type CustomParameter = typeof customParameters.$inferSelect;
export type InsertCustomParameter = typeof customParameters.$inferInsert;
export type AccountStats = typeof accountStats.$inferSelect;
export type InsertAccountStats = typeof accountStats.$inferInsert;
export type TradingHistory = typeof tradingHistory.$inferSelect;
export type InsertTradingHistory = typeof tradingHistory.$inferInsert;

export const insertTradingConfigSchema = createInsertSchema(tradingConfigs).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
});

export const insertCustomParameterSchema = createInsertSchema(customParameters).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
});
