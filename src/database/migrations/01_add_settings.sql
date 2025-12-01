-- Migration: Add settings column to users table
-- Description: Adds a JSONB column to store user preferences like notifications, security settings, etc.

ALTER TABLE users 
ADD COLUMN IF NOT EXISTS settings JSONB DEFAULT '{"notifications": {"tasks": true, "summary": false}, "security": {"auto_lock_minutes": 60}}'::jsonb;
