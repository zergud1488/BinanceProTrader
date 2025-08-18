import {
  users,
  tradingConfigs,
  botStatus,
  customParameters,
  accountStats,
  tradingHistory,
  type User,
  type UpsertUser,
  type TradingConfig,
  type InsertTradingConfig,
  type BotStatus,
  type InsertBotStatus,
  type CustomParameter,
  type InsertCustomParameter,
  type AccountStats,
  type InsertAccountStats,
  type TradingHistory,
  type InsertTradingHistory,
} from "@shared/schema";
import { db } from "./db";
import { eq, desc } from "drizzle-orm";

export interface IStorage {
  // User operations (mandatory for Replit Auth)
  getUser(id: string): Promise<User | undefined>;
  upsertUser(user: UpsertUser): Promise<User>;
  
  // Trading configuration operations
  getTradingConfig(userId: string): Promise<TradingConfig | undefined>;
  upsertTradingConfig(config: InsertTradingConfig): Promise<TradingConfig>;
  
  // Bot status operations
  getBotStatus(userId: string): Promise<BotStatus | undefined>;
  upsertBotStatus(status: InsertBotStatus): Promise<BotStatus>;
  
  // Custom parameters operations (admin only)
  getCustomParameters(): Promise<CustomParameter[]>;
  createCustomParameter(param: InsertCustomParameter): Promise<CustomParameter>;
  updateCustomParameter(id: string, param: Partial<InsertCustomParameter>): Promise<CustomParameter | undefined>;
  deleteCustomParameter(id: string): Promise<boolean>;
  
  // Account statistics operations
  getAccountStats(userId: string): Promise<AccountStats | undefined>;
  upsertAccountStats(stats: InsertAccountStats): Promise<AccountStats>;
  
  // Trading history operations
  getTradingHistory(userId: string, limit?: number): Promise<TradingHistory[]>;
  createTradingHistory(trade: InsertTradingHistory): Promise<TradingHistory>;
  updateTradingHistory(id: string, trade: Partial<InsertTradingHistory>): Promise<TradingHistory | undefined>;
}

export class DatabaseStorage implements IStorage {
  // User operations
  async getUser(id: string): Promise<User | undefined> {
    const [user] = await db.select().from(users).where(eq(users.id, id));
    return user;
  }

  async upsertUser(userData: UpsertUser): Promise<User> {
    const [user] = await db
      .insert(users)
      .values(userData)
      .onConflictDoUpdate({
        target: users.id,
        set: {
          ...userData,
          updatedAt: new Date(),
        },
      })
      .returning();
    return user;
  }

  // Trading configuration operations
  async getTradingConfig(userId: string): Promise<TradingConfig | undefined> {
    const [config] = await db.select().from(tradingConfigs).where(eq(tradingConfigs.userId, userId));
    return config;
  }

  async upsertTradingConfig(configData: InsertTradingConfig): Promise<TradingConfig> {
    const [config] = await db
      .insert(tradingConfigs)
      .values(configData)
      .onConflictDoUpdate({
        target: [tradingConfigs.userId],
        set: {
          ...configData,
          updatedAt: new Date(),
        },
      })
      .returning();
    return config;
  }

  // Bot status operations
  async getBotStatus(userId: string): Promise<BotStatus | undefined> {
    const [status] = await db.select().from(botStatus).where(eq(botStatus.userId, userId));
    return status;
  }

  async upsertBotStatus(statusData: InsertBotStatus): Promise<BotStatus> {
    const [status] = await db
      .insert(botStatus)
      .values(statusData)
      .onConflictDoUpdate({
        target: [botStatus.userId],
        set: {
          ...statusData,
          updatedAt: new Date(),
        },
      })
      .returning();
    return status;
  }

  // Custom parameters operations
  async getCustomParameters(): Promise<CustomParameter[]> {
    return await db.select().from(customParameters).where(eq(customParameters.isActive, true));
  }

  async createCustomParameter(paramData: InsertCustomParameter): Promise<CustomParameter> {
    const [param] = await db.insert(customParameters).values(paramData).returning();
    return param;
  }

  async updateCustomParameter(id: string, paramData: Partial<InsertCustomParameter>): Promise<CustomParameter | undefined> {
    const [param] = await db
      .update(customParameters)
      .set({ ...paramData, updatedAt: new Date() })
      .where(eq(customParameters.id, id))
      .returning();
    return param;
  }

  async deleteCustomParameter(id: string): Promise<boolean> {
    const result = await db
      .update(customParameters)
      .set({ isActive: false, updatedAt: new Date() })
      .where(eq(customParameters.id, id));
    return result.rowCount > 0;
  }

  // Account statistics operations
  async getAccountStats(userId: string): Promise<AccountStats | undefined> {
    const [stats] = await db.select().from(accountStats).where(eq(accountStats.userId, userId));
    return stats;
  }

  async upsertAccountStats(statsData: InsertAccountStats): Promise<AccountStats> {
    const [stats] = await db
      .insert(accountStats)
      .values(statsData)
      .onConflictDoUpdate({
        target: [accountStats.userId],
        set: {
          ...statsData,
          updatedAt: new Date(),
        },
      })
      .returning();
    return stats;
  }

  // Trading history operations
  async getTradingHistory(userId: string, limit = 10): Promise<TradingHistory[]> {
    return await db
      .select()
      .from(tradingHistory)
      .where(eq(tradingHistory.userId, userId))
      .orderBy(desc(tradingHistory.createdAt))
      .limit(limit);
  }

  async createTradingHistory(tradeData: InsertTradingHistory): Promise<TradingHistory> {
    const [trade] = await db.insert(tradingHistory).values(tradeData).returning();
    return trade;
  }

  async updateTradingHistory(id: string, tradeData: Partial<InsertTradingHistory>): Promise<TradingHistory | undefined> {
    const [trade] = await db
      .update(tradingHistory)
      .set(tradeData)
      .where(eq(tradingHistory.id, id))
      .returning();
    return trade;
  }
}

export const storage = new DatabaseStorage();
