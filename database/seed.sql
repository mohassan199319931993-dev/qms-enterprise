-- ============================================================
-- QMS Seed Data
-- Run after schema.sql
-- ============================================================

-- Default Permissions
INSERT INTO permissions (name, module, action, description) VALUES
-- Users module
('users.view', 'users', 'view', 'View users list'),
('users.create', 'users', 'create', 'Create new users'),
('users.edit', 'users', 'edit', 'Edit user data'),
('users.delete', 'users', 'delete', 'Delete users'),
-- Roles module
('roles.view', 'roles', 'view', 'View roles'),
('roles.create', 'roles', 'create', 'Create roles'),
('roles.edit', 'roles', 'edit', 'Edit roles'),
('roles.delete', 'roles', 'delete', 'Delete roles'),
-- Dashboard
('dashboard.view', 'dashboard', 'view', 'Access dashboard'),
-- Reports
('reports.view', 'reports', 'view', 'View reports'),
('reports.create', 'reports', 'create', 'Create reports'),
-- Quality
('quality.view', 'quality', 'view', 'View quality data'),
('quality.create', 'quality', 'create', 'Create quality records'),
('quality.edit', 'quality', 'edit', 'Edit quality records'),
-- Factory
('factory.view', 'factory', 'view', 'View factory settings'),
('factory.edit', 'factory', 'edit', 'Edit factory settings');

-- ============================================================
-- Demo Factory
-- ============================================================
INSERT INTO factories (id, name, location, subscription_plan)
VALUES (1, 'Demo Factory', 'Cairo, Egypt', 'enterprise');

-- ============================================================
-- System Roles for Demo Factory
-- ============================================================
INSERT INTO roles (id, name, description, factory_id, is_system_role) VALUES
(1, 'Admin', 'Full system access', 1, TRUE),
(2, 'Quality Manager', 'Quality management access', 1, FALSE),
(3, 'Inspector', 'Inspection and data entry', 1, FALSE),
(4, 'Viewer', 'Read-only access', 1, FALSE);

-- Admin gets all permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT 1, id FROM permissions;

-- Quality Manager permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT 2, id FROM permissions WHERE module IN ('dashboard', 'reports', 'quality');

-- Inspector permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT 3, id FROM permissions WHERE module IN ('dashboard', 'quality') AND action IN ('view', 'create');

-- Viewer permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT 4, id FROM permissions WHERE action = 'view';

-- ============================================================
-- Demo Admin User (password: Admin@123)
-- Hash generated with bcrypt rounds=12
-- ============================================================
-- NOTE: The actual hash is generated at runtime via Flask CLI
-- Run: flask seed-admin
-- Or use the admin-register endpoint

-- Reset sequences
SELECT setval('factories_id_seq', (SELECT MAX(id) FROM factories));
SELECT setval('roles_id_seq', (SELECT MAX(id) FROM roles));

-- ============================================================
-- Admin user is created via: python backend/seed_admin.py
-- OR via the /admin-register endpoint in the frontend
-- Default credentials: admin@qms.com / Admin@123!
-- ============================================================
