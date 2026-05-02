DROP TABLE IF EXISTS phones CASCADE;
DROP TABLE IF EXISTS contacts CASCADE;
DROP TABLE IF EXISTS groups CASCADE;

-- 1. Таблица групп
CREATE TABLE groups (
    group_id SERIAL PRIMARY KEY,
    group_name VARCHAR(100) UNIQUE NOT NULL
);

-- 2. Таблица контактов
CREATE TABLE contacts (
    contact_id SERIAL PRIMARY KEY,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255),
    email VARCHAR(255) UNIQUE,
    birthday DATE,
    group_id INT REFERENCES groups(group_id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Таблица телефонов
CREATE TABLE phones (
    phone_id SERIAL PRIMARY KEY,
    contact_id INT REFERENCES contacts(contact_id) ON DELETE CASCADE,
    phone_number VARCHAR(20) NOT NULL UNIQUE,
    phone_type VARCHAR(10) CHECK (phone_type IN ('home', 'work', 'mobile'))
);

DROP FUNCTION IF EXISTS search_contacts(TEXT);

-- 4. Функция: Поиск по всем полям (Имя, Фамилия, Email, Телефоны)
CREATE OR REPLACE FUNCTION search_contacts(p_query TEXT)
RETURNS TABLE (
    id INT, 
    first_name VARCHAR, 
    last_name VARCHAR, 
    email VARCHAR, 
    phones TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.contact_id, c.first_name, c.last_name, c.email, 
        COALESCE(string_agg(p.phone_number || ' (' || p.phone_type || ')', ', '), '') AS phones
    FROM contacts c
    LEFT JOIN phones p ON c.contact_id = p.contact_id
    WHERE 
        c.first_name ILIKE '%' || p_query || '%' OR 
        c.last_name ILIKE '%' || p_query || '%' OR 
        c.email ILIKE '%' || p_query || '%' OR 
        p.phone_number ILIKE '%' || p_query || '%'
    GROUP BY c.contact_id;
END;
$$ LANGUAGE plpgsql;