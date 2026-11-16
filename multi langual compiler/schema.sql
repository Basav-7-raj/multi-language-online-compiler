-- MLOC: Multi-Language Online Compiler
-- Run this once to initialize the database

CREATE DATABASE IF NOT EXISTS mloc_db;
USE mloc_db;

CREATE TABLE IF NOT EXISTS saved_codes (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(100)  NOT NULL DEFAULT 'Untitled',
    language    ENUM('python','c','java') NOT NULL DEFAULT 'python',
    code        TEXT          NOT NULL,
    output      TEXT,
    created_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
);

-- Optional seed row so the app isn't empty on first launch
INSERT INTO saved_codes (title, language, code, output) VALUES
('Hello World (Python)', 'python', 'print("Hello, World!")\nprint("Welcome to MLOC!")', 'Hello, World!\nWelcome to MLOC!');
