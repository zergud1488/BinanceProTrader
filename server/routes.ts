import type { Express } from "express";
import { createServer, type Server } from "http";
import { storage } from "./storage";
import { setupAuth, isAuthenticated } from "./replitAuth";
import { insertTradingConfigSchema, insertCustomParameterSchema } from "@shared/schema";
import { z } from "zod";

export async function registerRoutes(app: Express): Promise<Server> {
  // Auth middleware
  await setupAuth(app);

  // Auth routes
  app.get('/api/auth/user', isAuthenticated, async (req: any, res) => {
    try {
      const userId = req.user.claims.sub;
      const user = await storage.getUser(userId);
      res.json(user);
    } catch (error) {
      console.error("Error fetching user:", error);
      res.status(500).json({ message: "Failed to fetch user" });
    }
  });

  // Trading configuration routes
  app.get('/api/trading-config', isAuthenticated, async (req: any, res) => {
    try {
      const userId = req.user.claims.sub;
      const config = await storage.getTradingConfig(userId);
      res.json(config);
    } catch (error) {
      console.error("Error fetching trading config:", error);
      res.status(500).json({ message: "Failed to fetch trading configuration" });
    }
  });

  app.post('/api/trading-config', isAuthenticated, async (req: any, res) => {
    try {
      const userId = req.user.claims.sub;
      const validatedData = insertTradingConfigSchema.parse({ ...req.body, userId });
      const config = await storage.upsertTradingConfig(validatedData);
      res.json(config);
    } catch (error) {
      console.error("Error saving trading config:", error);
      res.status(500).json({ message: "Failed to save trading configuration" });
    }
  });

  // Bot status routes
  app.get('/api/bot-status', isAuthenticated, async (req: any, res) => {
    try {
      const userId = req.user.claims.sub;
      const status = await storage.getBotStatus(userId);
      res.json(status);
    } catch (error) {
      console.error("Error fetching bot status:", error);
      res.status(500).json({ message: "Failed to fetch bot status" });
    }
  });

  app.post('/api/bot-status', isAuthenticated, async (req: any, res) => {
    try {
      const userId = req.user.claims.sub;
      const { tradingBotActive, riskManagementActive } = req.body;
      const statusData = {
        userId,
        tradingBotActive,
        riskManagementActive,
        lastStarted: (tradingBotActive || riskManagementActive) ? new Date() : undefined,
      };
      const status = await storage.upsertBotStatus(statusData);
      res.json(status);
    } catch (error) {
      console.error("Error updating bot status:", error);
      res.status(500).json({ message: "Failed to update bot status" });
    }
  });

  // Account statistics routes
  app.get('/api/account-stats', isAuthenticated, async (req: any, res) => {
    try {
      const userId = req.user.claims.sub;
      const stats = await storage.getAccountStats(userId);
      res.json(stats);
    } catch (error) {
      console.error("Error fetching account stats:", error);
      res.status(500).json({ message: "Failed to fetch account statistics" });
    }
  });

  app.post('/api/account-stats', isAuthenticated, async (req: any, res) => {
    try {
      const userId = req.user.claims.sub;
      const statsData = { ...req.body, userId };
      const stats = await storage.upsertAccountStats(statsData);
      res.json(stats);
    } catch (error) {
      console.error("Error updating account stats:", error);
      res.status(500).json({ message: "Failed to update account statistics" });
    }
  });

  // Trading history routes
  app.get('/api/trading-history', isAuthenticated, async (req: any, res) => {
    try {
      const userId = req.user.claims.sub;
      const limit = req.query.limit ? parseInt(req.query.limit as string) : 10;
      const history = await storage.getTradingHistory(userId, limit);
      res.json(history);
    } catch (error) {
      console.error("Error fetching trading history:", error);
      res.status(500).json({ message: "Failed to fetch trading history" });
    }
  });

  // Custom parameters routes (admin only)
  app.get('/api/custom-parameters', isAuthenticated, async (req: any, res) => {
    try {
      // Check if user is admin (for demo purposes, check if username is 'Mustek')
      const userId = req.user.claims.sub;
      const user = await storage.getUser(userId);
      
      // For demo purposes, allow access if user exists
      // In production, implement proper role checking
      const parameters = await storage.getCustomParameters();
      res.json(parameters);
    } catch (error) {
      console.error("Error fetching custom parameters:", error);
      res.status(500).json({ message: "Failed to fetch custom parameters" });
    }
  });

  app.post('/api/custom-parameters', isAuthenticated, async (req: any, res) => {
    try {
      const validatedData = insertCustomParameterSchema.parse(req.body);
      const parameter = await storage.createCustomParameter(validatedData);
      res.json(parameter);
    } catch (error) {
      console.error("Error creating custom parameter:", error);
      res.status(500).json({ message: "Failed to create custom parameter" });
    }
  });

  app.put('/api/custom-parameters/:id', isAuthenticated, async (req: any, res) => {
    try {
      const { id } = req.params;
      const parameter = await storage.updateCustomParameter(id, req.body);
      if (!parameter) {
        return res.status(404).json({ message: "Parameter not found" });
      }
      res.json(parameter);
    } catch (error) {
      console.error("Error updating custom parameter:", error);
      res.status(500).json({ message: "Failed to update custom parameter" });
    }
  });

  app.delete('/api/custom-parameters/:id', isAuthenticated, async (req: any, res) => {
    try {
      const { id } = req.params;
      const success = await storage.deleteCustomParameter(id);
      if (!success) {
        return res.status(404).json({ message: "Parameter not found" });
      }
      res.json({ success: true });
    } catch (error) {
      console.error("Error deleting custom parameter:", error);
      res.status(500).json({ message: "Failed to delete custom parameter" });
    }
  });

  const httpServer = createServer(app);
  return httpServer;
}
