-- QuikSafe Bot - Row Level Security Policies
-- Run this SQL in Supabase SQL Editor AFTER running schema.sql

-- Disable RLS temporarily (we'll use service role key instead)
-- OR create permissive policies for the anon key

-- Option 1: Disable RLS (simpler, less secure but fine for personal use)
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE passwords DISABLE ROW LEVEL SECURITY;
ALTER TABLE tasks DISABLE ROW LEVEL SECURITY;
ALTER TABLE files DISABLE ROW LEVEL SECURITY;

-- Option 2: Create permissive policies (more secure)
-- Uncomment below if you want to keep RLS enabled:

/*
-- Users table policies
CREATE POLICY "Allow all operations on users" ON users
    FOR ALL USING (true) WITH CHECK (true);

-- Passwords table policies
CREATE POLICY "Allow all operations on passwords" ON passwords
    FOR ALL USING (true) WITH CHECK (true);

-- Tasks table policies
CREATE POLICY "Allow all operations on tasks" ON tasks
    FOR ALL USING (true) WITH CHECK (true);

-- Files table policies
CREATE POLICY "Allow all operations on files" ON files
    FOR ALL USING (true) WITH CHECK (true);
*/
