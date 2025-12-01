-- QuikSafe Bot - Row Level Security Policies
-- Run this SQL in Supabase SQL Editor AFTER running schema.sql

-- Disable RLS temporarily (we'll use service role key instead)
-- OR create permissive policies for the anon key

-- Option 1: Disable RLS (Commented out)
-- ALTER TABLE users DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE passwords DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE tasks DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE files DISABLE ROW LEVEL SECURITY;

-- Option 2: Create permissive policies (more secure)
-- First, ensure RLS is enabled
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE passwords ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE files ENABLE ROW LEVEL SECURITY;

-- Users table policies
DROP POLICY IF EXISTS "Allow all operations on users" ON users;
CREATE POLICY "Allow all operations on users" ON users
    FOR ALL USING (true) WITH CHECK (true);

-- Passwords table policies
DROP POLICY IF EXISTS "Allow all operations on passwords" ON passwords;
CREATE POLICY "Allow all operations on passwords" ON passwords
    FOR ALL USING (true) WITH CHECK (true);

-- Tasks table policies
DROP POLICY IF EXISTS "Allow all operations on tasks" ON tasks;
CREATE POLICY "Allow all operations on tasks" ON tasks
    FOR ALL USING (true) WITH CHECK (true);

-- Files table policies
DROP POLICY IF EXISTS "Allow all operations on files" ON files;
CREATE POLICY "Allow all operations on files" ON files
    FOR ALL USING (true) WITH CHECK (true);
